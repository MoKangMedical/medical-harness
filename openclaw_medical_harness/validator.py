"""Validation rules for harness outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationFinding:
    severity: ValidationSeverity = ValidationSeverity.INFO
    field: str = ""
    message: str = ""
    suggestion: str = ""


@dataclass
class ValidationResult:
    passed: bool = True
    confidence: float = 1.0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[ValidationFinding] = field(default_factory=list)
    message: str = "Validation passed"
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


HIGH_RISK_KEYWORDS = [
    "恶性",
    "癌症",
    "肿瘤",
    "acute",
    "critical",
    "emergency",
    "心肌梗死",
    "脑卒中",
    "肺栓塞",
]
ABSOLUTE_TERMS = ["肯定", "一定", "100%", "绝对", "definitely", "certainly", "absolutely"]
DANGEROUS_PATTERNS = [
    (r"no need for (further )?testing", "跳过检测的建议需要审查"),
    (r"definitely (not )?cancer", "没有病理支持的绝对癌症表述不安全"),
    (r"stop all medications", "在无监督下停用全部药物不安全"),
]
DOMAIN_REQUIRED_FIELDS = {
    "diagnosis": ["diagnosis", "confidence"],
    "drug_discovery": ["target", "candidates", "confidence"],
    "health_management": ["assessment", "plan", "confidence"],
}


class ResultValidator:
    def __init__(
        self,
        threshold: float = 0.7,
        strict_mode: bool = False,
        domain_rules: dict[str, Any] | None = None,
    ) -> None:
        self.threshold = threshold
        self.strict_mode = strict_mode
        self.domain_rules = domain_rules or {}

    def validate(
        self,
        result: Any,
        context: dict[str, Any] | None = None,
        domain: str = "general",
    ) -> ValidationResult:
        normalized = self._normalize_output(result)
        issues: list[str] = []
        warnings: list[str] = []
        findings: list[ValidationFinding] = []

        issues.extend(self._validate_format(normalized, domain))

        confidence = normalized.get("confidence", 0.0)
        if "confidence" in normalized and not isinstance(confidence, (int, float)):
            issues.append("'confidence' 必须是数值类型")
        elif isinstance(confidence, (int, float)):
            if not 0.0 <= confidence <= 1.0:
                issues.append(f"置信度 {confidence} 超出有效范围 [0, 1]")
            if confidence < self.threshold:
                issues.append(f"置信度 {confidence:.2f} 低于阈值 {self.threshold}")

        issues.extend(self._validate_safety(normalized))
        if context:
            warnings.extend(self._validate_consistency(normalized, context))
        warnings.extend(self._validate_high_risk(normalized))
        findings.extend(self._validate_domain(normalized, domain))

        if self.strict_mode:
            warning_findings = [finding for finding in findings if finding.severity == ValidationSeverity.WARNING]
            if warnings or warning_findings:
                issues.append("strict mode blocked warning-level output")

        score = self._calculate_score(findings, issues)
        passed = not issues
        message = f"Validation passed (score: {score:.2f})" if passed else f"Validation failed — {len(issues)} issue(s)"
        return ValidationResult(
            passed=passed,
            confidence=confidence if isinstance(confidence, (int, float)) else 0.0,
            issues=issues,
            warnings=warnings,
            findings=findings,
            message=message,
            metadata={"domain": domain, "strict_mode": self.strict_mode, "score": score},
        )

    def _normalize_output(self, output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            return output
        if isinstance(output, str):
            return {"raw_output": output}
        if hasattr(output, "output"):
            return self._normalize_output(output.output)
        if hasattr(output, "__dict__"):
            return {key: value for key, value in output.__dict__.items() if not key.startswith("_")}
        return {"raw_output": str(output)}

    def _validate_format(self, result: dict[str, Any], domain: str) -> list[str]:
        if not result:
            return ["输出为空"]
        issues: list[str] = []
        required = DOMAIN_REQUIRED_FIELDS.get(domain, [])
        for field_name in required:
            if field_name not in result:
                issues.append(f"缺少领域必需字段: {field_name}")
        if domain == "general":
            core_fields = {"diagnosis", "assessment", "target", "raw_output", "output"}
            if not core_fields.intersection(result):
                issues.append(f"输出缺少核心字段（{'/'.join(sorted(core_fields))} 之一）")
        return issues

    def _validate_safety(self, result: dict[str, Any]) -> list[str]:
        text = str(result)
        issues: list[str] = []
        for term in ABSOLUTE_TERMS:
            if term in text:
                issues.append(f"包含禁止的绝对性表述: '{term}'")
        for pattern, message in DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"检测到危险模式: {message}")
        return issues

    def _validate_consistency(self, result: dict[str, Any], context: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        patient = context.get("patient", {})
        diagnosis = str(result.get("diagnosis", "")).lower()
        age = patient.get("age")
        if isinstance(age, (int, float)) and age < 18:
            adult_only = ["coronary", "parkinson", "冠心病", "帕金森"]
            if any(term in diagnosis for term in adult_only):
                warnings.append(f"诊断 '{diagnosis}' 在 {age} 岁患者中并不常见")
        return warnings

    def _validate_high_risk(self, result: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        text = str(result).lower()
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword.lower() in text:
                if "differential" not in text and "鉴别" not in text:
                    warnings.append(f"高风险诊断 '{keyword}' 缺少鉴别诊断列表")
                break
        return warnings

    def _validate_domain(self, result: dict[str, Any], domain: str) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        if domain == "diagnosis":
            differential = result.get("differential", result.get("differential_list", []))
            if isinstance(differential, list) and len(differential) < 2:
                findings.append(
                    ValidationFinding(
                        severity=ValidationSeverity.WARNING,
                        field="differential",
                        message="鉴别诊断列表少于 2 个备选项",
                    )
                )
        return findings

    def _calculate_score(self, findings: list[ValidationFinding], issues: list[str]) -> float:
        penalties = {
            ValidationSeverity.INFO: 0.0,
            ValidationSeverity.WARNING: 0.1,
            ValidationSeverity.ERROR: 0.25,
            ValidationSeverity.CRITICAL: 0.5,
        }
        total = sum(penalties[finding.severity] for finding in findings)
        total += len(issues) * 0.15
        return max(0.0, 1.0 - total)
