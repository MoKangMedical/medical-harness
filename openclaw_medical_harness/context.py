"""Context shaping for harness execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CompressionStrategy(str, Enum):
    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    HIERARCHICAL = "hierarchical"
    MEDICAL_PRIORITIZED = "medical_prioritized"


@dataclass
class HarnessContext:
    patient_data: dict[str, Any] = field(default_factory=dict)
    clinical_history: list[dict[str, Any]] = field(default_factory=list)
    tool_outputs: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_compact(self) -> dict[str, Any]:
        return {
            "patient": self._summarize_patient(),
            "history": self._summarize_history(),
            "tools": self._summarize_tools(),
            "meta": self.metadata,
        }

    def _summarize_patient(self) -> dict[str, Any]:
        return dict(self.patient_data)

    def _summarize_history(self) -> list[str]:
        return [f"{item.get('date', '?')}: {item.get('event', '?')}" for item in self.clinical_history[-10:]]

    def _summarize_tools(self) -> dict[str, Any]:
        return {
            name: value.get("findings", value)
            for name, value in self.tool_outputs.items()
            if not isinstance(value, dict) or "error" not in value
        }


class ContextManager:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.max_history = self.config.get("max_history", 20)
        self.max_tokens = self.config.get("max_tokens", 8192)
        self.compression = self.config.get("compression", CompressionStrategy.MEDICAL_PRIORITIZED.value)

    def build(self, input_data: dict[str, Any]) -> dict[str, Any]:
        ctx = HarnessContext()
        ctx.patient_data = dict(input_data.get("patient", {}))

        for key in [
            "age",
            "sex",
            "symptoms",
            "chief_complaint",
            "disease",
            "target",
            "genetic_markers",
            "conditions",
            "medications",
            "lab_results",
            "wearable_data",
            "health_goal",
            "smiles",
            "screening_library",
            "max_compounds",
        ]:
            if key in input_data and key not in ctx.patient_data:
                ctx.patient_data[key] = input_data[key]

        if "history" in input_data:
            ctx.clinical_history.extend(input_data["history"])
        if "medical_history" in input_data:
            for item in input_data["medical_history"]:
                ctx.clinical_history.append(item if isinstance(item, dict) else {"event": item})

        ctx.metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "specialty": input_data.get("specialty", "general"),
            "urgency": input_data.get("urgency", "routine"),
            "language": input_data.get("language", "zh"),
            "compression_strategy": self.compression,
        }
        return ctx.to_compact()

    def compress(self, context: dict[str, Any]) -> dict[str, Any]:
        if self.estimate_tokens(context) <= self.max_tokens:
            return context
        strategy = self.compression
        if strategy == CompressionStrategy.TRUNCATE.value:
            return self._compress_truncate(context)
        if strategy == CompressionStrategy.SUMMARIZE.value:
            return self._compress_summarize(context)
        if strategy == CompressionStrategy.HIERARCHICAL.value:
            return self._compress_hierarchical(context)
        return self._compress_medical_prioritized(context)

    def merge(self, base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in new.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            elif isinstance(merged.get(key), list) and isinstance(value, list):
                merged[key] = (merged[key] + value)[-self.max_history :]
            else:
                merged[key] = value
        return merged

    def _compress_truncate(self, context: dict[str, Any]) -> dict[str, Any]:
        compressed = dict(context)
        compressed["history"] = compressed.get("history", [])[-2:]
        compressed["_compressed"] = True
        compressed["_strategy"] = CompressionStrategy.TRUNCATE.value
        return compressed

    def _compress_summarize(self, context: dict[str, Any]) -> dict[str, Any]:
        compressed = dict(context)
        history = compressed.get("history", [])
        if history:
            compressed["history_summary"] = f"{len(history)} prior events"
            compressed["history"] = history[-1:]
        compressed["_compressed"] = True
        compressed["_strategy"] = CompressionStrategy.SUMMARIZE.value
        return compressed

    def _compress_hierarchical(self, context: dict[str, Any]) -> dict[str, Any]:
        compressed = dict(context)
        for key, value in list(compressed.items()):
            if key in {"patient", "meta"}:
                continue
            if isinstance(value, dict):
                compressed[key] = {inner_key: type(inner_value).__name__ for inner_key, inner_value in value.items()}
        compressed["_compressed"] = True
        compressed["_strategy"] = CompressionStrategy.HIERARCHICAL.value
        return compressed

    def _compress_medical_prioritized(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "patient": context.get("patient", {}),
            "meta": context.get("meta", {}),
            "history": context.get("history", [])[-2:],
            "tools": context.get("tools", {}),
            "_compressed": True,
            "_strategy": CompressionStrategy.MEDICAL_PRIORITIZED.value,
        }

    @staticmethod
    def estimate_tokens(context: dict[str, Any]) -> int:
        return len(json.dumps(context, default=str)) // 4
