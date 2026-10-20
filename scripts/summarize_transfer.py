#!/usr/bin/env python3
"""Replay separate transfer runs offline and retain their distinct contexts."""
import argparse
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam import CorpusError, transfer
from maam.theory import digest


def ceiling_value(value):
    if not isinstance(value, (str, Decimal)):
        raise CorpusError("aggregate ceiling must be a finite positive decimal")
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CorpusError("aggregate ceiling must be a finite positive decimal") from exc
    if not number.is_finite() or number <= 0:
        raise CorpusError("aggregate ceiling must be a finite positive decimal")
    return number


def summarize(roots, ceiling_usd="1.00"):
    ceiling = ceiling_value(ceiling_usd)
    roots = [Path(root).resolve() for root in roots]
    if not roots or len(set(roots)) != len(roots):
        raise CorpusError("provide distinct transfer run roots")
    runs, goals, packages, fingerprints = [], {}, set(), None
    for index, root in enumerate(roots):
        state = transfer.report(root)  # Replays sealed records and original raw responses.
        _, plan, loaded = transfer.load(root)
        current = loaded["frozen"]["fingerprints"]
        if fingerprints is not None and current != fingerprints:
            raise CorpusError("cannot aggregate different frozen suites or source fingerprints")
        fingerprints = current
        spec = loaded["manifest"]
        runs.append({"root": str(root), "plan_sha256": digest((root / "plan.json").read_bytes()),
                     "protocol_sha256": loaded["fingerprints"]["protocol_sha256"],
                     "freeze_commit": plan["freeze_commit"], "config": spec["config"],
                     "task_order": spec["task_order"], "experiment_budget": spec["experiment_budget"],
                     "schedules": {phase: [{"task_id": t["task_id"], "condition": t["condition"]}
                         for t in state["stages"][phase]["generation"].get("tasks", [])]
                         for phase in ("development", "reserved")},
                     "report": state})
        for task in state["stages"]["development"]["generation"]["tasks"]:
            selected = task["selected"]
            if selected:
                for field in ("proof_source_tokens", "package_source_tokens"):
                    if type(selected[field]) is not int or selected[field] < 0:
                        raise CorpusError("selected source costs must be nonnegative integers")
                if task["condition"] == "treatment":
                    packages.add(selected["package_source_tokens"])
                elif selected["package_source_tokens"] != 0:
                    raise CorpusError("baseline must not charge candidate source")
            row = goals.setdefault(task["task_id"], {"observations": [], "selected": {}})
            observation = {"run_index": index, "condition": task["condition"],
                           "status": task["status"], "calls": task["calls"], "selected": selected}
            if selected:
                observation["artifact"] = str(root / "stages/development" / task["condition"] /
                    "attempts" / task["task_id"] / f"{selected['attempt']:03d}")
            row["observations"].append(observation)
            if selected:
                previous = row["selected"].get(task["condition"])
                if previous is None or selected["proof_source_tokens"] < previous["selected"]["proof_source_tokens"]:
                    row["selected"][task["condition"]] = observation
    if len(packages) > 1:
        raise CorpusError("candidate package source cost differs across retained proofs")
    common = sorted(task for task, row in goals.items()
                    if set(row["selected"]) == {"baseline", "treatment"})
    package = next(iter(packages)) if common else None
    baseline = sum(goals[t]["selected"]["baseline"]["selected"]["proof_source_tokens"] for t in common)
    treatment = sum(goals[t]["selected"]["treatment"]["selected"]["proof_source_tokens"] for t in common)
    ledgers = [run["report"]["ledger"] for run in runs]
    known = all(not row["generation_calls"] or row["usage_complete"] for row in ledgers)
    totals = {field: sum(row[field] for row in ledgers) for field in (
        "generation_calls", "known_input_tokens_lower_bound", "known_output_tokens_lower_bound",
        "charged_input_tokens", "charged_output_tokens")}
    for kind in ("input", "output"):
        totals[kind + "_tokens"] = totals["known_" + kind + "_tokens_lower_bound"] if known else None
    money_fields = ("guarded_cost_usd", "known_guarded_cost_lower_bound_usd")
    with localcontext() as context:
        context.prec = max(28, sum(len(row[field]) for row in ledgers for field in money_fields) + 8)
        for field in money_fields:
            totals[field] = str(sum((Decimal(row[field]) for row in ledgers), Decimal(0)))
    totals.update(usage_complete=known,
                  reserved_generation_calls=sum(run["report"]["stages"]["reserved"]["generation"]["calls"] for run in runs),
                  interrupted=any(row["interrupted"] for row in ledgers),
                  violations=[{"run_index": i, "violations": row["violations"]}
                              for i, row in enumerate(ledgers) if row["violations"]])
    return {"schema_version": 1, "status": "offline_cross_protocol_summary",
            "source_fingerprints": fingerprints, "runs": runs, "totals": totals,
            "aggregate_cost_ceiling_usd": str(ceiling),
            "within_cost_ceiling": Decimal(totals["guarded_cost_usd"]) <= ceiling,
            "development_goals": goals,
            "common_task_source_ledger": {"task_ids": common,
                "baseline_tokens": baseline if common else None,
                "treatment_including_package_tokens": treatment + package if common else None,
                "package_tokens_charged_once": package,
                "net_tokens_saved": baseline - treatment - package if common else None,
                "selection": "best observed full proof-module cost per condition across distinct protocols",
                "scope": "development common solved tasks only; whole candidate charged once"},
            "fair_model_performance_claim": False, "held_out_evaluation": False,
            "held_out_effectiveness_claim": False, "matched_allocations_complete": False,
            "exact_model_revision_verified": False, "training_eligible": False,
            "limitations": "Separate adaptive calibration contexts, not one completed comparison; all failed calls charged. "
                           "Frozen local cost estimates are not invoices, account caps or exact tokenizer guarantees."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ceiling-usd", default="1.00")
    args = parser.parse_args(argv)
    try:
        summary = summarize(args.run, args.ceiling_usd)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__}))
        return 2
    print(json.dumps({"status": summary["status"], "output": str(args.output),
                      "within_cost_ceiling": summary["within_cost_ceiling"], "totals": summary["totals"]}))
    return 0 if summary["within_cost_ceiling"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
