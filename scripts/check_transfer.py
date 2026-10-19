#!/usr/bin/env python3
"""Offline development-only controller smoke with synthetic usage and real Lean."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.migration import canonical, save_new
from maam.transfer import prepare, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    folder = ROOT / "experiments/metered_transfer_v1"
    prepare(folder / "protocol.json", args.output, verify_commit=False)
    references = json.loads((folder / "reference_proofs.json").read_bytes())["tasks"]
    calls = []

    def counting(payload, timeout):
        return 200, None, canonical({"input_tokens": 1000, "method": "synthetic_fixture"})

    def transport(payload, timeout):
        request = json.loads(payload["input"])["request"]
        task, condition = request["task"]["id"], request["condition"]
        proof = references[task][condition] if calls else {"proof": "by sorry", "bridge": "intentional rejected fixture"}
        calls.append((task, condition))
        value = {"id": "offline-fixture", "model": "deepseek-flash", "status": "completed",
                 "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proof)}]}],
                 "usage": {"input_tokens": 1000, "output_tokens": 64, "total_tokens": 1064,
                           "output_tokens_details": {"reasoning_tokens": 16}}}
        return 200, "offline-fixture", canonical(value)

    result = run(args.output, "development", transport=transport, count_input=counting)
    assert result["stages"]["development"]["complete"], result
    assert all(t["status"] == "verified" for t in result["stages"]["development"]["generation"]["tasks"]), result
    assert len(calls) == 9 and result["stages"]["reserved"]["generation"]["calls"] == 0, result
    assert not result["ledger"]["provider_evidence"] and not result["held_out_effectiveness_claim"]
    summary = {"status": "passed", "verification": "actual isolated Lean",
               "generation_usage": "synthetic transport and input allowances; no provider calls",
               "reserved_solver_attempts": 0, "result": result}
    save_new(args.output / "offline-summary.json", summary)
    print(json.dumps({"status": "passed", "development_verified": 8, "fixture_generation_calls": len(calls),
                      "reserved_solver_attempts": 0, "provider_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
