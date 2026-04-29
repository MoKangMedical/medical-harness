#!/usr/bin/env python3
"""One-command OpenArena readiness check and live submission."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from openclaw_medical_harness import OpenArenaClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit OpenClaw-Medical-Harness to OpenArena using .env runtime config.")
    parser.add_argument("--check-only", action="store_true", help="Only print readiness; do not submit.")
    parser.add_argument("--discover-action", action="store_true", help="Force live action-id discovery before submit.")
    args = parser.parse_args()

    client = OpenArenaClient()
    readiness = client.evaluate_env_submission(discover_action=args.discover_action)
    print(json.dumps(asdict(readiness), indent=2, ensure_ascii=False))

    if args.check_only:
        return 0 if readiness.ready else 1

    if not readiness.ready:
        print("OpenArena runtime is not ready for live submission.", file=sys.stderr)
        return 1

    result = client.submit_from_env(auto_discover_action=args.discover_action)
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
