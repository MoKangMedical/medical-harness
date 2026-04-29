import asyncio
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import httpx
import pytest

from openclaw_medical_harness import (
    DiagnosisHarness,
    MedicalToolRegistry,
    OpenArenaClient,
    OpenArenaProjectSubmission,
    ResultValidator,
)
from openclaw_medical_harness.daemon import DaemonPaths, is_process_running, read_pid, status_payload


def make_transport(routes):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key not in routes:
            return httpx.Response(404, text="not found")
        status_code, payload, headers = routes[key]
        if isinstance(payload, dict):
            return httpx.Response(status_code, json=payload, headers=headers)
        return httpx.Response(status_code, text=payload, headers=headers)

    return httpx.MockTransport(handler)


def test_registry_alias_resolution_and_list_all():
    registry = MedicalToolRegistry()
    assert registry.get("pubmed") is not None
    assert registry.get("pubmed_search") is not None
    assert registry.get("chembl_query") is not None
    assert registry.get("opentargets_association") is not None
    assert registry.get("omim_lookup") is not None
    assert registry.get("openfae_safety") is not None
    assert len(registry.list_all()) >= 6


def test_registry_tools_for_harness_matches_docs():
    registry = MedicalToolRegistry()
    diagnosis_tools = registry.get_tools_for_harness("diagnosis")
    drug_tools = registry.get_tools_for_harness("drug_discovery")
    assert [tool["name"] for tool in diagnosis_tools] == ["pubmed", "omim", "opentargets"]
    assert "rdkit" in [tool["name"] for tool in drug_tools]
    assert registry.get_tools_for_harness("unknown") == []
    toolchains = registry.list_toolchains()
    assert sorted(toolchains) == ["diagnosis", "drug_discovery", "health_management"]
    assert [tool["name"] for tool in toolchains["health_management"]] == ["pubmed", "openfda"]


def test_registry_real_http_execution_with_mock_transport():
    transport = make_transport(
        {
            (
                "GET",
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=3&sort=relevance&term=myasthenia+gravis",
            ): (
                200,
                {"esearchresult": {"count": "42", "idlist": ["1", "2"], "querytranslation": "myasthenia gravis"}},
                {},
            )
        }
    )
    client = httpx.Client(transport=transport)
    registry = MedicalToolRegistry(client=client)
    result = registry.call("pubmed_search", {}, query="myasthenia gravis", max_results=3)
    assert result["tool"] == "pubmed"
    assert result["count"] == 42
    assert result["ids"] == ["1", "2"]


def test_registry_graphql_adapter_keeps_exact_base_url():
    transport = make_transport(
        {
            ("POST", "https://api.platform.opentargets.org/api/v4/graphql"): (
                200,
                {"data": {"search": {"total": 1, "hits": [{"id": "ENSG000001", "entity": "target"}]}}},
                {},
            )
        }
    )
    client = httpx.Client(transport=transport)
    registry = MedicalToolRegistry(client=client)
    result = registry.call("opentargets_association", {}, query="EGFR NSCLC")
    assert result["tool"] == "opentargets"
    assert result["total"] == 1


def test_diagnosis_harness_returns_multiple_differentials_for_known_case():
    harness = DiagnosisHarness(specialty="neurology")
    result = harness.execute(
        {
            "symptoms": ["bilateral ptosis", "fatigable weakness", "diplopia"],
            "patient": {"age": 35, "sex": "F"},
        }
    )
    assert "重症肌无力" in result["diagnosis"] or "Myasthenia Gravis" in result["diagnosis"]
    assert len(result["differential"]) >= 2
    assert "support_signals" in result["evidence"]


def test_diagnosis_harness_supports_common_presentation_pathways():
    harness = DiagnosisHarness(specialty="cardiology")
    result = harness.execute(
        {
            "symptoms": ["chest pain radiating to left arm", "sweating", "nausea"],
            "patient": {"age": 62, "sex": "M"},
            "specialty": "cardiology",
        }
    )
    assert "Acute Coronary Syndrome" in result["diagnosis"]
    assert len(result["differential"]) >= 2
    assert result["recovery_applied"] is False


def test_domain_validator_detects_missing_differential_in_strict_mode():
    validator = ResultValidator(strict_mode=True)
    validation = validator.validate({"diagnosis": "MG", "confidence": 0.9}, domain="diagnosis")
    assert not validation.passed


def test_openarena_readiness_flags_runtime_and_payload_issues():
    client = OpenArenaClient()
    report = client.evaluate_submission(
        OpenArenaProjectSubmission(
            x_post_url="https://x.com/user/status/123",
            project_name="OpenClaw-Medical-Harness",
            github_repo_url="https://github.com/MoKangMedical/openclaw-medical-harness",
            ranking_reason="short",
        ),
        include_runtime_status=True,
        discover_action=False,
    )
    assert "missing required field: team_contact" in report.issues
    assert "OPENARENA_SESSION_COOKIE" in report.missing_runtime
    assert report.score < 100


def test_openarena_action_discovery_and_submit_parsing():
    html = '<html><script src="/_next/static/chunks/app-submit.js"></script></html>'
    js = 'console.log("submitProjectAction","abcde12345abcde12345abcde12345");'
    rsc = '\n'.join(
        [
            '0:{"a":"$@1"}',
            '1:{"success":true,"submissionId":"sub_123"}',
        ]
    )
    transport = make_transport(
        {
            ("GET", "https://openarena.to/submit"): (200, html, {}),
            ("GET", "https://openarena.to/_next/static/chunks/app-submit.js"): (200, js, {}),
            ("POST", "https://openarena.to/submit"): (200, rsc, {"content-type": "text/x-component"}),
        }
    )
    submission = OpenArenaProjectSubmission(
        x_post_url="https://x.com/user/status/123456",
        project_name="OpenClaw-Medical-Harness",
        github_repo_url="https://github.com/MoKangMedical/openclaw-medical-harness",
        team_contact="tony@example.com, @handle",
        submitter_name="Lin Zhang",
        submitter_contact="tony@example.com, @handle",
        submitter_payout_address="0x123",
        ranking_reason="This project adds a reusable harness layer for medical AI workflows with tools, validation, recovery, and domain-specific execution paths.",
    )
    client = OpenArenaClient(client=httpx.Client(transport=transport))
    result = client.submit(
        submission,
        session_cookie="openarena_session=test",
        auto_discover_action=True,
    )
    assert result.success is True
    assert result.submission_id == "sub_123"
    assert result.action_id == "abcde12345abcde12345abcde12345"


def test_openarena_loads_defaults_from_dotenv(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join(
            [
                "OPENARENA_PROJECT_NAME=OpenClaw-Medical-Harness",
                "OPENARENA_GITHUB_REPO_URL=https://github.com/MoKangMedical/openclaw-medical-harness",
                "OPENARENA_X_POST_URL=https://x.com/user/status/123456",
                "OPENARENA_TEAM_CONTACT=team@example.com, @handle",
                "OPENARENA_SUBMITTER_NAME=Lin Zhang",
                "OPENARENA_SUBMITTER_CONTACT=team@example.com, @handle",
                "OPENARENA_SUBMITTER_PAYOUT_ADDRESS=0x123",
                "OPENARENA_RANKING_REASON=This project adds a reusable harness layer for medical AI workflows with tools, validation, recovery, and domain-specific execution paths.",
                "OPENARENA_SESSION_COOKIE=openarena_session=test",
                "OPENARENA_AUTO_DISCOVER_ACTION=true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENARENA_PROJECT_NAME", raising=False)
    monkeypatch.delenv("OPENARENA_SESSION_COOKIE", raising=False)
    client = OpenArenaClient()
    submission = client.default_submission()
    runtime = client._runtime_config()
    assert submission.project_name == "OpenClaw-Medical-Harness"
    assert runtime["session_cookie"] == "openarena_session=test"
    assert runtime["auto_discover_action"] is True


def test_demo_server_health_check_and_interactive_page():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    payload = asyncio.run(demo_server.health_check())
    html = asyncio.run(demo_server.index())
    assert payload["status"] == "healthy"
    assert payload["tools_registered"] == len(demo_server._registry.list_all())
    assert "Diagnosis Harness" in html
    assert "OpenArena lane" in html
    assert "Launch Workbench" in html


def test_demo_server_openarena_readiness_endpoint():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    request = demo_server.OpenArenaRequest(
        x_post_url="https://x.com/user/status/123456",
        team_contact="team@example.com, @handle",
        submitter_name="Lin Zhang",
        submitter_contact="team@example.com, @handle",
        submitter_payout_address="0x123",
        ranking_reason="This project adds a reusable harness layer for medical AI workflows with tools, validation, recovery, and domain-specific execution paths.",
    )
    payload = asyncio.run(demo_server.openarena_readiness(request))
    assert "submission_payload" in payload
    assert payload["ready"] in {True, False}


def test_demo_server_runtime_exposes_env_defaults():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    payload = asyncio.run(demo_server.openarena_runtime())
    assert "submission_defaults" in payload
    assert "auto_discover_action" in payload


def test_demo_server_list_toolchains_endpoint():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    payload = asyncio.run(demo_server.list_toolchains())
    assert "toolchains" in payload
    assert "diagnosis" in payload["toolchains"]


def test_demo_server_execute_tool_endpoint(monkeypatch):
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")

    def fake_call(name, context=None, **kwargs):
        return {"tool": name, "context": context or {}, "kwargs": kwargs, "status": "ok"}

    monkeypatch.setattr(demo_server._registry, "call", fake_call)
    payload = asyncio.run(
        demo_server.execute_tool(
            "pubmed_search",
            demo_server.ToolInvokeRequest(
                context={"patient": {"disease": "MG"}},
                params={"query": "myasthenia gravis", "max_results": 3},
            ),
        )
    )
    assert payload["success"] is True
    assert payload["resolved_from"] == "pubmed_search"
    assert payload["result"]["tool"] == "pubmed_search"


def test_demo_server_execute_toolchain_endpoint(monkeypatch):
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")

    def fake_execute(harness_type, context, overrides=None):
        return {"harness_type": harness_type, "context": context, "overrides": overrides or {}}

    monkeypatch.setattr(demo_server._registry, "execute_toolchain", fake_execute)
    payload = asyncio.run(
        demo_server.execute_toolchain(
            "diagnosis",
            demo_server.ToolchainInvokeRequest(
                context={"patient": {"symptoms": ["ptosis"]}},
                overrides={"pubmed": {"query": "myasthenia gravis"}},
            ),
        )
    )
    assert payload["success"] is True
    assert payload["toolchain"] == "diagnosis"
    assert payload["results"]["harness_type"] == "diagnosis"


def test_demo_server_execute_openclaw_tool_auto(monkeypatch):
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")

    def fake_call(name, context=None, **kwargs):
        return {"tool": name, "context": context or {}, "kwargs": kwargs, "status": "ok"}

    monkeypatch.setattr(demo_server._registry, "call", fake_call)
    payload = asyncio.run(
        demo_server.execute_openclaw(
            demo_server.OpenClawExecuteRequest(
                target="pubmed_search",
                context={"patient": {"disease": "MG"}},
                params={"query": "myasthenia gravis"},
            )
        )
    )
    assert payload["success"] is True
    assert payload["kind"] == "tool"
    assert payload["tool"] == "pubmed"


def test_demo_server_execute_openclaw_toolchain_auto(monkeypatch):
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")

    def fake_execute(harness_type, context, overrides=None):
        return {"harness_type": harness_type, "context": context, "overrides": overrides or {}}

    monkeypatch.setattr(demo_server._registry, "execute_toolchain", fake_execute)
    payload = asyncio.run(
        demo_server.execute_openclaw(
            demo_server.OpenClawExecuteRequest(
                target="diagnosis",
                context={"patient": {"symptoms": ["ptosis"]}},
                overrides={"pubmed": {"query": "myasthenia gravis"}},
            )
        )
    )
    assert payload["success"] is True
    assert payload["kind"] == "toolchain"
    assert payload["target"] == "diagnosis"


def test_demo_server_diagnose_uses_request_specialty():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    payload = asyncio.run(
        demo_server.diagnose(
            demo_server.DiagnoseRequest(
                symptoms=["chest pain radiating to left arm", "sweating", "nausea"],
                specialty="cardiology",
            )
        )
    )
    assert payload.result["harness_name"] == "diagnosis_cardiology"


def test_demo_server_media_runtime_endpoint():
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")
    payload = asyncio.run(demo_server.media_runtime())
    assert payload["provider"] == "xiaomi-mimo"
    assert "audio_synthesis" in payload["supported"]


def test_demo_server_media_audio_synthesize_endpoint(monkeypatch):
    pytest.importorskip("fastapi")
    demo_server = importlib.import_module("demo_server")

    def fake_speech(**kwargs):
        return {"provider": "xiaomi-mimo", "audio_base64": "ZmFrZQ==", "voice": kwargs["voice"]}

    monkeypatch.setattr(demo_server._mimo_media, "synthesize_speech", fake_speech)
    payload = asyncio.run(
        demo_server.media_audio_synthesize(
            demo_server.MediaSpeechRequest(
                text="hello",
                voice="default_en",
            )
        )
    )
    assert payload["provider"] == "xiaomi-mimo"
    assert payload["voice"] == "default_en"


def test_daemon_read_pid_and_process_probe():
    with tempfile.TemporaryDirectory() as tmpdir:
        pid_file = os.path.join(tmpdir, "openclawd.pid")
        with open(pid_file, "w", encoding="utf-8") as handle:
            handle.write("12345")
        assert read_pid(Path(pid_file)) == 12345

    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    try:
        assert is_process_running(sleeper.pid) is True
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)
    assert is_process_running(sleeper.pid) is False


def test_daemon_status_payload_without_running_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = DaemonPaths(
            runtime_dir=Path(tmpdir),
            pid_file=Path(os.path.join(tmpdir, "openclawd.pid")),
            log_file=Path(os.path.join(tmpdir, "openclawd.log")),
        )
        payload = status_payload("127.0.0.1", 8011, paths)
        assert payload["running"] is False
        assert payload["healthy"] is False
