"""Minimal .env loading helpers for local runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path


def find_dotenv(start_dir: str | Path | None = None) -> Path | None:
    current = Path(start_dir or os.getcwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.exists():
            return candidate
    return None


def load_dotenv(path: str | Path | None = None, *, override: bool = False) -> Path | None:
    dotenv_path = Path(path).resolve() if path else find_dotenv()
    if dotenv_path is None or not dotenv_path.exists():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if override or key not in os.environ:
            os.environ[key] = value
    return dotenv_path


def getenv(name: str, default: str | None = None, *, env_path: str | Path | None = None) -> str | None:
    load_dotenv(env_path)
    return os.getenv(name, default)


def getenv_bool(name: str, default: bool = False, *, env_path: str | Path | None = None) -> bool:
    value = getenv(name, None, env_path=env_path)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
