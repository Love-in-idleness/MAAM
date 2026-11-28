#!/usr/bin/env python3
"""Prepare, check, replay, or preview the offline closure-transport fixture."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import CorpusError, closure_transport
from maam.lean_sandbox import SandboxUnavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report", "input"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--guide", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = closure_transport.prepare(args.output)
        elif args.action == "run":
            result = closure_transport.run(args.output)
        elif args.action == "input":
            if not args.task:
                parser.error("input requires --task")
            result = closure_transport.task_input(args.output, args.task, include_guide=args.guide)
        else:
            result = closure_transport.report(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (CorpusError, OSError, ValueError, SandboxUnavailable) as exc:
        print("Offline closure check stopped: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
