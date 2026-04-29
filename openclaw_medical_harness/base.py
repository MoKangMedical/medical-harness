"""Shared Harness primitives."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HarnessStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class HarnessMetrics:
    execution_time_ms: float = 0.0
    tools_called: int = 0
    tools_succeeded: int = 0
    context_tokens_used: int = 0
    recovery_attempts: int = 0
    validation_score: float = 0.0


@dataclass
class HarnessResult:
    output: Any = None
    harness_name: str = ""
    status: HarnessStatus = HarnessStatus.SUCCESS
    confidence: float = 0.0
    metrics: HarnessMetrics = field(default_factory=HarnessMetrics)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    recovery_applied: bool = False
    tool_chain_results: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in {HarnessStatus.SUCCESS, HarnessStatus.RECOVERED}


@dataclass
class HarnessConfig:
    name: str
    model_provider: str = "mimo"
    tools: list[str] = field(default_factory=list)
    context_config: dict[str, Any] = field(default_factory=dict)
    recovery_strategy: str = "escalate"
    validation_threshold: float = 0.7
    max_retries: int = 2
    timeout_seconds: float = 30.0


class ToolBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @abstractmethod
    def execute(self, context: dict[str, Any], prior_results: dict[str, Any]) -> dict[str, Any]:
        ...


class ToolExecutionError(Exception):
    def __init__(self, tool_name: str, message: str, recoverable: bool = True) -> None:
        self.tool_name = tool_name
        self.recoverable = recoverable
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ModelProviderBase(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str: ...


class BaseHarness(ABC):
    """Pipeline wrapper shared by domain harnesses."""

    def __init__(
        self,
        config: HarnessConfig | None = None,
        name: str = "base",
        model_provider: str = "mimo",
        tools: list[str] | None = None,
        tool_registry: Any | None = None,
        **_: Any,
    ) -> None:
        if config is None:
            config = HarnessConfig(
                name=name,
                model_provider=model_provider,
                tools=tools or [],
            )
        self.config = config
        self.name = config.name
        self.model_provider = config.model_provider

        from .context import ContextManager
        from .mcp_tools import MedicalToolRegistry
        from .recovery import FailureRecovery
        from .validator import ResultValidator

        self.context = ContextManager(config.context_config)
        self.recovery = FailureRecovery(
            strategy=config.recovery_strategy,
            max_retries=config.max_retries,
        )
        self.validator = ResultValidator(config.validation_threshold)
        self._tool_registry: dict[str, Any] = {}
        self.registry = tool_registry or MedicalToolRegistry()
        for tool_name in config.tools:
            tool = self.registry.get(tool_name)
            if tool is not None:
                self.register_tool(tool_name, tool)

    def register_tool(self, name: str, tool: Any) -> None:
        self._tool_registry[name] = tool

    def execute(self, input_data: dict[str, Any]) -> HarnessResult:
        start = time.time()
        context = self.context.build(input_data)
        context = self.context.compress(context)
        tool_results = self._chain_tools(context)
        reasoning = self._reason(context, tool_results)
        validation = self.validator.validate(reasoning, context=context, domain=self._domain())

        recovery_applied = False
        if not validation.passed:
            reasoning = self.recovery.recover(context, validation, self._reason)
            recovery_applied = True
            validation = self.validator.validate(reasoning, context=context, domain=self._domain())

        elapsed_ms = (time.time() - start) * 1000
        status = HarnessStatus.SUCCESS if validation.passed else HarnessStatus.FAILED
        if recovery_applied and validation.passed:
            status = HarnessStatus.RECOVERED

        metrics = self._compute_metrics(
            context=context,
            tool_results=tool_results,
            elapsed_ms=elapsed_ms,
            validation_score=validation.confidence,
            recovery_attempts=int(recovery_applied),
        )
        return HarnessResult(
            output=reasoning,
            harness_name=self.name,
            status=status,
            confidence=validation.confidence,
            metrics=metrics,
            metadata={"domain": self._domain(), "model": self.model_provider},
            execution_time_ms=elapsed_ms,
            recovery_applied=recovery_applied,
            tool_chain_results=tool_results,
        )

    def _chain_tools(self, context: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for tool_name in self.config.tools:
            tool = self._tool_registry.get(tool_name)
            if tool is None:
                results[tool_name] = {"error": f"Tool '{tool_name}' not registered"}
                continue
            try:
                tool_context = self.context.merge(context, {"tools": results})
                params = self._tool_parameters(tool_name, tool_context, results)
                if params is None:
                    results[tool_name] = {
                        "tool": tool_name,
                        "status": "skipped",
                        "reason": "no applicable domain parameters",
                    }
                    continue
                results[tool_name] = tool.execute(tool_context, prior_results=results, **params)
            except Exception as exc:  # pragma: no cover - defensive
                results[tool_name] = {"error": str(exc), "tool": tool_name}
        return results

    def _reason(self, context: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(context, tool_results)
        return self._call_model(prompt)

    def _call_model(self, prompt: str) -> dict[str, Any]:
        return {"reasoning": prompt, "provider": self.model_provider, "confidence": 0.5}

    def _compute_metrics(
        self,
        context: dict[str, Any],
        tool_results: dict[str, Any],
        elapsed_ms: float,
        validation_score: float,
        recovery_attempts: int,
    ) -> HarnessMetrics:
        return HarnessMetrics(
            execution_time_ms=elapsed_ms,
            tools_called=len(self.config.tools),
            tools_succeeded=sum(
                1 for value in tool_results.values() if not isinstance(value, dict) or "error" not in value
            ),
            context_tokens_used=self.context.estimate_tokens(context),
            recovery_attempts=recovery_attempts,
            validation_score=validation_score,
        )

    @abstractmethod
    def _build_prompt(self, context: dict[str, Any], tool_results: dict[str, Any]) -> str:
        ...

    def _tool_parameters(
        self,
        tool_name: str,
        context: dict[str, Any],
        prior_results: dict[str, Any],
    ) -> dict[str, Any] | None:
        return {}

    @abstractmethod
    def _domain(self) -> str:
        ...
