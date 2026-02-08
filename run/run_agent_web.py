#!/usr/bin/env python3
"""Start ADK web UI for the calibrator agent (development only)."""
import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
agent_dir = _root / "calibrator_agent"
if not agent_dir.exists():
    print("calibrator_agent/ not found.", file=sys.stderr)
    sys.exit(1)
# Run adk web from project root so it finds calibrator_agent
sys.exit(subprocess.call(["adk", "web", "--port", "8000"], cwd=_root))
