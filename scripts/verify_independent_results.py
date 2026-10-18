#!/usr/bin/env python3
"""Reconstruct the independent-context cohort from complete archived records."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.independent import restore_archive
from maam.theory import digest, read_object


def verify():
    archive = ROOT / "results/independent"
    receipt = read_object(archive / "receipt.json")
    assert receipt["status"] in {"local_verified_pending_clean_replay", "verified_clean_replay"}
    for name, expected in receipt["reports_sha256"].items():
        assert digest((archive / name).read_bytes()) == expected, name
    assert receipt["controller_sha256"] == digest((ROOT / "maam/independent.py").read_bytes())
    assert receipt["replay_runner_sha256"] == digest((ROOT / "scripts/check_independent.py").read_bytes())
    with tempfile.TemporaryDirectory() as temp:
        summary = restore_archive(archive, Path(temp) / "run")
    assert summary["status"] == "completed" and summary["registered_workers"] == 40
    assert summary["freeze_commit"] == receipt["freeze_commit"]
    assert summary["attempts"] == receipt["original_attempts"]
    assert summary["scope"]["generation_budget_verified"] is False
    assert summary["scope"]["held_out_evaluation"] is False
    assert summary["scope"]["training_eligible"] is False
    assert summary["scope"]["fair_model_performance_claim"] is False
    if receipt["status"] == "verified_clean_replay":
        validation = read_object(archive / "validation.json")
        assert receipt["workflow_conclusion"] == "success"
        assert validation["status"] == "passed" and validation["attempts"] == summary["attempts"]
        assert all(c["matched"] for c in validation["cases"])
        assert validation["original_summary_sha256"] == digest((archive / "summary.json").read_bytes())
        assert validation["original_scope"] == summary["scope"]
        assert sum(c["original_infrastructure_failure"] for c in validation["cases"]) == len(summary["infrastructure_failures"])
    print("Independent-context cohort: complete original requests, prompts, attempts, feedback and cost inventories replayed; generation-budget limits remain explicit.")


if __name__ == "__main__":
    verify()
