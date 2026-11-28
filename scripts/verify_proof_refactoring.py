#!/usr/bin/env python3
"""Compare a fresh Lean run with the published proof-refactoring evidence."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results/proof-refactoring-v1.json"
WITNESSES = ROOT / "results/proof-refactoring-v1"


def check(workdir):
    workdir = Path(workdir)
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    actual = json.loads((workdir / "report.json").read_text(encoding="utf-8"))
    for field in ("status", "input_fingerprints", "archive_sha256", "archive_receipts", "evaluators",
                  "preparation_sha256", "continuation_from", "shared_proposals", "cohorts", "routes", "scope"):
        if actual[field] != reference[field]:
            raise ValueError(f"replay differs in {field}")
    for label, expected in reference["attempts"].items():
        result = actual["attempts"][label]
        for field in ("status", "identity", "audit_sha256", "inventory_sha256", "shared_dependencies",
                      "candidate_dependencies", "lean_commands"):
            if result.get(field) != expected.get(field):
                raise ValueError(f"replay differs in {label}.{field}")
    attempts = actual["attempts"]
    if attempts["archive-v2-without-package"]["status"] != "rejected":
        raise ValueError("proofs with real candidate dependencies unexpectedly passed without the package")
    for operation in ("compact", "reprove"):
        detached = attempts[f"treatment-{operation}-without-package"]
        if detached["status"] != "verified" or detached["identity"] != attempts[f"control-{operation}"]["identity"]:
            raise ValueError("package-free replay does not match the old-tool proof")
    shared = attempts["control-reprove"]["shared_dependencies"]
    if sum(bool(paths) for paths in shared.values()) != 4:
        raise ValueError("at least one verified original goal did not reach a shared lemma")
    sources = ["RefactorShared.lean", *(f"RefactorProofs/{tid}.lean" for tid in actual["tasks"])]
    for name in sources:
        if (workdir / "control-reprove" / name).read_bytes() != (WITNESSES / name).read_bytes():
            raise ValueError(f"checked-in proof differs from replay: {name}")
    print(f"Replayed {len(attempts)} records and {len(actual['cohorts'])} target sets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    check(parser.parse_args().workdir)
