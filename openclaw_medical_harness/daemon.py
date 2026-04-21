"""Background process manager for the OpenClaw demo server."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(frozen=True)
class DaemonPaths:
    runtime_dir: Path
    pid_file: Path
    log_file: Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_paths() -> DaemonPaths:
    runtime_dir = project_root() / ".openclaw"
    return DaemonPaths(
        runtime_dir=runtime_dir,
        pid_file=runtime_dir / "openclawd.pid",
        log_file=runtime_dir / "openclawd.log",
    )


def python_executable() -> Path:
    return project_root() / ".venv" / "bin" / "python"


def ensure_server_runtime() -> None:
    python_bin = python_executable()
    if python_bin.exists():
        probe = subprocess.run(
            [
                str(python_bin),
                "-c",
                "import fastapi, uvicorn; print('ok')",
            ],
            cwd=project_root(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            return

    subprocess.run(
        ["uv", "sync", "--extra", "server"],
        cwd=project_root(),
        check=True,
    )


def read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    value = pid_file.read_text(encoding="utf-8").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_process_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_health(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def status_payload(host: str, port: int, paths: DaemonPaths | None = None) -> dict[str, object]:
    resolved = paths or default_paths()
    pid = read_pid(resolved.pid_file)
    running = is_process_running(pid)
    url = f"http://{host}:{port}"
    payload: dict[str, object] = {
        "running": running,
        "pid": pid,
        "url": url,
        "health_url": f"{url}/health-check",
        "pid_file": str(resolved.pid_file),
        "log_file": str(resolved.log_file),
    }
    if running:
        try:
            response = httpx.get(f"{url}/health-check", timeout=2.0)
            payload["healthy"] = response.status_code == 200
        except httpx.HTTPError:
            payload["healthy"] = False
    else:
        payload["healthy"] = False
    return payload


def start_server(host: str, port: int, paths: DaemonPaths | None = None) -> dict[str, object]:
    resolved = paths or default_paths()
    resolved.runtime_dir.mkdir(parents=True, exist_ok=True)

    current_pid = read_pid(resolved.pid_file)
    if is_process_running(current_pid):
        return status_payload(host, port, resolved)

    ensure_server_runtime()
    python_bin = python_executable()
    if not python_bin.exists():
        raise RuntimeError("Python runtime was not created in .venv after dependency sync")

    with resolved.log_file.open("ab") as log_handle:
        process = subprocess.Popen(
            [
                str(python_bin),
                "-m",
                "uvicorn",
                "demo_server:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=project_root(),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    resolved.pid_file.write_text(str(process.pid), encoding="utf-8")
    health_url = f"http://{host}:{port}/health-check"
    if not wait_for_health(health_url):
        stop_server(host, port, resolved, missing_ok=True)
        raise RuntimeError(f"Server failed health check after start: {health_url}")
    return status_payload(host, port, resolved)


def stop_server(host: str, port: int, paths: DaemonPaths | None = None, missing_ok: bool = False) -> dict[str, object]:
    resolved = paths or default_paths()
    pid = read_pid(resolved.pid_file)
    if not is_process_running(pid):
        if resolved.pid_file.exists():
            resolved.pid_file.unlink()
        if missing_ok:
            return status_payload(host, port, resolved)
        return status_payload(host, port, resolved)

    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not is_process_running(pid):
            break
        time.sleep(0.2)
    if is_process_running(pid):
        os.kill(pid, signal.SIGKILL)

    if resolved.pid_file.exists():
        resolved.pid_file.unlink()
    return status_payload(host, port, resolved)


def restart_server(host: str, port: int, paths: DaemonPaths | None = None) -> dict[str, object]:
    resolved = paths or default_paths()
    stop_server(host, port, resolved, missing_ok=True)
    return start_server(host, port, resolved)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the OpenClaw demo server as a background process.")
    parser.add_argument("command", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            payload = start_server(args.host, args.port)
        elif args.command == "stop":
            payload = stop_server(args.host, args.port)
        elif args.command == "restart":
            payload = restart_server(args.host, args.port)
        else:
            payload = status_payload(args.host, args.port)
    except subprocess.CalledProcessError as exc:
        print(json.dumps({"success": False, "error": str(exc), "returncode": exc.returncode}, ensure_ascii=False))
        return exc.returncode or 1
    except Exception as exc:  # pragma: no cover - CLI guard
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"success": True, **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
