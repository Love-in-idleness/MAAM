#!/usr/bin/env python3
"""Freeze a small existing baseline proof pool without model calls."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam.baseline import inventory_baseline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", action="append", required=True, type=Path)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        report = inventory_baseline(args.session, args.task)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps({"status": report["status"], "missing_tasks": report["missing_tasks"],
                      "output": str(args.output)}))
    return 1 if report["missing_tasks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
