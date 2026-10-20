#!/usr/bin/env python3
"""Local supplied-proof workflow check with real isolated Lean and no API."""
import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from maam.baseline import inventory_baseline
from maam.baseline_search import next_request, prepare_search, report, submit
from maam.migration import save_new, start_session, submit_attempt, task_request
from maam.theory import CORE_AXIOMS, digest

SHORT = "by\n  exact True.intro"
PADDED = "by\n  have fixture_padding : True := True.intro\n  exact True.intro"


def fixture(root):
    root.mkdir()
    sources = {
        "Base": "namespace Foundation\ndef toy : Prop := True\nend Foundation\n",
        "Candidate": "import Base\nnamespace Theory\ntheorem unused : True := True.intro\nend Theory\n",
        "Tasks.Toy": "import Base\nnamespace Tasks\ndef toy : Prop := Foundation.toy\nend Tasks\n"}
    descriptors = {}
    for module, source in sources.items():
        path = Path(*module.split(".")).with_suffix(".lean")
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        descriptors[module] = {"path": str(path), "sha256": digest(source.encode())}
    # Existing migration format requires package metadata; it is unavailable to
    # baseline requests and is never compiled or used by these fixture proofs.
    save_new(root / "package.json", {"schema_version": 1, "package_id": "unused-fixture",
        "base_id": "baseline-fixture", "status": "proved_extension", "modules": ["Candidate"],
        "declarations": ["Theory.unused"], "conjectures": []})
    save_new(root / "suite.json", {"schema_version": 1, "suite_id": "baseline-search-smoke",
        "phase": "migration_calibration", "lean_version": "4.24.0", "package": "package.json",
        "base": {"id": "baseline-fixture", "modules": ["Base"],
                 "allowed_core_prefixes": ["Init"], "allowed_axioms": CORE_AXIOMS},
        "sources": descriptors, "tasks": [{"id": "toy", "split": "development",
            "family": "workflow_fixture", "module": "Tasks.Toy", "goal": "Tasks.toy"}],
        "budget": {"max_attempts_per_task": 2, "max_proof_bytes": 8192,
            "max_heartbeats": 100000, "per_command_timeout_seconds": 30,
            "per_attempt_timeout_seconds": 120}})
    return root / "suite.json"


def response(root, **value):
    request = next_request(root)
    assert request is not None
    assert [s["module"] for s in request["inner_request"]["sources"]] == ["Base", "Tasks.Toy"]
    return submit(root, {"request_sha256": request["request_sha256"], **value})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = fixture(output / "fixture")
    seed = output / "seed"
    start_session(suite, seed, condition="baseline", solver_id="supplied-workflow-fixture",
                  mode="supplied_reference")
    request = task_request(seed, "toy")
    checked = submit_attempt(seed, {"task_id": "toy", "request_sha256": request["request_sha256"],
        "proof": PADDED, "bridge": "Synthetic padding for strict-shorter controller check only."},
        lean=str(REPO / "scripts/lean_sandbox.py"))
    assert checked["status"] == "verified", checked.get("failure")
    inventory = output / "inventory.json"
    save_new(inventory, inventory_baseline([seed], ["toy"]))
    policy = {"schema_version": 1, "evidence_mode": "supplied_local", "max_sweeps": 3,
        "stable_sweeps": 2, "methods": [{"name": "remove_fixture_padding",
            "instructions": "Controlled workflow fixture; supplied responses are not model search."}]}
    save_new(output / "policy.json", policy)
    root = output / "search"
    prepare_search(inventory, policy, root)
    initial = report(root)
    first = response(root, action="candidate", proof=SHORT, bridge="Remove synthetic unused padding.")
    assert first["selected_source_tokens"] < initial["selected_source_tokens"]
    assert first["stable_sweeps"] == 0
    second = response(root, action="candidate", proof=PADDED, bridge="Deliberately longer valid fixture.")
    assert second["selected_source_tokens"] == first["selected_source_tokens"]
    assert second["stable_sweeps"] == 1
    final = response(root, action="retain", reason="Retain the checked shorter fixture proof.")
    assert final["status"] == "declared_search_finished", final
    assert final["stable_sweeps"] == 2 and final["completed_sweeps"] == 3
    assert next_request(root) is None and report(root) == final

    badroot = output / "rejection-search"
    prepare_search(inventory, {**policy, "max_sweeps": 1, "stable_sweeps": 1}, badroot)
    rejected = response(badroot, action="candidate", proof="by sorry", bridge="Intentional invalid fixture.")
    assert rejected["status"] == "sweep_budget_exhausted", rejected
    assert rejected["stable_sweeps"] == 0
    assert rejected["selected_source_tokens"] == initial["selected_source_tokens"]
    for state in (final, rejected):
        assert not state["baseline_search_complete"] and not state["package_attribution_ready"]
        assert not state["globally_shortest"] and not state["model_search_verified"]
        assert state["generation_usage"] is None and state["actual_provider_calls"] == 0
    save_new(output / "summary.json", {"status": "passed", "verification": "actual isolated Lean 4.24.0",
        "lean_checks": 4, "provider_calls": 0, "generation_usage": None,
        "scope": "Supplied synthetic proofs validate workflow controls, not model search or package value.",
        "completed_case": final, "rejected_case": rejected})
    print(json.dumps({"status": "passed", "lean_checks": 4, "provider_calls": 0,
        "completed_sweeps": final["completed_sweeps"], "stable_sweeps": final["stable_sweeps"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
