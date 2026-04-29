"""Real transport adapters for MCP-style and HTTP-backed tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


class ToolInvocationError(RuntimeError):
    """Raised when a transport-backed tool cannot be executed successfully."""


@dataclass
class HTTPRequestSpec:
    method: str = "GET"
    url: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    data: Any = None
    headers: dict[str, str] = field(default_factory=dict)


class ToolAdapter(ABC):
    """Adapter interface used by the registry to invoke real transports."""

    transport: str = "callable"
    protocol: str = "local"
    endpoint: str = ""

    @abstractmethod
    def invoke(self, context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        ...


class LocalToolAdapter(ToolAdapter):
    transport = "local"
    protocol = "python"

    def __init__(self, handler: Callable[[dict[str, Any]], dict[str, Any]], endpoint: str = "local://handler"):
        self.handler = handler
        self.endpoint = endpoint

    def invoke(self, context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.handler(context, **kwargs)


class HTTPToolAdapter(ToolAdapter):
    """Generic HTTP adapter with pluggable request and response builders."""

    transport = "http"
    protocol = "rest"

    def __init__(
        self,
        base_url: str,
        request_builder: Callable[[dict[str, Any]], HTTPRequestSpec],
        response_parser: Callable[[httpx.Response], dict[str, Any]],
        *,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = self.base_url
        self.request_builder = request_builder
        self.response_parser = response_parser
        self.client = client
        self.timeout = timeout
        self.default_headers = default_headers or {"user-agent": "openclaw-medical-harness/0.2.0"}

    def invoke(self, context: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        spec = self.request_builder(context, **kwargs)
        if spec.url.startswith("http"):
            url = spec.url
        elif spec.url:
            url = f"{self.base_url}/{spec.url.lstrip('/')}"
        else:
            url = self.base_url
        headers = {**self.default_headers, **spec.headers}
        if self.client is not None:
            response = self.client.request(
                spec.method,
                url,
                params=spec.params,
                json=spec.json_body,
                data=spec.data,
                headers=headers,
            )
            return self._parse_response(response)

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.request(
                spec.method,
                url,
                params=spec.params,
                json=spec.json_body,
                data=spec.data,
                headers=headers,
            )
            return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            raise ToolInvocationError(str(exc)) from exc
        return self.response_parser(response)


class GraphQLToolAdapter(HTTPToolAdapter):
    protocol = "graphql"
