#!/usr/bin/env python3
"""Prepare, preflight, execute one call, or replay the fixed constrained-construction trial."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import CorpusError
from maam import construct_use
from maam.lean_sandbox import SandboxUnavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "next", "report"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--key-file", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = construct_use.prepare(construct_use.FIXTURE, args.output)
        elif args.action == "preflight":
            result = construct_use.preflight(args.output)
        elif args.action == "next":
            if args.key_file is None:
                parser.error("next requires the user-selected --key-file")
            result = construct_use.execute_next(args.output, args.key_file)
        else:
            result = construct_use.report(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (CorpusError, OSError, ValueError, SandboxUnavailable) as exc:
        # Credential paths and provider exception bodies are never printed.
        print("Construction controller stopped: " + (str(exc) if isinstance(exc, CorpusError) else type(exc).__name__), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
