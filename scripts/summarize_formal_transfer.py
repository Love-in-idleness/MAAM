#!/usr/bin/env python3
"""Replay one frozen comparison offline; earlier calibration contributes cost only."""
import argparse
from decimal import Decimal, localcontext
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam import CorpusError, generation, transfer
from maam.theory import digest


def total_costs(ledgers):
    known = all(not row["generation_calls"] or row["usage_complete"] for row in ledgers)
    totals = {field: sum(row[field] for row in ledgers) for field in (
        "generation_calls", "known_input_tokens_lower_bound", "known_output_tokens_lower_bound",
        "charged_input_tokens", "charged_output_tokens")}
    for kind in ("input", "output"):
        totals[kind + "_tokens"] = totals["known_" + kind + "_tokens_lower_bound"] if known else None
    fields = ("guarded_cost_usd", "known_guarded_cost_lower_bound_usd")
    with localcontext() as context:
        context.prec = max(28, sum(len(row[field]) for row in ledgers for field in fields) + 8)
        for field in fields:
            totals[field] = str(sum((Decimal(row[field]) for row in ledgers), Decimal(0)))
    totals.update(usage_complete=known, interrupted=any(row["interrupted"] for row in ledgers))
    return totals


def summarize(root, calibration_runs=()):
    root = Path(root).resolve()
    calibration_runs = [Path(path).resolve() for path in calibration_runs]
    if len({root, *calibration_runs}) != len(calibration_runs) + 1:
        raise CorpusError("provide distinct formal and calibration run roots")
    state = transfer.report(root)  # Authoritative sealed/raw replay; never runs Lean or HTTP.
    _, plan, loaded = transfer.load(root)
    stages = {}
    for phase in transfer.PHASES:
        stage = state["stages"][phase]
        stage_root, record = generation.load_run(root / "stages" / phase)
        calls = generation.call_records(stage_root, record)
        outcomes = {}
        for row in calls:
            pending, result, receipt = row["pending"], row["result"], row["receipt"]
            item = {"call_id": pending["call_id"],
                    "status": result["status"] if result else "interrupted",
                    "failure": result.get("feedback") if result else None,
                    "usage": receipt["usage"] if receipt else None,
                    "output_allowance": pending["allowance"]}
            outcomes.setdefault((pending["task_id"], pending["condition"]), []).append(item)
        generation_tasks = {(t["task_id"], t["condition"]): t for t in stage["generation"]["tasks"]}
        goals = []
        for task in stage["comparison"]["tasks"]:
            goal = {"task_id": task["id"], "family": task["family"]}
            for condition in ("baseline", "treatment"):
                generated = generation_tasks[(task["id"], condition)]
                selected = generated["selected"]
                goal[condition] = {"proof_status": task[condition],
                    "generation_status": generated["status"], "calls": generated["calls"],
                    "selected_source_cost": {key: selected[key] for key in (
                        "attempt", "proof_source_tokens", "package_source_tokens")} if selected else None,
                    "call_outcomes": outcomes.get((task["id"], condition), [])}
            goals.append(goal)
        stages[phase] = {"complete": stage["complete"], "goals": goals,
            "coverage": stage["comparison"]["coverage"],
            "common_task_source_ledger": stage["comparison"]["common_task_source_ledger"],
            "reported_models": stage["generation"]["reported_models"]}
    calibration = [{"root": str(path), "ledger": transfer.report(path)["ledger"]}
                   for path in calibration_runs]
    return {"schema_version": 1, "status": "offline_single_formal_run_summary",
        "root": str(root), "run_status": state["status"], "study_id": state["study_id"],
        "freeze_commit": plan["freeze_commit"],
        "plan_sha256": digest((root / "plan.json").read_bytes()),
        "protocol_sha256": loaded["fingerprints"]["protocol_sha256"],
        "config": loaded["manifest"]["config"], "formal_ledger": state["ledger"],
        "stages": stages, "stop": state["stop"], "calibration_cost_only": calibration,
        "cumulative_cost_only": total_costs([state["ledger"], *(r["ledger"] for r in calibration)]),
        "matched_allocations_complete": state["matched_allocations_complete"],
        "reserved_evaluation_started": bool(state["stages"]["reserved"]["generation"]["calls"]),
        "reserved_evaluation_completed": stages["reserved"]["complete"],
        "provider_evidence": state["ledger"]["provider_evidence"],
        "fair_model_performance_claim": False, "held_out_effectiveness_claim": False,
        "exact_model_revision_verified": False, "training_eligible": False,
        "limitations": "One frozen run; development and reserved proofs remain separate. "
            "Earlier runs contribute costs only, including failed calls; no cross-run proof selection. "
            "Each declared common solved set charges the full candidate once. "
            "Unknown usage stays unknown and retains its charged allowance. "
            "Model aliases do not verify a revision; local cost estimates are not invoices or account caps."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--calibration-run", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    try:
        summary = summarize(args.root, args.calibration_run)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps({"status": summary["status"], "run_status": summary["run_status"],
        "matched_allocations_complete": summary["matched_allocations_complete"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
