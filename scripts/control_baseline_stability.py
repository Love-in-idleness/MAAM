#!/usr/bin/env python3
"""Confirm bounded old-tool stability by composing frozen one-sweep executors."""

import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from maam import CorpusError, baseline_execution as execution, baseline_methods, baseline_search as search
from maam.baseline import inventory_baseline
from maam.migration import canonical, save_new, seal, session_lock, unseal
from maam.theory import digest, read_object

MAX_ROUNDS = 3
STABLE_ROUNDS = 2
POLICY = {"schema_version": 1, "evidence_mode": "supplied_local", "max_sweeps": 1,
          "stable_sweeps": 1, "methods": [
              {"name": name, "instructions": instructions}
              for name, instructions in baseline_methods.METHODS.items()]}


def _tools():
    return {**execution._tools(), "scripts/control_baseline_stability.py": digest(Path(__file__).read_bytes())}


def prepare(inventory_path, output):
    content = Path(inventory_path).read_bytes()
    inventory = json.loads(content.decode("utf-8"))
    tasks = [row["task_id"] for row in inventory["tasks"]]
    sessions = [row["root"] for row in inventory["sessions"]]
    if not 1 <= len(tasks) <= 2 or inventory["missing_tasks"]:
        raise CorpusError("stability confirmation requires one or two verified development goals")
    if canonical(inventory) != canonical(inventory_baseline(sessions, tasks)):
        raise CorpusError("initial inventory differs from its original evidence")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "inventory.json").write_bytes(content)
    plan = {"schema_version": 1, "max_rounds": MAX_ROUNDS, "stable_rounds": STABLE_ROUNDS,
            "policy": POLICY, "inventory_sha256": digest(content), "tool_sha256": _tools()}
    save_new(root / "plan.json", seal(plan))
    (root / "rounds").mkdir()
    with (root / "issued.jsonl").open("xb") as stream:
        stream.write(canonical(seal({"plan_sha256": digest(canonical(plan))})) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return report(root)


def _replay(output):
    root = Path(output).resolve()
    plan = unseal(root / "plan.json")
    if (set(plan) != {"schema_version", "max_rounds", "stable_rounds", "policy", "inventory_sha256", "tool_sha256"}
            or canonical([plan["schema_version"], plan["max_rounds"], plan["stable_rounds"], plan["policy"]])
            != canonical([1, MAX_ROUNDS, STABLE_ROUNDS, POLICY]) or plan["tool_sha256"] != _tools()
            or plan["inventory_sha256"] != digest((root / "inventory.json").read_bytes())):
        raise CorpusError("stability plan, tools or initial inventory changed")
    initial = read_object(root / "inventory.json")
    tasks = [row["task_id"] for row in initial["tasks"]]
    sessions = [row["root"] for row in initial["sessions"]]
    if not 1 <= len(tasks) <= 2 or initial["missing_tasks"]:
        raise CorpusError("invalid stability task scope")
    current = inventory_baseline(sessions, tasks)
    if canonical(current) != canonical(initial):
        raise CorpusError("initial evidence no longer replays")
    journal = [json.loads(line) for line in (root / "issued.jsonl").read_bytes().splitlines()]
    for row in journal:
        if not isinstance(row, dict):
            raise CorpusError("invalid stability journal")
        fingerprint = row.pop("seal_sha256", None)
        if fingerprint != digest(canonical(row)):
            raise CorpusError("stability journal changed")
    if (not journal or journal[0] != {"plan_sha256": digest(canonical(plan))}
            or len(journal) - 1 > MAX_ROUNDS):
        raise CorpusError("stability journal differs from the frozen plan")
    issued = journal[1:]
    if {path.name for path in (root / "rounds").iterdir()} - {f"{i:02d}" for i in range(1, len(issued) + 1)}:
        raise CorpusError("round evidence has no issued slot")

    rounds, stable, interrupted = [], 0, False
    for number, pending in enumerate(issued, 1):
        if interrupted or stable >= STABLE_ROUNDS:
            raise CorpusError("rounds continued after the stopping rule")
        if (set(pending) != {"round", "inventory_sha256"} or type(pending["round"]) is not int
                or pending["round"] != number or pending["inventory_sha256"] != digest(canonical(current))):
            raise CorpusError("round inventory or ordering differs from its predecessor")
        folder = root / "rounds" / f"{number:02d}"
        row = {"round": number, "status": "incomplete", "clean": False}
        required = [folder / "inventory.json", folder / "search/plan.json", folder / "execution/plan.json"]
        if not all(path.exists() for path in required):
            interrupted = True
        else:
            if (canonical(read_object(folder / "inventory.json")) != canonical(current)
                    or canonical(read_object(folder / "search/inventory.json")) != canonical(current)):
                raise CorpusError("round does not inherit the exact preceding inventory")
            search_plan = unseal(folder / "search/plan.json")
            execution_plan = unseal(folder / "execution/plan.json")
            schedule = [{"slot": method_index * len(tasks) + task_index + 1, "sweep": 1,
                         "method": method, "task_id": task,
                         "session": f"sessions/s01/m{method_index + 1:02d}"}
                        for method_index, method in enumerate(POLICY["methods"])
                        for task_index, task in enumerate(tasks)]
            incumbent = [[item["task_id"], item["selected"]["proof_sha256"],
                          item["selected"]["proof_source_tokens"]] for item in current["tasks"]]
            bound = [[item["task_id"], item["proof_sha256"], item["proof_source_tokens"]]
                     for item in search_plan["initial"]]
            if (canonical(search_plan["policy"]) != canonical(POLICY)
                    or canonical(search_plan["schedule"]) != canonical(schedule)
                    or canonical(bound) != canonical(incumbent)
                    or [item["path"] for item in search_plan["sessions"]]
                    != [f"sessions/s01/m{i + 1:02d}" for i in range(len(POLICY["methods"]))]
                    or execution_plan["search_root"] != str(folder / "search")):
                raise CorpusError("round task, method or execution binding changed")
            result, state = execution.report(folder / "execution"), search.report(folder / "search")
            row.update(status=result["status"], search_status=state["status"], counts=result["counts"],
                       initial_source_tokens=result["initial_source_tokens"],
                       selected_source_tokens=result["selected_source_tokens"])
            if result["status"] != "declared_methods_executed":
                interrupted = True
            else:
                sessions += [str(folder / "search" / item["path"]) for item in search_plan["sessions"]]
                updated = inventory_baseline(sessions, tasks)
                inherited = {item["task_id"]: [item["selected"]["proof_sha256"],
                             item["selected"]["proof_source_tokens"]] for item in updated["tasks"]}
                chosen = {item["task_id"]: [item["proof_sha256"], item["proof_source_tokens"]]
                          for item in state["tasks"]}
                if canonical(inherited) != canonical(chosen):
                    raise CorpusError("selected certificates differ at the round boundary")
                current = updated
                clean = (state["status"] == "declared_search_finished"
                         and result["counts"]["replacements"] == 0 and result["counts"]["rejected"] == 0
                         and result["counts"]["inconclusive"] == 0)
                row["clean"] = clean
                stable = stable + 1 if clean else 0
        if interrupted:
            stable = 0
        row["stable_rounds_after"] = stable
        rounds.append(row)

    complete = not interrupted and stable >= STABLE_ROUNDS
    status = ("interrupted_or_inconclusive" if interrupted else "declared_method_preparation_complete" if complete
              else "round_budget_exhausted" if len(issued) == MAX_ROUNDS else "in_progress")
    return {
        "schema_version": 1, "status": status, "stable_rounds": stable, "rounds": rounds,
        "max_rounds": MAX_ROUNDS, "required_stable_rounds": STABLE_ROUNDS,
        "task_ids": tasks, "methods": POLICY["methods"],
        "initial_source_tokens": sum(row["selected"]["proof_source_tokens"] for row in initial["tasks"]),
        "selected_source_tokens": sum(row["selected"]["proof_source_tokens"] for row in current["tasks"]),
        "selected_certificates": [{"task_id": row["task_id"], "proof_sha256": row["selected"]["proof_sha256"],
                                   "source_tokens": row["selected"]["proof_source_tokens"]} for row in current["tasks"]],
        "declared_method_preparation_complete": complete,
        "baseline_search_complete": False, "package_attribution_ready": False, "globally_shortest": False,
        "model_search_verified": False, "definition_optimization_performed": False,
        "generation_usage": None, "actual_provider_calls": 0,
        "plan_sha256": digest(canonical(plan)),
        "scope": "One or two development goals, two frozen source-pattern rewrites, at most three rounds; "
                 "two consecutive clean no-improvement rounds confirm only this declared scope. "
                 "Repeated deterministic scans are not independent statistical evidence. Definitions and "
                 "imports remain fixed; broad tool exhaustion, cognitive benefit and concept attribution are unknown.",
    }, current


def report(root):
    return _replay(root)[0]


def execute_round(output):
    root = Path(output).resolve()
    with session_lock(root):
        state, inventory = _replay(root)
        if state["status"] != "in_progress":
            raise CorpusError("no stability round available; incomplete work cannot be retried")
        number = len(state["rounds"]) + 1
        with (root / "issued.jsonl").open("r+b") as stream:
            stream.seek(0, 2)
            stream.write(canonical(seal({"round": number, "inventory_sha256": digest(canonical(inventory))})) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        folder = root / "rounds" / f"{number:02d}"
        folder.mkdir()
        save_new(folder / "inventory.json", inventory)
        search.prepare_search(folder / "inventory.json", POLICY, folder / "search")
        result = execution.prepare_execution(folder / "search", folder / "execution")
        while result["status"] == "in_progress":
            result = execution.execute_next(folder / "execution")
    return report(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "prepare" and args.inventory is None:
        parser.error("prepare requires --inventory")
    os.umask(0o077)
    try:
        result = prepare(args.inventory, args.root) if args.action == "prepare" else report(args.root)
        if args.action == "run":
            while result["status"] == "in_progress":
                result = execute_round(args.root)
        if args.output:
            save_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__, "message": str(exc)}))
        return 2
    return 2 if result["status"] in {"round_budget_exhausted", "interrupted_or_inconclusive"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
