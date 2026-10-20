#!/usr/bin/env python3
"""Execute and replay bounded existing-tool rewrites without any API transport."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import baseline_execution as execution


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--search-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "prepare" and args.search_root is None:
        parser.error("prepare requires --search-root")
    os.umask(0o077)
    try:
        if args.action == "prepare":
            result = execution.prepare_execution(args.search_root, args.root)
        elif args.action == "status":
            result = execution.report(args.root)
        else:
            result = execution.report(args.root)
            while result["status"] == "in_progress":
                result = execution.execute_next(args.root)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"status": result["status"], "output": str(args.output)}))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    return 2 if result["status"] == "interrupted_or_inconclusive" else 0


if __name__ == "__main__":
    raise SystemExit(main())
