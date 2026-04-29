"""FastAPI demo server for OpenClaw Medical Harness."""

from __future__ import annotations

import time
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        'FastAPI and Pydantic are required for the demo server. Install with: pip install "openclaw-medical-harness[server]"'
    ) from exc

from openclaw_medical_harness import (
    DiagnosisHarness,
    DrugDiscoveryHarness,
    HealthManagementHarness,
    MedicalToolRegistry,
    MimoMediaClient,
    OpenArenaClient,
    OpenArenaProjectSubmission,
    __version__,
)
from openclaw_medical_harness.demo_page import render_demo_page


class PatientInfo(BaseModel):
    age: int | None = None
    sex: str | None = None
    medical_history: list[str] = Field(default_factory=list)


class DiagnoseRequest(BaseModel):
    symptoms: list[str] = Field(..., min_length=1)
    patient: PatientInfo | None = None
    specialty: str = "neurology"
    language: str = "zh"


class DrugDiscoveryRequest(BaseModel):
    target: str
    disease: str
    max_compounds: int = Field(default=100, ge=1, le=1000)


class HealthRequest(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    health_goal: str = "general wellness"
    lab_results: dict[str, Any] = Field(default_factory=dict)
    wearable_data: dict[str, Any] = Field(default_factory=dict)
    age: int | None = None


class OpenArenaRequest(BaseModel):
    x_post_url: str = ""
    project_name: str = "OpenClaw-Medical-Harness"
    github_repo_url: str = "https://github.com/MoKangMedical/openclaw-medical-harness"
    project_website_url: str = ""
    team_contact: str = ""
    submitter_name: str = ""
    submitter_contact: str = ""
    submitter_payout_address: str = ""
    ranking_reason: str = ""
    team_aware: bool = True
    additional_notes: str = ""

    def to_submission(self) -> OpenArenaProjectSubmission:
        return OpenArenaProjectSubmission(
            x_post_url=self.x_post_url,
            project_name=self.project_name,
            github_repo_url=self.github_repo_url,
            project_website_url=self.project_website_url,
            team_contact=self.team_contact,
            submitter_name=self.submitter_name,
            submitter_contact=self.submitter_contact,
            submitter_payout_address=self.submitter_payout_address,
            ranking_reason=self.ranking_reason,
            team_aware=self.team_aware,
            additional_notes=self.additional_notes,
        )


class MediaSpeechRequest(BaseModel):
    text: str
    voice: str = "mimo_default"
    audio_format: str = "wav"
    style: str = ""
    user_prompt: str = ""


class MediaAudioAnalyzeRequest(BaseModel):
    prompt: str = "Please describe the content of the audio."
    audio_url: str = ""
    audio_base64: str = ""
    mime_type: str = "audio/wav"


class MediaVideoAnalyzeRequest(BaseModel):
    prompt: str = "Please describe the content of the video."
    video_url: str = ""
    video_base64: str = ""
    mime_type: str = "video/mp4"
    fps: int = Field(default=2, ge=1, le=8)
    media_resolution: str = "default"


class MediaVideoCreateRequest(BaseModel):
    brief: str
    audience: str = "patients"
    duration_seconds: int = Field(default=60, ge=15, le=300)
    language: str = "zh"
    tone: str = "clear medical education"


class HarnessResponse(BaseModel):
    success: bool
    result: dict[str, Any]
    execution_time_ms: float
    harness_version: str = __version__


class ToolInvokeRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class ToolchainInvokeRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class OpenClawExecuteRequest(BaseModel):
    target: str
    kind: str = "auto"
    context: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


app = FastAPI(
    title="OpenClaw-Medical-Harness API",
    description="Medical AI Agent Orchestration Framework",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_registry = MedicalToolRegistry()
_diagnosis_harness = DiagnosisHarness(specialty="neurology", tool_registry=_registry)
_drug_harness = DrugDiscoveryHarness(tool_registry=_registry)
_health_harness = HealthManagementHarness(tool_registry=_registry)
_openarena = OpenArenaClient()
_mimo_media = MimoMediaClient()
_start_time = time.time()


def _diagnosis_harness_for(specialty: str) -> DiagnosisHarness:
    normalized = (specialty or "neurology").strip().lower()
    return DiagnosisHarness(specialty=normalized, tool_registry=_registry)


@app.get("/", response_class=HTMLResponse, tags=["General"])
async def index() -> str:
    return render_demo_page(version=__version__, tool_count=len(_registry.list_all()))


@app.get("/health-check", tags=["General"])
async def health_check() -> dict[str, Any]:
    uptime = time.time() - _start_time
    return {
        "status": "healthy",
        "version": __version__,
        "uptime_seconds": round(uptime, 1),
        "harnesses": {
            "diagnosis": _diagnosis_harness.name,
            "drug_discovery": _drug_harness.name,
            "health_management": _health_harness.name,
        },
        "media": _mimo_media.runtime_report().__dict__,
        "tools_registered": len(_registry.list_all()),
    }


@app.get("/api/tools", tags=["General"])
async def list_tools() -> dict[str, Any]:
    return {"tools": _registry.list_all(), "categories": _registry.list_categories()}


@app.get("/api/toolchains", tags=["General"])
async def list_toolchains() -> dict[str, Any]:
    return {"toolchains": _registry.list_toolchains()}


@app.post("/api/tools/{tool_name}/execute", tags=["General"])
async def execute_tool(tool_name: str, request: ToolInvokeRequest) -> dict[str, Any]:
    tool = _registry.get(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    return {
        "success": True,
        "tool": tool.name,
        "resolved_from": tool_name,
        "result": _registry.call(tool_name, request.context, **request.params),
    }


@app.post("/api/toolchains/{harness_type}/execute", tags=["General"])
async def execute_toolchain(harness_type: str, request: ToolchainInvokeRequest) -> dict[str, Any]:
    if harness_type not in _registry.list_toolchains():
        raise HTTPException(status_code=404, detail=f"Unknown toolchain: {harness_type}")
    return {
        "success": True,
        "toolchain": harness_type,
        "results": _registry.execute_toolchain(harness_type, request.context, overrides=request.overrides),
    }


@app.post("/api/openclaw/execute", tags=["General"])
async def execute_openclaw(request: OpenClawExecuteRequest) -> dict[str, Any]:
    toolchains = _registry.list_toolchains()
    normalized_kind = (request.kind or "auto").strip().lower()

    if normalized_kind not in {"auto", "tool", "toolchain"}:
        raise HTTPException(status_code=400, detail="kind must be one of: auto, tool, toolchain")

    if normalized_kind in {"auto", "toolchain"} and request.target in toolchains:
        return {
            "success": True,
            "kind": "toolchain",
            "target": request.target,
            "results": _registry.execute_toolchain(request.target, request.context, overrides=request.overrides),
        }

    tool = _registry.get(request.target)
    if normalized_kind in {"auto", "tool"} and tool is not None:
        return {
            "success": True,
            "kind": "tool",
            "tool": tool.name,
            "target": request.target,
            "result": _registry.call(request.target, request.context, **request.params),
        }

    if normalized_kind == "toolchain":
        raise HTTPException(status_code=404, detail=f"Unknown toolchain: {request.target}")
    raise HTTPException(status_code=404, detail=f"Unknown tool or toolchain: {request.target}")


@app.get("/openarena/runtime", tags=["OpenArena"])
async def openarena_runtime() -> dict[str, Any]:
    report = _openarena.evaluate_env_submission(discover_action=False)
    submission_defaults = _openarena.default_submission()
    runtime = _openarena._runtime_config()
    return {
        "can_submit_live": not report.missing_runtime and not report.issues,
        "missing_runtime": report.missing_runtime,
        "warnings": report.warnings,
        "submission_defaults": {
            "x_post_url": submission_defaults.x_post_url,
            "project_name": submission_defaults.project_name,
            "github_repo_url": submission_defaults.github_repo_url,
            "project_website_url": submission_defaults.project_website_url,
            "team_contact": submission_defaults.team_contact,
            "submitter_name": submission_defaults.submitter_name,
            "submitter_contact": submission_defaults.submitter_contact,
            "submitter_payout_address": submission_defaults.submitter_payout_address,
            "ranking_reason": submission_defaults.ranking_reason,
            "additional_notes": submission_defaults.additional_notes,
        },
        "env_path": runtime["env_path"],
        "auto_discover_action": runtime["auto_discover_action"],
    }


@app.post("/diagnose", response_model=HarnessResponse, tags=["Harness"])
async def diagnose(request: DiagnoseRequest) -> HarnessResponse:
    start = time.time()
    input_data: dict[str, Any] = {
        "symptoms": request.symptoms,
        "specialty": request.specialty,
        "language": request.language,
    }
    if request.patient:
        input_data["patient"] = request.patient.model_dump(exclude_none=True)
    try:
        result = _diagnosis_harness_for(request.specialty).execute(input_data)
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=500, detail=f"Diagnosis harness error: {exc}") from exc
    return HarnessResponse(success=True, result=result, execution_time_ms=round((time.time() - start) * 1000, 2))


@app.post("/drug-discovery", response_model=HarnessResponse, tags=["Harness"])
async def drug_discovery(request: DrugDiscoveryRequest) -> HarnessResponse:
    start = time.time()
    try:
        result = _drug_harness.execute(request.model_dump())
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=500, detail=f"Drug discovery harness error: {exc}") from exc
    return HarnessResponse(success=True, result=result, execution_time_ms=round((time.time() - start) * 1000, 2))


@app.post("/health", response_model=HarnessResponse, tags=["Harness"])
async def health_management(request: HealthRequest) -> HarnessResponse:
    start = time.time()
    input_data = request.model_dump()
    if request.age is not None:
        input_data["patient"] = {"age": request.age}
    try:
        result = _health_harness.execute(input_data)
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=500, detail=f"Health harness error: {exc}") from exc
    return HarnessResponse(success=True, result=result, execution_time_ms=round((time.time() - start) * 1000, 2))


@app.get("/media/runtime", tags=["Media"])
async def media_runtime() -> dict[str, Any]:
    report = _mimo_media.runtime_report()
    return {
        "provider": report.provider,
        "base_url": report.base_url,
        "has_api_key": report.has_api_key,
        "supported": report.supported,
        "limitations": report.limitations,
    }


@app.post("/media/audio/synthesize", tags=["Media"])
async def media_audio_synthesize(request: MediaSpeechRequest) -> dict[str, Any]:
    try:
        return _mimo_media.synthesize_speech(
            text=request.text,
            voice=request.voice,
            audio_format=request.audio_format,
            style=request.style,
            user_prompt=request.user_prompt,
        )
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=400, detail=f"MiMo speech synthesis error: {exc}") from exc


@app.post("/media/audio/analyze", tags=["Media"])
async def media_audio_analyze(request: MediaAudioAnalyzeRequest) -> dict[str, Any]:
    try:
        return _mimo_media.analyze_audio(
            prompt=request.prompt,
            audio_url=request.audio_url,
            audio_base64=request.audio_base64,
            mime_type=request.mime_type,
        )
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=400, detail=f"MiMo audio understanding error: {exc}") from exc


@app.post("/media/video/analyze", tags=["Media"])
async def media_video_analyze(request: MediaVideoAnalyzeRequest) -> dict[str, Any]:
    try:
        return _mimo_media.analyze_video(
            prompt=request.prompt,
            video_url=request.video_url,
            video_base64=request.video_base64,
            mime_type=request.mime_type,
            fps=request.fps,
            media_resolution=request.media_resolution,
        )
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=400, detail=f"MiMo video understanding error: {exc}") from exc


@app.post("/media/video/create", tags=["Media"])
async def media_video_create(request: MediaVideoCreateRequest) -> dict[str, Any]:
    try:
        return _mimo_media.create_video_package(
            brief=request.brief,
            audience=request.audience,
            duration_seconds=request.duration_seconds,
            language=request.language,
            tone=request.tone,
        )
    except Exception as exc:  # pragma: no cover - endpoint guard
        raise HTTPException(status_code=400, detail=f"MiMo video package error: {exc}") from exc


@app.post("/openarena/readiness", tags=["OpenArena"])
async def openarena_readiness(request: OpenArenaRequest) -> dict[str, Any]:
    report = _openarena.evaluate_submission(request.to_submission(), include_runtime_status=True, discover_action=False)
    return {
        "ready": report.ready,
        "score": report.score,
        "issues": report.issues,
        "warnings": report.warnings,
        "missing_runtime": report.missing_runtime,
        "submission_payload": report.submission_payload,
        "discovered_action_id": report.discovered_action_id,
    }


@app.post("/openarena/submit", tags=["OpenArena"])
async def openarena_submit(request: OpenArenaRequest) -> dict[str, Any]:
    try:
        result = _openarena.submit(request.to_submission())
    except Exception as exc:  # pragma: no cover - network variability
        raise HTTPException(status_code=500, detail=f"OpenArena submit error: {exc}") from exc
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": result.error,
                "action_id": result.action_id,
            },
        )
    return {
        "success": True,
        "submission_id": result.submission_id,
        "action_id": result.action_id,
    }


@app.post("/openarena/submit-default", tags=["OpenArena"])
async def openarena_submit_default() -> dict[str, Any]:
    readiness = _openarena.evaluate_env_submission(discover_action=False)
    if not readiness.ready:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "issues": readiness.issues,
                "missing_runtime": readiness.missing_runtime,
                "warnings": readiness.warnings,
            },
        )
    try:
        result = _openarena.submit_from_env()
    except Exception as exc:  # pragma: no cover - network variability
        raise HTTPException(status_code=500, detail=f"OpenArena one-click submit error: {exc}") from exc
    if not result.success:
        raise HTTPException(status_code=400, detail={"success": False, "error": result.error})
    return {
        "success": True,
        "submission_id": result.submission_id,
        "action_id": result.action_id,
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
