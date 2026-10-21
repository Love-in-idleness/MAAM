#!/usr/bin/env python3
"""Replay metered baseline certificates through the frozen package comparison."""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from maam import CorpusError
from maam.baseline import inventory_baseline
from maam.migration import canonical, save_new, unseal
from maam.theory import digest, read_object
from scripts import control_model_baseline as model
from scripts import control_baseline_stability as stability
from scripts import measure_retained_portfolio as measurement


def model_inventory(model_root):
    root = Path(model_root).resolve()
    observed = model.report(root)
    if observed["status"] != "completed" or observed["generation_usage"] is None:
        raise CorpusError("comparison requires a completed, metered model pilot")
    initial = read_object(root / "search/inventory.json")
    plan = unseal(root / "search/plan.json")
    tasks = [row["task_id"] for row in initial["tasks"]]
    sessions = [row["root"] for row in initial["sessions"]]
    sessions += [str(root / "search" / row["path"]) for row in plan["sessions"]]
    inventory = inventory_baseline(sessions, tasks)
    selected = observed["search_report"]["tasks"]
    if len(selected) != len(inventory["tasks"]):
        raise CorpusError("model selections differ from the derived inventory")
    for row, choice in zip(inventory["tasks"], selected):
        witness = row["selected"]
        if (witness is None or row["task_id"] != choice["task_id"]
                or witness["proof_sha256"] != choice["proof_sha256"]
                or witness["proof_source_tokens"] != choice["proof_source_tokens"]):
            raise CorpusError("derived certificate differs from the metered model selection")
        # Retained incumbents are copied into the search; bind their bytes, not their directory names.
        for name in ("Proof.lean", "submission.json", "result.json"):
            if ((Path(witness["artifact"]) / name).read_bytes()
                    != (root / "search" / choice["artifact"] / name).read_bytes()):
                raise CorpusError("derived witness differs from the model-selected artifact")
    return observed, inventory


def build_report(model_root, exported_inventory_path, confirmation_root, treatment_root):
    model_root, inventory_path = Path(model_root).resolve(), Path(exported_inventory_path).resolve()
    confirmation_root = Path(confirmation_root).resolve()
    observed, inventory = model_inventory(model_root)
    if (canonical(read_object(inventory_path)) != canonical(inventory)
            or canonical(read_object(confirmation_root / "inventory.json")) != canonical(inventory)):
        raise CorpusError("export and confirmation must inherit the exact metered baseline inventory")
    confirmation, confirmed_inventory = stability._replay(confirmation_root)
    comparison = measurement.build_report(confirmation_root, treatment_root)
    if (comparison["inputs"]["baseline_inventory_sha256"] != digest(canonical(confirmed_inventory))
            or comparison["inputs"]["baseline_confirmation_sha256"] != digest(canonical(confirmation))
            or comparison["retained_portfolio"]["original_goal_source_ledger"]["baseline_tokens"]
            != confirmation["selected_source_tokens"]):
        raise CorpusError("comparison does not use the confirmed successor certificates")
    return {
        "schema_version": 1, "status": "measured_model_seeded_retained_portfolio",
        "inputs": {"model_root": str(model_root), "exported_inventory": str(inventory_path),
                   "baseline_root": str(confirmation_root),
                   "model_report_sha256": digest(canonical(observed)),
                   "exported_inventory_sha256": digest(canonical(inventory)),
                   "confirmation_report_sha256": digest(canonical(confirmation)),
                   "comparison_sha256": digest(canonical(comparison)),
                   "tool_sha256": {name: digest((REPO / name).read_bytes()) for name in (
                       "scripts/measure_model_portfolio.py", "scripts/control_model_baseline.py",
                       "scripts/measure_retained_portfolio.py", "scripts/control_baseline_stability.py")}},
        "baseline_generation_ledger": {
            "provider": observed["provider"], "requested_model": observed["requested_model"],
            "source_commit": observed["source_commit"], "latest_model_calls": observed["actual_provider_calls"],
            "latest_generation_usage": observed["generation_usage"],
            "latest_estimated_cost_usd": observed["estimated_cost_usd"],
            "exact_model_revision_verified": observed["exact_model_revision_verified"],
            "inherited_generation_usage": None, "inherited_generation_usage_status": "unknown",
            "before_model_source_tokens": observed["initial_source_tokens"],
            "after_model_source_tokens": observed["selected_source_tokens"],
            "after_confirmation_source_tokens": confirmation["selected_source_tokens"],
            "scope": "Known usage covers only the bound latest model pilot. Earlier inherited proof "
                     "generation remains unknown; this is not the total cost of constructing the baseline."},
        "comparison": comparison,
        "evidence": {"new_model_calls": 0, "fresh_lean_verification": False,
                     "metered_baseline_provenance_replayed": True,
                     "baseline_declared_method_scope_complete": True, "broad_baseline_prepared": False,
                     "historical_treatment_generation_usage": None, "fair_model_comparison": False,
                     "held_out_evaluation": False, "causal_theory_attribution": False,
                     "method_card_usability_measured": False, "training_eligible": False,
                     "scope": "Offline composition only. Prior generation and confirmation are separate "
                              "stages; this command neither generates nor checks new proofs. "
                              "The frozen nested comparison retains its original historical evidence labels."},
    }


def check_report(path, model_root, exported_inventory_path, confirmation_root, treatment_root):
    actual = build_report(model_root, exported_inventory_path, confirmation_root, treatment_root)
    if canonical(read_object(Path(path))) != canonical(actual):
        raise CorpusError("model-seeded comparison differs from current evidence or measurements")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--treatment-session", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    inputs = (args.model_root, args.inventory, args.baseline_root, args.treatment_session)
    try:
        if args.check:
            check_report(args.check, *inputs)
            result = {"status": "reproduced", "report": str(args.check)}
        else:
            value = build_report(*inputs)
            save_new(args.output, value)
            result = {"status": value["status"], "output": str(args.output),
                      "source_ledger": value["comparison"]["retained_portfolio"]["original_goal_source_ledger"]}
        print(json.dumps(result, ensure_ascii=False))
    except (CorpusError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
