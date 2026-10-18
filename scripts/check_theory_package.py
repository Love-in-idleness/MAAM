#!/usr/bin/env python3
"""Require real Lean evidence and exercise invalid, well-typed alternatives."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam.theory import CORE_AXIOMS, load_experiment, run_experiment


def check_reference(report):
    assert report["status"] == "verified_reference_comparison", report
    assert report["comparison"]["search_performed"] is False
    assert report["comparison"]["held_out_evaluation"] is False
    for condition in ("baseline", "treatment"):
        audit = report["audits"][condition]
        assert set(audit["axioms_used"]) <= set(CORE_AXIOMS)
        assert all(t["goal_preserved"] for t in audit["targets"])
        assert all(t["source"]["body_tokens"] > 0 for t in audit["targets"])
    candidate_sources = report["audits"]["treatment"]["sources"]
    assert any(s["module"] == "Candidate" and s["source_tokens"] > 0 for s in candidate_sources)
    comparison = report["comparison"]
    assert comparison["source_ledger"]["treatment_including_package_tokens"] == sum(
        s["source_tokens"] for s in candidate_sources
    )
    assert comparison["training_eligibility"].startswith("reference demonstration")


def negative_cases():
    folder = ROOT / "experiments" / "hom_kernel"
    cases = {
        "admitted_proof": ("Treatment", "import Candidate\nnamespace Treatment\n"
                           "theorem kernelMul : Foundation.kernelMulGoal := by sorry\nend Treatment\n",
                           "forbidden axiom: sorryAx"),
        "changed_goal": ("Treatment", "import Candidate\nnamespace Treatment\n"
                         "theorem kernelMul : True := True.intro\nend Treatment\n",
                         "target proposition changed"),
        "extra_assumption": ("Treatment", "import Candidate\nnamespace Treatment\n"
                             "theorem kernelMul : False → Foundation.kernelMulGoal := fun h => False.elim h\n"
                             "end Treatment\n", "target proposition changed"),
        "unused_axiom": ("Candidate", (folder / "Candidate.lean").read_text() +
                         "\naxiom HiddenPackageAxiom : False\n", "forbidden axiom"),
        "hidden_import": ("Baseline", "import Lean\n" + (folder / "Baseline.lean").read_text(),
                          "forbidden imported module"),
        "unimported_charged_module": ("Unused", "axiom UnusedModuleAxiom : False\n",
                                      "experiment module not imported by entry: Unused"),
    }
    outcomes = {}
    for label, (module, source, expected) in cases.items():
        with tempfile.TemporaryDirectory(prefix="maam-negative-") as temp:
            work = Path(temp) / "experiment"
            shutil.copytree(folder, work)
            path = work / f"{module}.lean"
            path.write_text(source, encoding="utf-8")
            manifest = json.loads((work / "experiment.json").read_text())
            # Re-freeze deliberately changed input so the Lean audit, rather than
            # only the fingerprint guard, must detect the semantic violation.
            manifest["sources"][module] = {
                "path": f"{module}.lean", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            if module == "Unused":
                package_path = work / "package.json"
                package = json.loads(package_path.read_text())
                package["modules"].append(module)
                package_path.write_text(json.dumps(package))
            manifest_path = work / "experiment.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = run_experiment(manifest_path)
            assert report["status"] == "rejected", (label, report)
            assert expected in report["failure"]["message"], (label, report)
            assert report["comparison"] is None
            outcomes[label] = {
                "status": report["status"],
                "kind": report["failure"]["kind"],
                "stage": report["failure"]["stage"],
                "expected_diagnostic": expected,
                "matched": True,
            }
            print(f"Lean rejected {label}: {expected}", flush=True)
    return outcomes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--negative-output", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    check_reference(report)
    frozen = load_experiment(ROOT / "experiments" / "hom_kernel" / "experiment.json")
    assert report["fingerprints"] == frozen["fingerprints"], "reference report is stale"
    outcomes = negative_cases()
    Path(args.negative_output).write_text(json.dumps({
        "status": "passed",
        "kind": "actual_lean_rejection_cases",
        "cases": outcomes,
        "reference_fingerprints": frozen["fingerprints"],
    }, indent=2) + "\n")
    print("Reference report and all actual Lean rejection cases passed.")


if __name__ == "__main__":
    main()
