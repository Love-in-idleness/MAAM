#!/usr/bin/env python3
"""Prepare, run or inspect a bounded direct-provider development calibration."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.corpus import CorpusError
from maam.generation import prepare, report, run
from maam.theory import read_object


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--task", action="append")
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            if args.suite is None or args.config is None or not args.task:
                parser.error("prepare requires --suite, --config and at least one --task")
            result = prepare(args.suite, args.root, read_object(args.config), args.task)
        elif args.action == "run":
            result = run(args.root, lean=args.lean)
        else:
            result = report(args.root)
    except (CorpusError, OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    if args.action == "run" and any(t["status"] != "verified" for t in result["tasks"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
