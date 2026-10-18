#!/usr/bin/env python3
"""Recheck all archived LLM outputs, including failed attempts; no LLM rerun."""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.independent import replay_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "results/independent")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if shutil.which("lean") is None:
        parser.error("install and warm Lean 4.24.0, with lean on PATH, before replay")
    result = replay_archive(args.archive, args.output)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
