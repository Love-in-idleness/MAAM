#!/usr/bin/env python3
"""Deterministic transport fixtures plus real Lean; never calls a model API."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.generation import prepare, run
from maam.migration import compare_sessions, save_new, session_report
from maam.theory import read_object


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args()
    suite = ROOT / "experiments/hom_kernel_migration/suite.json"
    proofs = read_object(suite.parent / "reference_proofs.json")["tasks"]["d01"]
    config = {"model": "deterministic-fixture-not-a-model", "sampling": {}, "budget": {
        "max_calls_per_task": 2, "max_output_tokens_per_call": 128,
        "max_output_tokens_per_task": 256, "request_timeout_seconds": 30}}
    prepare(suite, args.output, config, ["d01"])
    calls = []

    def fixture(payload, timeout):
        request = json.loads(payload["input"])["request"]
        condition = request["condition"]
        proof = proofs[condition]
        if not calls:
            proof = {"proof": "by sorry", "bridge": "deliberate rejected fixture"}
        calls.append(condition)
        response = {"id": f"fixture-{len(calls)}", "model": config["model"], "status": "completed",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proof)}]}],
                    "usage": {"input_tokens": 100, "output_tokens": 64, "total_tokens": 164,
                              "output_tokens_details": {"reasoning_tokens": 16}}}
        return 200, "fixture-request", json.dumps(response).encode()

    result = run(args.output, lean=args.lean, transport=fixture)
    assert calls == ["baseline", "baseline", "treatment"], calls
    assert all(t["status"] == "verified" for t in result["tasks"]), result
    assert result["usage_complete"] and not result["provider_usage_observed"]
    baseline = session_report(args.output / "baseline")["tasks"][0]
    assert [a["status"] for a in baseline["attempts"]] == ["rejected", "verified"], baseline
    assert "sorryAx" in baseline["attempts"][0]["failure"]["message"], baseline
    comparison = compare_sessions(args.output / "baseline", args.output / "treatment")
    summary = {"status": "passed", "transport": "injected_test_transport",
               "generation_usage": "synthetic fixture values; no provider usage observed",
               "lean": "actual pinned Lean compilation and audits",
               "result": result, "comparison": comparison}
    save_new(args.output / "smoke-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
