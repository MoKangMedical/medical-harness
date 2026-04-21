#!/usr/bin/env python3
"""CLI wrapper for running the OpenClaw demo server in the background."""

from openclaw_medical_harness.daemon import main


if __name__ == "__main__":
    raise SystemExit(main())
