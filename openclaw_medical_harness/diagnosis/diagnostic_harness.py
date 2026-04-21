"""Diagnosis harness implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..base import BaseHarness, HarnessConfig
from ..env import getenv
from ..recovery import RecoveryStrategy


RARE_DISEASE_KB: dict[str, dict[str, Any]] = {
    "MG": {
        "name": "重症肌无力 / Myasthenia Gravis",
        "key_symptoms": ["ptosis", "diplopia", "fatigable weakness", "bilateral ptosis"],
        "diagnostic_tests": ["AChR antibody", "MuSK antibody", "EMG", "CT chest (thymoma)"],
        "differential": ["Lambert-Eaton", "botulism", "CPEO", "thyroid eye disease"],
    },
    "SMA": {
        "name": "脊髓性肌萎缩症 / Spinal Muscular Atrophy",
        "key_symptoms": ["muscle weakness", "hypotonia", "areflexia", "fasciculations"],
        "diagnostic_tests": ["SMN1 gene test", "SMN2 copy number", "EMG/NCS", "CK"],
        "differential": ["DMD", "ALS", "Pompe disease", "CIDP"],
    },
    "DMD": {
        "name": "杜氏肌营养不良 / Duchenne Muscular Dystrophy",
        "key_symptoms": ["progressive weakness", "calf pseudohypertrophy", "gowers sign"],
        "diagnostic_tests": ["DMD gene test", "CK level", "muscle biopsy", "EMG"],
        "differential": ["Becker MD", "SMA", "LGMD", "inflammatory myopathy"],
    },
}

RED_FLAG_PATTERNS = {
    "chest pain": "Possible cardiac event — consider ACS workup",
    "sudden severe headache": "Possible subarachnoid hemorrhage",
    "shortness of breath at rest": "Respiratory emergency evaluation needed",
    "loss of consciousness": "Neurological emergency",
}

COMMON_PRESENTATION_PATHWAYS: list[dict[str, Any]] = [
    {
        "code": "ACS",
        "name": "急性冠脉综合征 / Acute Coronary Syndrome",
        "keywords": ["chest pain", "left arm", "diaphoresis", "sweating", "nausea", "pressure"],
        "diagnostic_tests": ["ECG", "Troponin", "Chest X-ray", "Coronary risk assessment"],
        "differential": ["Pulmonary embolism", "Aortic dissection", "Pericarditis", "GERD"],
        "base_score": 0.62,
    },
    {
        "code": "SAH",
        "name": "蛛网膜下腔出血 / Subarachnoid Hemorrhage",
        "keywords": ["sudden severe headache", "thunderclap headache", "neck stiffness", "vomiting"],
        "diagnostic_tests": ["Non-contrast head CT", "Lumbar puncture", "CTA/MRA"],
        "differential": ["Migraine", "Meningitis", "Intracerebral hemorrhage", "RCVS"],
        "base_score": 0.64,
    },
    {
        "code": "PE",
        "name": "肺栓塞 / Pulmonary Embolism",
        "keywords": ["shortness of breath", "pleuritic chest pain", "tachycardia", "hypoxia", "hemoptysis"],
        "diagnostic_tests": ["D-dimer", "CTPA", "Arterial blood gas", "Lower-limb ultrasound"],
        "differential": ["Pneumonia", "ACS", "Pneumothorax", "Heart failure"],
        "base_score": 0.6,
    },
    {
        "code": "DKA",
        "name": "糖尿病酮症酸中毒 / Diabetic Ketoacidosis",
        "keywords": ["polyuria", "polydipsia", "vomiting", "abdominal pain", "fruity breath", "fatigue"],
        "diagnostic_tests": ["Blood glucose", "Ketones", "Blood gas", "Electrolytes"],
        "differential": ["Hyperosmolar hyperglycemic state", "Sepsis", "Gastroenteritis", "Toxic ingestion"],
        "base_score": 0.58,
    },
]


@dataclass
class DifferentialDiagnosis:
    condition: str = ""
    probability: float = 0.0
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    recommended_tests: list[str] = field(default_factory=list)
    icd10_code: str = ""


@dataclass
class DiagnosticResult:
    primary_diagnosis: str = "Undetermined"
    confidence: float = 0.0
    differential_list: list[DifferentialDiagnosis] = field(default_factory=list)
    recommended_tests: list[str] = field(default_factory=list)
    urgency_level: str = "routine"
    specialist_referral: str = ""
    reasoning_chain: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DiagnosisHarness(BaseHarness):
    def __init__(
        self,
        model_provider: str = "mimo",
        specialty: str = "neurology",
        knowledge_base: dict[str, Any] | None = None,
        name: str = "",
        config: HarnessConfig | None = None,
        **kwargs: Any,
    ) -> None:
        if config is None:
            config = HarnessConfig(
                name=name or f"diagnosis_{specialty}",
                model_provider=model_provider,
                tools=["pubmed", "omim", "opentargets"],
                recovery_strategy=RecoveryStrategy.ESCALATE.value,
                validation_threshold=0.7,
            )
        super().__init__(config=config, **kwargs)
        self.specialty = specialty
        self.kb = knowledge_base or RARE_DISEASE_KB

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        symptoms = input_data.get("symptoms", [])
        if symptoms:
            input_data.setdefault("patient", {})
            input_data["patient"]["symptoms"] = symptoms
            input_data["patient"].setdefault("chief_complaint", symptoms[0])
        result = super().execute(input_data)
        output = result.output if isinstance(result.output, dict) else {"diagnosis": str(result.output)}
        return {
            "diagnosis": output.get("diagnosis", "无法确定"),
            "confidence": output.get("confidence", result.confidence),
            "differential": output.get("differential", []),
            "next_steps": output.get("next_steps", []),
            "evidence": output.get("evidence", {}),
            "red_flags": output.get("red_flags", []),
            "harness_name": result.harness_name,
            "execution_time_ms": result.execution_time_ms,
            "recovery_applied": result.recovery_applied,
        }

    def _build_prompt(self, context: dict[str, Any], tool_results: dict[str, Any]) -> str:
        patient = context.get("patient", {})
        symptoms = patient.get("symptoms", [])
        specialty = self._specialty_from_context(context)
        lines = [
            f"你是一位 {specialty} 专科医生。",
            f"年龄: {patient.get('age', '未知')}",
            f"性别: {patient.get('sex', '未知')}",
            "症状:",
            *[f"- {symptom}" for symptom in symptoms],
        ]
        if tool_results:
            lines.append("工具结果:")
            lines.extend(f"- {name}: {value}" for name, value in tool_results.items())
        lines.append("请输出诊断、置信度、鉴别诊断、下一步检查和关键依据。")
        return "\n".join(lines)

    def _reason(self, context: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        patient = context.get("patient", {})
        symptoms = self._normalize_symptoms(patient)
        candidates = self._rank_candidates(patient)
        red_flags = self._extract_red_flags(symptoms)

        if not candidates:
            return {
                "diagnosis": "需要进一步评估",
                "confidence": 0.3,
                "differential": ["详细病史采集", "体格检查", "实验室检查"],
                "next_steps": ["详细病史采集", "体格检查", "实验室检查"],
                "evidence": {"knowledge_base_match": False, "tool_results": tool_results},
                "red_flags": red_flags,
            }

        top = candidates[0]
        pubmed_hits = int(tool_results.get("pubmed", {}).get("count", 0) or 0)
        omim_entries = len(tool_results.get("omim", {}).get("entries", []) or [])
        target_hits = int(tool_results.get("opentargets", {}).get("total", 0) or 0)
        confidence = min(top["score"] + 0.18 + min(pubmed_hits / 50, 0.08) + min(omim_entries * 0.02, 0.06), 0.95)
        differentials = list(top["differential"])
        for candidate in candidates[1:]:
            if candidate["name"] not in differentials:
                differentials.append(candidate["name"])
        return {
            "diagnosis": top["name"],
            "confidence": confidence,
            "differential": differentials[:4],
            "next_steps": top["tests"],
            "evidence": {
                "knowledge_base_match": True,
                "matched_candidates": len(candidates),
                "support_signals": {
                    "pubmed_hits": pubmed_hits,
                    "omim_entries": omim_entries,
                    "opentargets_hits": target_hits,
                },
                "tool_results": tool_results,
            },
            "red_flags": red_flags,
        }

    def _tool_parameters(
        self,
        tool_name: str,
        context: dict[str, Any],
        prior_results: dict[str, Any],
    ) -> dict[str, Any] | None:
        patient = context.get("patient", {})
        symptoms = self._normalize_symptoms(patient)
        candidates = self._rank_candidates(patient)
        top = candidates[0] if candidates else None
        top_name = self._candidate_query_name(top) if top else ""
        symptom_query = ", ".join(str(symptom) for symptom in patient.get("symptoms", [])[:4])
        chief_complaint = str(patient.get("chief_complaint", "")).strip()
        specialty = self._specialty_from_context(context)

        if tool_name == "pubmed":
            focus = top_name or chief_complaint or symptom_query
            query = " ".join(part for part in [specialty, "differential diagnosis", focus, symptom_query] if part).strip()
            return {"query": query, "max_results": 5, "sort": "relevance"} if query else None

        if tool_name == "omim":
            api_key = getenv("OMIM_API_KEY")
            if not api_key or not top_name or (top and top.get("source") != "rare_disease_kb"):
                return None
            return {"search": top_name, "api_key": api_key}

        if tool_name == "opentargets":
            focus = top_name or chief_complaint
            query = " ".join(part for part in [focus, specialty, chief_complaint] if part).strip()
            if not query and symptom_query:
                query = f"{specialty} {symptom_query}"
            return {"query": query} if query else None

        return super()._tool_parameters(tool_name, context, prior_results)

    def _domain(self) -> str:
        return "diagnosis"

    def request_multidisciplinary_consult(self, specialists: list[str], context: dict[str, Any]) -> dict[str, Any]:
        return {name: {"status": "pending", "specialist_type": name, "context": context} for name in specialists}

    def query_rare_disease_kb(
        self,
        symptoms: list[str],
        genetic_markers: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        markers = [marker.lower() for marker in (genetic_markers or [])]
        symptom_text = [symptom.lower() for symptom in symptoms]
        results = []
        for code, info in self.kb.items():
            score = sum(1 for key in info["key_symptoms"] if any(key.lower() in symptom for symptom in symptom_text))
            if markers and any(marker in code.lower() for marker in markers):
                score += 1
            if score:
                results.append({"code": code, "name": info["name"], "match_score": score})
        return sorted(results, key=lambda item: item["match_score"], reverse=True)

    def _rank_candidates(self, patient: dict[str, Any]) -> list[dict[str, Any]]:
        symptoms = self._normalize_symptoms(patient)
        candidates: list[dict[str, Any]] = []
        for disease_code, disease_info in self.kb.items():
            score = sum(
                1
                for key_symptom in disease_info["key_symptoms"]
                if any(key_symptom.lower() in symptom for symptom in symptoms)
            )
            if score:
                candidates.append(
                    {
                        "code": disease_code,
                        "name": disease_info["name"],
                        "score": score / len(disease_info["key_symptoms"]),
                        "tests": disease_info["diagnostic_tests"],
                        "differential": disease_info["differential"],
                        "source": "rare_disease_kb",
                    }
                )
        candidates.extend(self._presentation_candidates(symptoms))
        deduped: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            existing = deduped.get(candidate["name"])
            if existing is None or candidate["score"] > existing["score"]:
                deduped[candidate["name"]] = candidate
        return sorted(deduped.values(), key=lambda item: item["score"], reverse=True)

    @staticmethod
    def _candidate_query_name(candidate: dict[str, Any]) -> str:
        if not candidate:
            return ""
        parts = [part.strip() for part in str(candidate["name"]).split("/") if part.strip()]
        return parts[-1] if parts else str(candidate["name"])

    @staticmethod
    def _normalize_symptoms(patient: dict[str, Any]) -> list[str]:
        symptoms = [str(symptom).lower() for symptom in patient.get("symptoms", []) if str(symptom).strip()]
        chief_complaint = str(patient.get("chief_complaint", "")).lower().strip()
        if chief_complaint:
            symptoms.append(chief_complaint)
        return list(dict.fromkeys(symptoms))

    @staticmethod
    def _presentation_candidates(symptoms: list[str]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for pathway in COMMON_PRESENTATION_PATHWAYS:
            keyword_hits = sum(1 for keyword in pathway["keywords"] if any(keyword in symptom for symptom in symptoms))
            if keyword_hits == 0:
                continue
            score = min(pathway["base_score"] + 0.05 * max(keyword_hits - 1, 0), 0.86)
            candidates.append(
                {
                    "code": pathway["code"],
                    "name": pathway["name"],
                    "score": score,
                    "tests": list(pathway["diagnostic_tests"]),
                    "differential": list(pathway["differential"]),
                    "source": "presentation_pathway",
                }
            )
        return candidates

    def _specialty_from_context(self, context: dict[str, Any]) -> str:
        return str(context.get("meta", {}).get("specialty", self.specialty) or self.specialty)

    @staticmethod
    def _extract_red_flags(symptoms: list[str]) -> list[str]:
        findings: list[str] = []
        for symptom in symptoms:
            for pattern, message in RED_FLAG_PATTERNS.items():
                if pattern in symptom:
                    findings.append(message)
        return list(dict.fromkeys(findings))
