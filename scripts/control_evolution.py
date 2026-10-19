#!/usr/bin/env python3
"""Prepare, record and verify a frozen package-version experiment."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam import evolution
from checkpoint_evolution import checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "register", "verify", "measure", "status", "export"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--study", type=Path, default=ROOT / "experiments/hom_kernel_evolution/study.json")
    parser.add_argument("--skill", type=Path, default=ROOT / "skills/evaluate-theory-package")
    parser.add_argument("--workers", type=Path)
    parser.add_argument("--freeze-commit")
    parser.add_argument("--construction", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--worker")
    parser.add_argument("--agent-id")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--checkpoints", type=Path,
                        help="Append a complete checkpoint before and after each operation")
    args = parser.parse_args()
    if args.checkpoints and args.root.exists():
        checkpoint(args.root, args.checkpoints, "before:" + args.action)
    try:
        result = dispatch(args, parser)
    finally:
        if args.checkpoints and (args.root / "run.json").exists():
            checkpoint(args.root, args.checkpoints, "after:" + args.action)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def dispatch(args, parser):
    if args.action == "prepare":
        if args.workers is None or args.freeze_commit is None:
            parser.error("prepare requires --workers and --freeze-commit")
        result = evolution.prepare(args.study, args.root, args.workers, args.skill, args.freeze_commit,
            construction=json.loads(args.construction.read_text()) if args.construction else None,
            runtime=json.loads(args.runtime.read_text()) if args.runtime else None)
    elif args.action == "register":
        result = evolution.register(args.root, args.worker, args.agent_id)
    elif args.action == "verify":
        result = evolution.verify_return(args.root, args.worker, args.attempt, lean=args.lean)
    elif args.action == "measure":
        result = evolution.measure(args.root, lean=args.lean)
    elif args.action == "status":
        result = evolution.summarize(args.root)
    else:
        if args.output is None:
            parser.error("export requires --output")
        result = evolution.export_run(args.root, args.output)
    return result


if __name__ == "__main__":
    main()
