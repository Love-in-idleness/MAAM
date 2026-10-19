#!/usr/bin/env python3
"""Prepare a frozen transfer study, inspect it, or explicitly run one paid phase."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.transfer import prepare, report, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "status", "run"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--protocol", type=Path, default=ROOT / "experiments/metered_transfer_v1/protocol.json")
    parser.add_argument("--phase", choices=("development", "reserved"))
    parser.add_argument("--key-file", type=Path)
    args = parser.parse_args()
    if args.action == "run" and (args.phase is None or args.key_file is None):
        parser.error("run requires an explicit --phase and --key-file")
    os.umask(0o077)
    try:
        if args.action == "prepare":
            result = prepare(args.protocol, args.root)
        elif args.action == "status":
            result = report(args.root)
        else:
            result = run(args.root, args.phase, key_file=args.key_file)
    except Exception as exc:
        # Provider errors and credential source contents must never reach the UI.
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["status"] == "stopped" else 0


if __name__ == "__main__":
    raise SystemExit(main())
