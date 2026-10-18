#!/usr/bin/env python3
"""Replay archived whole-package ledgers and exact finite portfolio frontiers."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maam.ablation import analyse_variants, load_study
from maam.theory import digest


def verify():
    folder=ROOT/"results/ablation"
    receipt=json.loads((folder/"receipt.json").read_text())
    assert receipt["status"]=="verified" and receipt["workflow_conclusion"]=="success"
    for filename,expected in receipt["reports_sha256"].items():
        assert digest((folder/filename).read_bytes())==expected,filename
    study=load_study(ROOT/"experiments/hom_kernel_ablation/study.json")
    variants=[json.loads((folder/(v["variant"]["id"]+".json")).read_text()) for v in study["loaded"]]
    comparison=json.loads((folder/"comparison.json").read_text())
    assert analyse_variants(study,variants)==comparison
    assert comparison["fingerprints"]==study["fingerprints"]
    assert comparison["held_out_evaluation"] is False and comparison["training_eligible"] is False
    assert comparison["protocol"]["search_performed"] is False
    assert len(comparison["common_measured_tasks"])==20
    assert sum(v["verified_attempts"] for v in comparison["coverage"].values())==140
    assert sum(v["measured_attempts"] for v in comparison["coverage"].values())==140
    assert all(f["status"]=="exact_finite_portfolio" for f in comparison["frontiers"].values())
    for provenance in comparison["provenance"].values():
        assert provenance["code_commit"]==receipt["implementation_commit"]
        assert provenance["workflow_run_id"]==str(receipt["workflow_run_id"])
    checks=json.loads((folder/"validation.json").read_text())
    assert checks["status"]=="passed" and checks["verified_attempts"]==checks["measured_attempts"]==140
    assert checks["study_fingerprints"]==study["fingerprints"]
    assert len(checks["cases"])==receipt["control_cases"]==3
    assert all(c["matched"] for c in checks["cases"].values())
    assert receipt["runner_sha256"]==digest((ROOT/"scripts/check_ablation.py").read_bytes())
    print("M3 archived 140 verified/inventoried proofs, complete package costs and finite Pareto frontiers replayed.")


if __name__=="__main__":verify()
