"""Multi-agent orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OrchestratorMode(str, Enum):
    OPENCLAW = "openclaw"
    CREWAI = "crewai"


@dataclass
class AgentDefinition:
    name: str
    role: str
    specialty: str = ""
    tools: list[str] = field(default_factory=list)
    backstory: str = ""


@dataclass
class ConsensusResult:
    final_diagnosis: str
    confidence: float
    agent_opinions: dict[str, Any] = field(default_factory=dict)
    consensus_rounds: int = 0
    disagreements: list[str] = field(default_factory=list)


class MedicalOrchestrator:
    def __init__(self, mode: str | OrchestratorMode = "openclaw") -> None:
        self.mode = OrchestratorMode(mode)
        self.agents: dict[str, AgentDefinition] = {}

    def add_agent(
        self,
        name: str,
        role: str = "",
        specialty: str = "",
        tools: list[str] | None = None,
        backstory: str = "",
    ) -> None:
        self.agents[name] = AgentDefinition(
            name=name,
            role=role or name,
            specialty=specialty,
            tools=tools or [],
            backstory=backstory,
        )

    def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        consensus_rounds: int = 3,
    ) -> ConsensusResult:
        context = context or {}
        opinions = {name: self._agent_reason(agent, task, context) for name, agent in self.agents.items()}
        final = self._reach_consensus(opinions)
        return ConsensusResult(
            final_diagnosis=final.get("diagnosis", ""),
            confidence=final.get("confidence", 0.0),
            agent_opinions=opinions,
            consensus_rounds=consensus_rounds,
            disagreements=final.get("disagreements", []),
        )

    def _agent_reason(self, agent: AgentDefinition, task: str, context: dict[str, Any]) -> dict[str, Any]:
        symptoms = context.get("symptoms", [])
        if "diagnos" in agent.name or "diagnos" in agent.role:
            opinion = f"[{agent.role}] 基于症状 {', '.join(symptoms) or task} 的鉴别分析"
            confidence = 0.78
        elif "literature" in agent.name:
            opinion = f"[{agent.role}] 文献支持该方向需要进一步验证"
            confidence = 0.66
        elif "pharmac" in agent.name:
            opinion = f"[{agent.role}] 从药理角度暂无明显冲突"
            confidence = 0.62
        else:
            opinion = f"[{agent.role}] 针对任务 '{task}' 的专业判断"
            confidence = 0.7
        return {
            "agent": agent.name,
            "role": agent.role,
            "opinion": opinion,
            "confidence": confidence,
            "evidence": context,
        }

    def _reach_consensus(self, opinions: dict[str, Any]) -> dict[str, Any]:
        if not opinions:
            return {"diagnosis": "", "confidence": 0.0, "disagreements": []}
        ranked = sorted(opinions.values(), key=lambda item: item.get("confidence", 0.0), reverse=True)
        top = ranked[0]
        disagreements = [f"{item['agent']}: {item['opinion']}" for item in ranked[1:] if item["confidence"] > 0.5]
        return {
            "diagnosis": top["opinion"],
            "confidence": top["confidence"],
            "disagreements": disagreements,
        }
