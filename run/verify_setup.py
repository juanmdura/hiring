#!/usr/bin/env python3
"""Launch setup verification."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))

from verify_setup import main

if __name__ == "__main__":
    main()
