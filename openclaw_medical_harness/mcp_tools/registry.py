"""Medical tool registry backed by real HTTP and local adapters."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .adapters import GraphQLToolAdapter, HTTPRequestSpec, HTTPToolAdapter, LocalToolAdapter, ToolAdapter


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _derive_query_from_context(context: dict[str, Any], explicit: str | None = None) -> str:
    patient = context.get("patient", {})
    pieces: list[str] = []
    for value in [
        explicit,
        patient.get("chief_complaint"),
        patient.get("disease"),
        patient.get("target"),
    ]:
        if value:
            pieces.append(str(value))
    symptoms = patient.get("symptoms", [])
    if symptoms:
        pieces.extend(str(symptom) for symptom in symptoms[:4])
    conditions = patient.get("conditions", [])
    if conditions:
        pieces.extend(str(condition) for condition in conditions[:2])
    return " ".join(piece for piece in pieces if piece).strip()


def _build_pubmed_request(context: dict[str, Any], **kwargs: Any) -> HTTPRequestSpec:
    query = _derive_query_from_context(context, kwargs.get("query"))
    max_results = int(kwargs.get("max_results", 5))
    return HTTPRequestSpec(
        method="GET",
        url="esearch.fcgi",
        params={
            "db": "pubmed",
            "retmode": "json",
            "retmax": max_results,
            "sort": kwargs.get("sort", "relevance"),
            "term": query,
        },
    )


def _parse_pubmed_response(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()["esearchresult"]
    return {
        "tool": "pubmed",
        "query": payload.get("querytranslation", ""),
        "count": int(payload.get("count", 0)),
        "ids": payload.get("idlist", []),
        "status": "ok",
    }


def _build_chembl_request(context: dict[str, Any], **kwargs: Any) -> HTTPRequestSpec:
    query_type = kwargs.get("query_type", "molecule")
    identifier = _first_non_empty(
        kwargs.get("identifier"),
        kwargs.get("target"),
        kwargs.get("disease"),
        context.get("patient", {}).get("target"),
        context.get("patient", {}).get("disease"),
    )
    path_map = {
        "molecule": "molecule/search.json",
        "target": "target/search.json",
        "mechanism": "mechanism/search.json",
    }
    return HTTPRequestSpec(
        method="GET",
        url=path_map.get(query_type, "molecule/search.json"),
        params={"q": str(identifier or "")},
    )


def _parse_chembl_response(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    records = []
    for key, value in payload.items():
        if key.endswith("_list") and isinstance(value, list):
            records = value
            break
    return {
        "tool": "chembl",
        "count": len(records),
        "records": records[:5],
        "status": "ok",
    }


OPENTARGETS_SEARCH_QUERY = """
query SearchEntities($queryString: String!) {
  search(queryString: $queryString, page: {index: 0, size: 5}, entityNames: ["target", "disease"]) {
    total
    hits {
      id
      entity
      object {
        ... on Target {
          approvedSymbol
          approvedName
        }
        ... on Disease {
          name
          description
        }
      }
    }
  }
}
""".strip()


def _build_opentargets_request(context: dict[str, Any], **kwargs: Any) -> HTTPRequestSpec:
    query_string = _derive_query_from_context(context, kwargs.get("query"))
    if kwargs.get("gene"):
        query_string = f"{kwargs['gene']} {query_string}".strip()
    if kwargs.get("disease"):
        query_string = f"{query_string} {kwargs['disease']}".strip()
    return HTTPRequestSpec(
        method="POST",
        url="",
        json_body={"query": OPENTARGETS_SEARCH_QUERY, "variables": {"queryString": query_string}},
        headers={"content-type": "application/json"},
    )


def _parse_opentargets_response(response: httpx.Response) -> dict[str, Any]:
    payload = response.json().get("data", {}).get("search", {})
    return {
        "tool": "opentargets",
        "total": payload.get("total", 0),
        "hits": payload.get("hits", []),
        "status": "ok",
    }


def _build_omim_request(context: dict[str, Any], **kwargs: Any) -> HTTPRequestSpec:
    api_key = kwargs.get("api_key")
    if not api_key:
        raise RuntimeError("OMIM API key required")
    query = _derive_query_from_context(context, kwargs.get("search"))
    return HTTPRequestSpec(
        method="GET",
        url="entry/search",
        params={"search": query, "apiKey": api_key, "format": "json"},
    )


def _parse_omim_response(response: httpx.Response) -> dict[str, Any]:
    payload = response.json().get("omim", {}).get("searchResponse", {})
    return {
        "tool": "omim",
        "total": payload.get("totalResults", 0),
        "entries": payload.get("entryList", [])[:5],
        "status": "ok",
    }


def _build_openfda_request(context: dict[str, Any], **kwargs: Any) -> HTTPRequestSpec:
    dataset = kwargs.get("dataset", "drug/label.json")
    search = _first_non_empty(
        kwargs.get("search"),
        context.get("patient", {}).get("drug"),
        (context.get("patient", {}).get("conditions") or [None])[0],
        kwargs.get("query"),
    )
    return HTTPRequestSpec(
        method="GET",
        url=dataset,
        params={"search": str(search or ""), "limit": int(kwargs.get("limit", 5))},
    )


def _parse_openfda_response(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    return {
        "tool": "openfda",
        "meta": payload.get("meta", {}),
        "results": payload.get("results", [])[:5],
        "status": "ok",
    }


def _run_rdkit_adapter(context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    smiles = kwargs.get("smiles") or context.get("patient", {}).get("smiles") or context.get("smiles")
    operation = kwargs.get("operation", "descriptors")
    if not smiles:
        return {"tool": "rdkit", "error": "smiles is required"}
    if importlib.util.find_spec("rdkit") is None:
        return {
            "tool": "rdkit",
            "error": "rdkit is not installed in the current environment",
            "smiles": smiles,
        }
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {"tool": "rdkit", "error": "invalid smiles", "smiles": smiles}
    if operation == "descriptors":
        return {
            "tool": "rdkit",
            "smiles": smiles,
            "molecular_weight": round(Descriptors.MolWt(molecule), 3),
            "logp": round(Crippen.MolLogP(molecule), 3),
            "hbd": Lipinski.NumHDonors(molecule),
            "hba": Lipinski.NumHAcceptors(molecule),
            "status": "ok",
        }
    if operation == "formula":
        return {
            "tool": "rdkit",
            "smiles": smiles,
            "formula": Chem.rdMolDescriptors.CalcMolFormula(molecule),
            "status": "ok",
        }
    return {"tool": "rdkit", "error": f"unsupported operation: {operation}"}


@dataclass
class MCPTool:
    name: str
    description: str
    category: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    adapter: ToolAdapter | None = None
    aliases: tuple[str, ...] = ()

    @property
    def endpoint(self) -> str:
        return self.adapter.endpoint if self.adapter else ""

    @property
    def transport(self) -> str:
        return self.adapter.transport if self.adapter else "callable"

    @property
    def protocol(self) -> str:
        return self.adapter.protocol if self.adapter else "local"

    def execute(self, context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        if self.adapter is None:
            return {"tool": self.name, "error": "no adapter configured"}
        try:
            return self.adapter.invoke(context, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            return {"tool": self.name, "error": str(exc)}


HARNESS_TOOLCHAINS: dict[str, tuple[str, ...]] = {
    "diagnosis": ("pubmed", "omim", "opentargets"),
    "drug_discovery": ("chembl", "opentargets", "pubmed", "rdkit"),
    "health_management": ("pubmed", "openfda"),
}


def create_builtin_tools(client: httpx.Client | None = None) -> dict[str, MCPTool]:
    return {
        "pubmed": MCPTool(
            name="pubmed",
            description="PubMed literature search",
            category="literature",
            parameters={"query": "string", "max_results": "int", "sort": "string"},
            adapter=HTTPToolAdapter(
                base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
                request_builder=_build_pubmed_request,
                response_parser=_parse_pubmed_response,
                client=client,
            ),
            aliases=("pubmed_search",),
        ),
        "chembl": MCPTool(
            name="chembl",
            description="ChEMBL compound activity data",
            category="drug",
            parameters={"query_type": "string", "identifier": "string"},
            adapter=HTTPToolAdapter(
                base_url="https://www.ebi.ac.uk/chembl/api/data",
                request_builder=_build_chembl_request,
                response_parser=_parse_chembl_response,
                client=client,
            ),
            aliases=("chembl_query",),
        ),
        "opentargets": MCPTool(
            name="opentargets",
            description="OpenTargets target-disease evidence search",
            category="target",
            parameters={"query": "string", "gene": "string", "disease": "string"},
            adapter=GraphQLToolAdapter(
                base_url="https://api.platform.opentargets.org/api/v4/graphql",
                request_builder=_build_opentargets_request,
                response_parser=_parse_opentargets_response,
                client=client,
            ),
            aliases=("opentargets_association",),
        ),
        "omim": MCPTool(
            name="omim",
            description="OMIM genetics knowledge base",
            category="genetics",
            parameters={"search": "string", "api_key": "string"},
            adapter=HTTPToolAdapter(
                base_url="https://api.omim.org/api",
                request_builder=_build_omim_request,
                response_parser=_parse_omim_response,
                client=client,
            ),
            aliases=("omim_lookup",),
        ),
        "openfda": MCPTool(
            name="openfda",
            description="OpenFDA drug safety and label data",
            category="safety",
            parameters={"dataset": "string", "search": "string", "limit": "int"},
            adapter=HTTPToolAdapter(
                base_url="https://api.fda.gov",
                request_builder=_build_openfda_request,
                response_parser=_parse_openfda_response,
                client=client,
            ),
            aliases=("openfda_safety", "openfae_safety"),
        ),
        "rdkit": MCPTool(
            name="rdkit",
            description="RDKit cheminformatics descriptors",
            category="cheminformatics",
            parameters={"smiles": "string", "operation": "string"},
            adapter=LocalToolAdapter(_run_rdkit_adapter, endpoint="local://rdkit"),
        ),
    }


class MedicalToolRegistry:
    """Registry with alias resolution plus real execution against adapters."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._aliases: dict[str, str] = {}
        for name, tool in create_builtin_tools(client=client).items():
            self.register(name, tool)

    def register(self, name: str, tool: MCPTool | Any) -> None:
        if not isinstance(tool, MCPTool):
            if hasattr(tool, "execute"):
                tool = MCPTool(
                    name=name,
                    description=getattr(tool, "description", ""),
                    adapter=LocalToolAdapter(tool.execute, endpoint=f"local://{name}"),
                )
            else:
                raise ValueError("Tool must be MCPTool or expose execute()")
        self._tools[name] = tool
        self._aliases[name] = name
        for alias in tool.aliases:
            self._aliases[alias] = name

    def resolve_name(self, name: str) -> str | None:
        return self._aliases.get(name)

    def get(self, name: str) -> MCPTool | None:
        canonical = self.resolve_name(name)
        return self._tools.get(canonical) if canonical else None

    def call(self, name: str, context: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        tool = self.get(name)
        if tool is None:
            return {"tool": name, "error": "tool not found"}
        return tool.execute(context or {}, **kwargs)

    def list_tools(self, category: str = "") -> list[dict[str, Any]]:
        rows = []
        for tool in self._tools.values():
            if category and tool.category != category:
                continue
            rows.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category,
                    "aliases": list(tool.aliases),
                    "endpoint": tool.endpoint,
                    "transport": tool.transport,
                    "protocol": tool.protocol,
                }
            )
        return rows

    def list_all(self) -> list[dict[str, Any]]:
        return self.list_tools()

    def list_categories(self) -> list[str]:
        return sorted({tool.category for tool in self._tools.values() if tool.category})

    def list_toolchains(self) -> dict[str, list[dict[str, Any]]]:
        return {
            harness_type: self.get_tools_for_harness(harness_type)
            for harness_type in sorted(HARNESS_TOOLCHAINS)
        }

    def get_tools_for_harness(self, harness_type: str) -> list[dict[str, Any]]:
        return [tool for tool_name in HARNESS_TOOLCHAINS.get(harness_type, ()) if (tool := self._describe(tool_name))]

    def execute_toolchain(
        self,
        harness_type: str,
        context: dict[str, Any],
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for tool_name in HARNESS_TOOLCHAINS.get(harness_type, ()):
            params = (overrides or {}).get(tool_name, {})
            results[tool_name] = self.call(tool_name, context, **params)
        return results

    def _describe(self, tool_name: str) -> dict[str, Any] | None:
        tool = self.get(tool_name)
        if tool is None:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "aliases": list(tool.aliases),
            "endpoint": tool.endpoint,
            "transport": tool.transport,
            "protocol": tool.protocol,
        }
