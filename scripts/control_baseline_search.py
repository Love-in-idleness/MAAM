#!/usr/bin/env python3
"""Record bounded baseline-only searches; this CLI makes no model calls."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import baseline_search
from maam.theory import read_object


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "request", "submit", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--submission", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "prepare" and (args.inventory is None or args.policy is None):
        parser.error("prepare requires --inventory and --policy")
    if args.action == "submit" and args.submission is None:
        parser.error("submit requires --submission")
    os.umask(0o077)
    try:
        if args.action == "prepare":
            baseline_search.prepare_search(args.inventory, read_object(args.policy), args.root)
            result = baseline_search.report(args.root)
        elif args.action == "request":
            request = baseline_search.next_request(args.root)
            result = request if request is not None else baseline_search.report(args.root)
        elif args.action == "submit":
            result = baseline_search.submit(args.root, read_object(args.submission))
        else:
            result = baseline_search.report(args.root)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"status": "written", "output": str(args.output)}))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    return 2 if result.get("status") in {"interrupted_or_inconclusive", "sweep_budget_exhausted"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
