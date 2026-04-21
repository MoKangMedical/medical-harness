"""Recovery strategies for failed harness outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class RecoveryStrategy(str, Enum):
    ESCALATE = "escalate"
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE_GRACEFULLY = "degrade_gracefully"
    ABORT = "abort"


class EscalationLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RecoveryResult:
    recovered: bool = False
    strategy_used: RecoveryStrategy = RecoveryStrategy.RETRY
    validation: Any = None
    message: str = ""
    requires_human: bool = False


@dataclass
class EscalationEvent:
    level: EscalationLevel
    source: str
    reason: str
    context_snapshot: dict[str, Any]
    resolution: str = "pending"


class FailureRecovery:
    def __init__(
        self,
        strategy: RecoveryStrategy | str = RecoveryStrategy.ESCALATE,
        max_retries: int = 2,
        escalation_threshold: int = 3,
    ) -> None:
        self.strategy = RecoveryStrategy(strategy)
        self.max_retries = max_retries
        self.escalation_threshold = escalation_threshold
        self._failure_count = 0
        self._escalation_log: list[EscalationEvent] = []
        self._recovery_log: list[dict[str, Any]] = []

    def recover(
        self,
        context: dict[str, Any],
        validation: Any,
        reason_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._failure_count += 1
        severity = self._assess_severity(validation)
        self._recovery_log.append(
            {
                "strategy": self.strategy.value,
                "severity": severity.value,
                "issues": list(getattr(validation, "issues", [])),
                "confidence": getattr(validation, "confidence", 0.0),
            }
        )
        event = EscalationEvent(
            level=severity,
            source="validation",
            reason=getattr(validation, "message", "validation failed"),
            context_snapshot=self._safe_context_snapshot(context),
        )

        if severity == EscalationLevel.CRITICAL:
            event.resolution = "escalated_to_human"
            self._escalation_log.append(event)
            return {
                "diagnosis": "无法确定 — 需要人工专家审核",
                "confidence": 0.0,
                "method": "escalate_to_human",
                "issues": list(getattr(validation, "issues", [])),
                "recommendation": "请补充关键临床信息并联系专科医生",
            }

        if severity == EscalationLevel.HIGH:
            event.resolution = "degraded_gracefully"
            self._escalation_log.append(event)
            return self._degrade_gracefully(validation)

        if severity == EscalationLevel.MEDIUM and reason_fn is not None and self._failure_count <= self.max_retries:
            event.resolution = "retry_attempted"
            self._escalation_log.append(event)
            enhanced_context = {
                **context,
                "_recovery": {
                    "attempt": self._failure_count,
                    "issues": list(getattr(validation, "issues", [])),
                    "constraint": "请明确给出置信度与鉴别诊断，避免绝对化表述。",
                },
            }
            return reason_fn(enhanced_context, {})

        event.resolution = "fallback"
        self._escalation_log.append(event)
        return self._fallback(validation)

    def _assess_severity(self, validation: Any) -> EscalationLevel:
        score = getattr(validation, "confidence", 0.5)
        if score < 0.2:
            return EscalationLevel.CRITICAL
        if score < 0.4:
            return EscalationLevel.HIGH
        if score < 0.6:
            return EscalationLevel.MEDIUM
        return EscalationLevel.LOW

    def _degrade_gracefully(self, validation: Any) -> dict[str, Any]:
        return {
            "diagnosis": "需要进一步检查（部分结果）",
            "confidence": 0.3,
            "method": "degraded_gracefully",
            "issues": list(getattr(validation, "issues", [])),
            "recommendation": "建议追加检查或升级人工会诊",
            "degraded": True,
        }

    def _fallback(self, validation: Any) -> dict[str, Any]:
        return {
            "diagnosis": "需要进一步检查",
            "confidence": 0.3,
            "method": "rule_based_fallback",
            "issues": list(getattr(validation, "issues", [])),
            "recommendation": "建议人工会诊",
        }

    @staticmethod
    def _safe_context_snapshot(context: dict[str, Any]) -> dict[str, Any]:
        return {
            "specialty": context.get("meta", {}).get("specialty", "unknown"),
            "patient_keys": sorted(context.get("patient", {}).keys()),
            "has_history": bool(context.get("history")),
        }

    @property
    def escalation_log(self) -> list[EscalationEvent]:
        return list(self._escalation_log)

    @property
    def recovery_log(self) -> list[dict[str, Any]]:
        return list(self._recovery_log)

    def reset(self) -> None:
        self._failure_count = 0
