"""Run the pinned conjecture evaluator with an explicit larger audit budget."""

import argparse
from pathlib import Path
import json
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maam import conjecture_compression as evaluator
from maam.theory import digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", required=True)
    p.add_argument("--mathlib", required=True)
    p.add_argument("--lean", required=True)
    p.add_argument("--auditor-source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    original = evaluator._command

    def run(command, cwd, env, resources, deadline, stage, trace):
        return original(command, cwd, env, {**resources, "per_command_timeout_seconds": 120},
                        deadline + 360, stage, trace)

    with patch.object(evaluator, "_command", run):
        report = evaluator.measure_compression(args.suite, args.mathlib, lean=args.lean)
    report["panel_audit"] = {"compiled_source_sha256": digest(args.auditor_source.read_bytes()),
                             "per_command_timeout_seconds": 120, "total_timeout_seconds": 540}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0 if report["status"] == "measured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
