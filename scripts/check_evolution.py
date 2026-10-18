#!/usr/bin/env python3
"""Recheck every archived attempt and full inventory with the pinned Lean."""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.evolution import replay_archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "results/evolution")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    if shutil.which(args.lean) is None or shutil.which("lean") is None:
        parser.error("install pinned Lean and expose lean on PATH for auditor subprocesses")
    result = replay_archive(args.archive, args.output, lean=args.lean)
    raise SystemExit(0 if result["status"] == "passed" else 1)
