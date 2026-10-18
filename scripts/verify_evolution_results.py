#!/usr/bin/env python3
"""Restore complete version/reuse evidence and check its receipt, without Lean."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.evolution import restore_archive
from maam.theory import digest, read_object


def verify():
    archive = ROOT / "results/evolution"
    receipt = read_object(archive / "receipt.json")
    for name, expected in receipt["reports_sha256"].items():
        assert digest((archive / name).read_bytes()) == expected, name
    assert receipt["runner_sha256"] == digest((ROOT / "scripts/check_evolution.py").read_bytes())
    with tempfile.TemporaryDirectory() as temp:
        summary = restore_archive(archive, Path(temp) / "run")
    assert summary["status"] == "completed" and summary["registered_workers"] == 12
    assert receipt["attempts"] == summary["attempts"]
    assert receipt["freeze_commit"] == summary["freeze_commit"]
    assert all(value is False for value in summary["scope"].values())
    if receipt["status"] == "verified_clean_replay":
        validation = read_object(archive / "validation.json")
        assert receipt["workflow_conclusion"] == "success"
        assert validation["status"] == "passed" and validation["attempts"] == summary["attempts"]
        assert validation["summary_sha256"] == digest((archive / "summary.json").read_bytes())
        assert all(c["matched"] for c in validation["cases"])
    else:
        assert receipt["status"] == "local_verified_pending_clean_replay"
    print("Package ancestry, complete attempts, costs and later-use paths replayed; generation usage remains unknown.")
    return summary


if __name__ == "__main__":
    verify()
