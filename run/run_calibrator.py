#!/usr/bin/env python3
"""Launch candidates calibrator."""
import sys
from pathlib import Path

# Project root = parent of run/
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))

from run_calibrator import main

if __name__ == "__main__":
    sys.exit(main())
