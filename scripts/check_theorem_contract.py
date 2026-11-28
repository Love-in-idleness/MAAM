#!/usr/bin/env python3
"""Prepare, inspect, run or replay fixed offline theorem-declaration controls."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import CorpusError, theorem_contract
from maam.lean_sandbox import SandboxUnavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "input", "run", "report"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--task", choices=theorem_contract.TASKS)
    parser.add_argument("--guide", action="store_true")
    args = parser.parse_args()
    if args.action == "input" and args.task is None:
        parser.error("input requires --task")
    try:
        if args.action == "input":
            result = theorem_contract.task_input(args.output, args.task, include_guide=args.guide)
        else:
            result = getattr(theorem_contract, args.action)(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get("status") in {"failed", "interrupted"})
    except (CorpusError, OSError, ValueError, SandboxUnavailable) as exc:
        print("Offline contract controls stopped: " + (str(exc) if isinstance(exc, CorpusError)
              else type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
