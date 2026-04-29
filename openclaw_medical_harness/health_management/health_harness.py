"""Health management harness implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..base import BaseHarness, HarnessConfig
from ..recovery import RecoveryStrategy


@dataclass
class HealthAssessment:
    risk_scores: dict[str, float] = field(default_factory=dict)
    lifestyle_factors: list[str] = field(default_factory=list)
    biomarkers: dict[str, dict[str, Any]] = field(default_factory=dict)
    mental_health_screen: dict[str, Any] = field(default_factory=dict)
    overall_risk_level: str = "moderate"


@dataclass
class CarePlanItem:
    category: str = ""
    description: str = ""
    frequency: str = ""
    duration: str = ""
    priority: str = "recommended"
    evidence_level: str = "B"


@dataclass
class HealthPlan:
    plan_items: list[CarePlanItem] = field(default_factory=list)
    goals: list[dict[str, Any]] = field(default_factory=list)
    follow_up_schedule: list[dict[str, str]] = field(default_factory=list)
    compliance_tracking: dict[str, Any] = field(default_factory=dict)
    escalation_triggers: list[str] = field(default_factory=list)


class HealthManagementHarness(BaseHarness):
    def __init__(
        self,
        model_provider: str = "mimo",
        health_domain: str = "general",
        follow_up_interval_days: int = 30,
        name: str = "",
        config: HarnessConfig | None = None,
        **kwargs: Any,
    ) -> None:
        if config is None:
            config = HarnessConfig(
                name=name or f"health_{health_domain}",
                model_provider=model_provider,
                tools=["pubmed", "openfda"],
                recovery_strategy=RecoveryStrategy.FALLBACK.value,
                validation_threshold=0.6,
            )
        super().__init__(config=config, **kwargs)
        self.health_domain = health_domain
        self.follow_up_interval_days = follow_up_interval_days

    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data.setdefault("patient", {})
        for key in ["conditions", "lab_results", "wearable_data", "health_goal", "age", "medications"]:
            if key in input_data and key not in input_data["patient"]:
                input_data["patient"][key] = input_data[key]
        result = super().execute(input_data)
        output = result.output if isinstance(result.output, dict) else {}
        return {
            "assessment": output.get("assessment", {}),
            "plan": output.get("plan", {}),
            "adherence_metrics": output.get("adherence", {}),
            "effectiveness": output.get("effectiveness", {}),
            "confidence": output.get("confidence", result.confidence),
            "harness_name": result.harness_name,
            "execution_time_ms": result.execution_time_ms,
        }

    def _build_prompt(self, context: dict[str, Any], tool_results: dict[str, Any]) -> str:
        patient = context.get("patient", {})
        return "\n".join(
            [
                f"你是一位 {self.health_domain} 方向 AI 健康管理专家。",
                f"年龄: {patient.get('age', '未知')}",
                f"健康目标: {patient.get('health_goal', 'general wellness')}",
                f"现有疾病: {patient.get('conditions', [])}",
                f"工具结果: {tool_results}",
                "请输出评估、干预计划、依从性跟踪和效果评估。",
            ]
        )

    def _reason(self, context: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        patient = context.get("patient", {})
        conditions = patient.get("conditions", [])
        medications = patient.get("medications", [])
        key_findings = []
        if patient.get("lab_results", {}).get("hba1c", 0) >= 7:
            key_findings.append("血糖控制未达标")
        if not key_findings:
            key_findings.extend(["BMI 偏高", "运动不足"])
        pubmed_hits = int(tool_results.get("pubmed", {}).get("count", 0) or 0)
        openfda_results = tool_results.get("openfda", {}).get("results", []) or []
        monitoring_plan = "每周记录体重、步数和关键指标"
        if medications and openfda_results:
            monitoring_plan = f"每周记录核心指标，并复核 {medications[0]} 的安全提示与标签更新"
        diet_plan = "以地中海饮食或高纤维控糖饮食为主"
        if any("diabetes" in str(condition).lower() for condition in conditions):
            diet_plan = "优先控糖饮食、固定碳水分配，并结合 HbA1c 目标追踪"
        elif any("hypertension" in str(condition).lower() for condition in conditions):
            diet_plan = "优先限盐 DASH 饮食，并结合家庭血压监测"
        return {
            "assessment": {
                "overall_risk": "moderate",
                "key_findings": key_findings,
                "conditions": conditions,
                "evidence_strength": "moderate" if pubmed_hits else "limited",
            },
            "plan": {
                "diet": diet_plan,
                "exercise": "每周 150 分钟中等强度运动",
                "monitoring": monitoring_plan,
            },
            "adherence": {
                "tracking_metrics": ["体重", "运动时长", "饮食日志"],
                "check_interval_days": 7,
            },
            "effectiveness": {
                "evaluation_points": ["2周", "1月", "3月"],
                "success_criteria": "核心指标改善并维持依从性",
            },
            "confidence": min(0.62 + (0.06 if pubmed_hits else 0.0) + (0.04 if openfda_results else 0.0), 0.85),
            "evidence": tool_results,
        }

    def _tool_parameters(
        self,
        tool_name: str,
        context: dict[str, Any],
        prior_results: dict[str, Any],
    ) -> dict[str, Any] | None:
        patient = context.get("patient", {})
        conditions = patient.get("conditions", [])
        medications = patient.get("medications", [])
        goal = patient.get("health_goal", "")

        if tool_name == "pubmed":
            query = " ".join(
                part
                for part in [
                    conditions[0] if conditions else "",
                    goal,
                    "guideline lifestyle management adherence",
                ]
                if part
            ).strip()
            return {"query": query, "max_results": 5} if query else None

        if tool_name == "openfda":
            if medications:
                return {"dataset": "drug/label.json", "search": medications[0], "limit": 3}
            return None

        return super()._tool_parameters(tool_name, context, prior_results)

    def _domain(self) -> str:
        return "health_management"

    def conduct_follow_up(self, patient_id: str, current_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "patient_id": patient_id,
            "compliance_rate": 0.75,
            "outcome_changes": current_data,
            "plan_adjustments": [],
            "alerts": [],
        }
