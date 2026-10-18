#!/usr/bin/env python3
"""Prepare/record a fresh-worker study without binding a model provider.

The user or an applicable skill must authorize any external worker calls.
This program does not launch agents or meter generation tokens.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.independent import (export_run, measure_verified, prepare_run,
                              register_launch, summarize, verify_return)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "register", "verify", "measure", "status", "export"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--worker")
    parser.add_argument("--agent-id")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=Path)
    parser.add_argument("--freeze-commit")
    args = parser.parse_args()
    if args.action == "prepare":
        if args.workers is None or args.freeze_commit is None:
            parser.error("prepare requires --workers and --freeze-commit")
        result = prepare_run(ROOT / "experiments/hom_kernel_independent/protocol.json", args.run,
                             args.workers, ROOT / "skills/evaluate-theory-package",
                             freeze_commit=args.freeze_commit)
    elif args.action == "register":
        if args.worker is None or args.agent_id is None:
            parser.error("register requires --worker and --agent-id")
        result = register_launch(args.run, args.worker, args.agent_id)
    elif args.action == "verify":
        if args.worker is None or args.attempt is None:
            parser.error("verify requires --worker and --attempt")
        result = verify_return(args.run, args.worker, args.attempt)
    elif args.action == "measure":
        result = measure_verified(args.run)
    elif args.action == "export":
        if args.output is None:
            parser.error("export requires --output")
        result = export_run(args.run, args.output)
    else:
        result = summarize(args.run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.action == "verify" and result["status"] != "verified":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
