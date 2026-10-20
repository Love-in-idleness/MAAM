#!/usr/bin/env python3
"""Offline finite-rule example separating old-tool cleanup from package value."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.attribution import source_attribution
from maam.migration import save_new
from maam.proofs import ProofSystem


def check():
    # Tree-node lengths here demonstrate the identity, not measured Lean source.
    data = {"schema_version": 1, "system_id": "baseline-attribution-control-v1",
            "statement_lengths": {"A": 1, "L": 1, "G": 1}, "axioms": ["A"],
            "rules": [{"id": "historical-long", "conclusion": "G", "premises": ["A"] * 99},
                      {"id": "existing-short", "conclusion": "G", "premises": ["A"] * 39},
                      {"id": "build-lemma", "conclusion": "L", "premises": ["A"] * 19},
                      {"id": "use-lemma", "conclusion": "G", "premises": ["L"] * 34}]}
    system = ProofSystem(data)
    old, _ = system.solve()
    augmented, _ = system.solve(reusable="L")
    historical = 1 + 99 * old["A"]
    assert (historical, old["G"], old["L"], augmented["G"]) == (100, 40, 20, 35)
    gain = system.reuse_gain("L", ["G"])
    assert gain["net_savings"] == -15
    # The algebra also applies to tree-node costs; do not label this as source data.
    parts = source_attribution(historical=historical, prepared=old["G"], control=old["G"],
                               treatment=augmented["G"], package=old["L"])
    parts["unit"] = "finite_tree_statement_length_units"
    assert parts["historical_net_saving"] == 45
    assert parts["old_tool_preparation_saving"] == 60
    assert parts["package_associated_net_difference"] == -15
    return {"status": "passed", "proof_system": data, "attribution": parts,
            "baseline_optimality": "exact only in supplied finite tree-proof graph",
            "rule_correctness": "supplied by caller; not checked by Lean",
            "provider_calls": 0, "scope": "Synthetic arithmetic/control test; not a model outcome, "
                "Lean source measurement or globally shortest mathematical proof."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = check()
        save_new(args.output, result)
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps({"status": result["status"], "output": str(args.output), "provider_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
