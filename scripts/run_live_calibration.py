#!/usr/bin/env python3
"""Run one private, input-counted, isolated development calibration."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.live_calibration import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = execute(args.root, args.key_file, ROOT / "scripts/lean_sandbox.py")
    except Exception as exc:
        # Do not expose a key, raw provider error, or credential source contents.
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps({k: result[k] for k in ("status", "generation_calls")}, indent=2))
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
