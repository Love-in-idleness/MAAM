"""Small supplied-local searches over existing tools; no generation transport."""
from pathlib import Path
import json
import os
import re
import shutil

from .baseline import inventory_baseline
from .corpus import CorpusError
from .migration import (canonical, load_session, proof_source, save_new, seal, session_lock,
                        session_report, start_session, submit_attempt, task_request, unseal)
from .theory import digest, read_object

REPO = Path(__file__).resolve().parents[1]
TOOLS = ("maam/baseline_search.py", "maam/baseline.py", "maam/migration.py",
         "maam/theory.py", "maam/PackageCheck.lean", "scripts/lean_sandbox.py",
         "scripts/control_baseline_search.py")


def _policy(value):
    if (not isinstance(value, dict) or set(value) != {"schema_version", "methods",
            "max_sweeps", "stable_sweeps", "evidence_mode"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["evidence_mode"] != "supplied_local"
            or type(value["max_sweeps"]) is not int or not 1 <= value["max_sweeps"] <= 4
            or type(value["stable_sweeps"]) is not int
            or not 1 <= value["stable_sweeps"] <= value["max_sweeps"]
            or not isinstance(value["methods"], list) or not 1 <= len(value["methods"]) <= 3):
        raise CorpusError("invalid bounded supplied-local search policy")
    names = []
    for method in value["methods"]:
        if (not isinstance(method, dict) or set(method) != {"name", "instructions"}
                or not isinstance(method["name"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_]*", method["name"])
                or not isinstance(method["instructions"], str) or not method["instructions"].strip()):
            raise CorpusError("methods need distinct safe names and nonempty instructions")
        names.append(method["name"])
    if len(set(names)) != len(names):
        raise CorpusError("duplicate search method")
    return value


def _files(folder):
    files = {}
    for path in Path(folder).rglob("*"):
        if path.is_symlink():
            raise CorpusError("search evidence must not contain symbolic links")
        if path.is_file():
            files[str(path.relative_to(folder))] = digest(path.read_bytes())
    return dict(sorted(files.items()))


def prepare_search(inventory_path, policy, output):
    policy = _policy(policy)
    inventory_path = Path(inventory_path)
    inventory = read_object(inventory_path)
    sessions = [row["root"] for row in inventory["sessions"]]
    tasks = [row["task_id"] for row in inventory["tasks"]]
    if inventory_baseline(sessions, tasks) != inventory:
        raise CorpusError("baseline inventory no longer matches its source evidence")
    if inventory["missing_tasks"] or any(row["selected"] is None for row in inventory["tasks"]):
        raise CorpusError("search requires a verified incumbent for every task")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "inventory.json").write_bytes(inventory_path.read_bytes())
    source_snapshot = Path(sessions[0]) / "snapshot"
    _files(source_snapshot)
    shutil.copytree(source_snapshot, root / "snapshot")
    initial = []
    for row in inventory["tasks"]:
        selected = row["selected"]
        relative = "incumbents/" + row["task_id"]
        _files(Path(selected["artifact"]))
        shutil.copytree(selected["artifact"], root / relative)
        initial.append({"task_id": row["task_id"], "artifact": relative,
                        "proof_source_tokens": selected["proof_source_tokens"],
                        "proof_sha256": selected["proof_sha256"],
                        "files": _files(root / relative)})
    session_rows, schedule = [], []
    for sweep in range(1, policy["max_sweeps"] + 1):
        for number, method in enumerate(policy["methods"], 1):
            relative = f"sessions/s{sweep:02d}/m{number:02d}"
            start_session(root / "snapshot/suite.json", root / relative, condition="baseline",
                          solver_id="baseline-search-supplied-local-v1", mode="supplied_reference")
            session_rows.append({"path": relative,
                "session_sha256": digest((root / relative / "session.json").read_bytes())})
            for task in tasks:
                schedule.append({"slot": len(schedule) + 1, "sweep": sweep,
                                 "method": method, "task_id": task, "session": relative})
    (root / "reservations").mkdir()
    (root / "attempts").mkdir()
    plan = {"schema_version": 1, "policy": policy, "initial": initial,
            "knowledge_sha256": inventory["knowledge_sha256"],
            "source_metric_sha256": inventory["source_metric_sha256"],
            "inventory_sha256": digest((root / "inventory.json").read_bytes()),
            "snapshot_files": _files(root / "snapshot"), "sessions": session_rows,
            "schedule": schedule, "tool_sha256": {p: digest((REPO / p).read_bytes()) for p in TOOLS}}
    save_new(root / "plan.json", seal(plan))
    with (root / "issued.jsonl").open("xb") as journal:
        journal.write(canonical(seal({"schema_version": 1, "plan_sha256": digest(canonical(plan))})) + b"\n")
    return report(root)


def _load(root):
    root = Path(root).resolve()
    plan = unseal(root / "plan.json")
    _policy(plan["policy"])
    if (plan["tool_sha256"] != {p: digest((REPO / p).read_bytes()) for p in TOOLS}
            or plan["snapshot_files"] != _files(root / "snapshot")
            or plan["inventory_sha256"] != digest((root / "inventory.json").read_bytes())):
        raise CorpusError("search tools, snapshot or inventory changed")
    for item in plan["initial"]:
        if item["files"] != _files(root / item["artifact"]):
            raise CorpusError("initial incumbent evidence changed")
    for item in plan["sessions"]:
        if item["session_sha256"] != digest((root / item["path"] / "session.json").read_bytes()):
            raise CorpusError("search session changed")
        load_session(root / item["path"])
    return root, plan


def _request(root, plan, slot, selected):
    incumbent = selected[slot["task_id"]]
    artifact = root / incumbent["artifact"]
    response = read_object(artifact / "submission.json")
    value = {"schema_version": 1, "slot": slot["slot"], "sweep": slot["sweep"],
        "method": slot["method"], "task_id": slot["task_id"],
        "plan_sha256": digest(canonical(plan)), "policy_sha256": digest(canonical(plan["policy"])),
        "knowledge_sha256": plan["knowledge_sha256"], "source_metric_sha256": plan["source_metric_sha256"],
        "inner_request": task_request(root / slot["session"], slot["task_id"]),
        "incumbent": {"proof": response["proof"], "proof_source_sha256": incumbent["proof_sha256"],
                      "proof_source_tokens": incumbent["proof_source_tokens"]},
        "contract": "Use existing task-local sources only; retain the incumbent or supply a shorter proof. "
                    "Definitions, imports and goals stay unchanged; all helper source is charged.",
        "provenance": "supplied_local; no model transport or independently metered generation"}
    return {**value, "request_sha256": digest(canonical(value))}


def _response(value):
    if not isinstance(value, dict):
        raise CorpusError("search response must be an object")
    fields = ({"action", "request_sha256", "proof", "bridge"} if value.get("action") == "candidate"
              else {"action", "request_sha256", "reason"} if value.get("action") == "retain" else set())
    if not fields or set(value) != fields or any(not isinstance(value[k], str) or not value[k].strip()
                                               for k in fields):
        raise CorpusError("invalid search response fields")
    return value


def _inner_submission(request, response):
    return {"task_id": request["task_id"],
        "request_sha256": request["inner_request"]["request_sha256"],
        "proof": response["proof"], "bridge": response["bridge"],
        "generation": {"provenance": "supplied_local", "usage": None,
                       "outer_request_sha256": request["request_sha256"]}}


def _issued(root, plan):
    try:
        lines = (root / "issued.jsonl").read_bytes().splitlines()
        rows = [json.loads(line) for line in lines]
    except (OSError, ValueError) as exc:
        raise CorpusError("issued-slot journal is missing or unreadable") from exc
    for row in rows:
        if not isinstance(row, dict):
            raise CorpusError("invalid issued-slot journal")
        fingerprint = row.pop("seal_sha256", None)
        if fingerprint != digest(canonical(row)):
            raise CorpusError("issued-slot journal fingerprint changed")
    if (not rows or rows[0] != {"schema_version": 1, "plan_sha256": digest(canonical(plan))}
            or len(rows) - 1 > len(plan["schedule"])):
        raise CorpusError("issued-slot journal belongs to another plan")
    for number, row in enumerate(rows[1:], 1):
        if set(row) != {"slot", "request_sha256", "response_sha256"} or row["slot"] != number:
            raise CorpusError("issued slots are not contiguous")
    return rows[1:]


def _state(root):
    root, plan = _load(root)
    issued = _issued(root, plan)
    reservations = sorted((root / "reservations").glob("*.json"))
    expected_dirs = {f"{i:04d}" for i in range(1, len(issued) + 1)}
    if {p.stem for p in reservations} - expected_dirs:
        raise CorpusError("search reservation has no issued slot")
    if {p.name for p in (root / "attempts").iterdir()} - expected_dirs:
        raise CorpusError("search attempt has no reservation")
    inner = {}
    for item in plan["sessions"]:
        for task in session_report(root / item["path"])["tasks"]:
            if len(task["attempts"]) > 1:
                raise CorpusError("search session contains duplicate task attempts")
            if task["attempts"]:
                inner[(item["path"], task["id"])] = (task["attempts"][0], task["selected"])
    allowed = {(s["session"], s["task_id"]) for s in plan["schedule"][:len(issued)]}
    if set(inner) - allowed:
        raise CorpusError("inner attempt has no outer reservation")
    selected = {row["task_id"]: dict(row) for row in plan["initial"]}
    attempts, replacements = [], []
    completed = stable = 0
    sweep_clean, sweep_improved, interrupted = True, False, False
    sweep_size = len(plan["initial"]) * len(plan["policy"]["methods"])
    for index, pending in enumerate(issued):
        if interrupted or stable >= plan["policy"]["stable_sweeps"]:
            raise CorpusError("search continued after its stopping rule")
        slot = plan["schedule"][index]
        request = _request(root, plan, slot, selected)
        path = root / "reservations" / f"{index + 1:04d}.json"
        reservation_present = path.exists()
        if reservation_present and unseal(path) != pending:
            raise CorpusError("outer reservation differs from its issued slot")
        if (set(pending) != {"slot", "request_sha256", "response_sha256"}
                or pending["slot"] != slot["slot"]
                or pending["request_sha256"] != request["request_sha256"]):
            raise CorpusError("outer reservation belongs to a stale or different request")
        artifact = root / "attempts" / f"{index + 1:04d}"
        key = (slot["session"], slot["task_id"])
        row = {"slot": slot["slot"], "sweep": slot["sweep"], "task_id": slot["task_id"],
               "method": slot["method"]["name"], "status": "incomplete", "replaced": False}
        response = None
        if (artifact / "response.json").exists():
            response = _response(read_object(artifact / "response.json"))
            if (digest(canonical(response)) != pending["response_sha256"]
                    or response["request_sha256"] != request["request_sha256"]):
                raise CorpusError("outer response changed or belongs to another request")
        if key in inner:
            if response is None or response["action"] != "candidate":
                raise CorpusError("inner attempt was not authorized by its response")
            inner_artifact = root / slot["session"] / inner[key][0]["artifact"]
            expected = _inner_submission(request, response)
            inner_pending = unseal(root / slot["session"] / "reservations" / f"{slot['task_id']}-001.json")
            expected_source = proof_source(request["inner_request"], response["proof"]).encode()
            if (inner_pending["submission_sha256"] != digest(canonical(expected))
                    or inner_pending["proof_sha256"] != digest(expected_source)
                    or ((inner_artifact / "submission.json").exists()
                        and read_object(inner_artifact / "submission.json") != expected)
                    or ((inner_artifact / "Proof.lean").exists()
                        and (inner_artifact / "Proof.lean").read_bytes() != expected_source)
                    or ((inner_artifact / "pending.json").exists()
                        and unseal(inner_artifact / "pending.json") != inner_pending)):
                raise CorpusError("inner submission differs from the bound response")
        if not reservation_present or not (artifact / "result.json").exists():
            interrupted = True
        else:
            result = unseal(artifact / "result.json")
            if response is None or result.get("reservation_sha256") != digest(canonical(pending)):
                raise CorpusError("outer result differs from its reservation")
            if response["action"] == "retain":
                if key in inner or result != {"reservation_sha256": digest(canonical(pending)), "action": "retain"}:
                    raise CorpusError("retain response unexpectedly invoked Lean")
                row["status"] = "retained"
            else:
                if key not in inner:
                    raise CorpusError("candidate result is missing its inner attempt")
                attempt, chosen = inner[key]
                result_path = root / slot["session"] / attempt["artifact"] / "result.json"
                if (set(result) != {"reservation_sha256", "action", "inner_result_sha256"}
                        or result["action"] != "candidate" or not result_path.exists()
                        or result["inner_result_sha256"] != digest(result_path.read_bytes())):
                    raise CorpusError("candidate result evidence changed")
                row["status"] = attempt["status"]
                if attempt["status"] == "verified":
                    if chosen is None or chosen["package_source_tokens"] != 0:
                        raise CorpusError("candidate lacks an old-tool-only certificate")
                    row["proof_source_tokens"] = chosen["proof_source_tokens"]
                    before = selected[slot["task_id"]]["proof_source_tokens"]
                    if chosen["proof_source_tokens"] < before:
                        relative = str((Path(slot["session"]) / attempt["artifact"]))
                        selected[slot["task_id"]] = {"task_id": slot["task_id"], "artifact": relative,
                            "proof_source_tokens": chosen["proof_source_tokens"],
                            "proof_sha256": digest((root / relative / "Proof.lean").read_bytes())}
                        row["replaced"] = True
                        replacements.append({"slot": slot["slot"], "task_id": slot["task_id"],
                                             "before": before, "after": chosen["proof_source_tokens"]})
                        sweep_improved = True
                        stable = 0
                elif attempt["status"] == "rejected":
                    sweep_clean = False
                    stable = 0
                else:
                    interrupted = True
        if interrupted:
            stable = 0
        attempts.append(row)
        if not interrupted and (index + 1) % sweep_size == 0:
            completed += 1
            stable = stable + 1 if sweep_clean and not sweep_improved else 0
            sweep_clean, sweep_improved = True, False
    finished = stable >= plan["policy"]["stable_sweeps"]
    exhausted = len(attempts) == len(plan["schedule"])
    status = ("interrupted_or_inconclusive" if interrupted else "declared_search_finished" if finished
              else "sweep_budget_exhausted" if exhausted else "in_progress")
    next_slot = plan["schedule"][len(attempts)] if status == "in_progress" else None
    summary = {"schema_version": 1, "status": status,
        "stop_reason": {"interrupted_or_inconclusive": "incomplete_or_unknown_verification",
            "declared_search_finished": "required_clean_no_improvement_sweeps_observed",
            "sweep_budget_exhausted": "maximum_sweeps_reached", "in_progress": None}[status],
        "completed_sweeps": completed, "stable_sweeps": stable, "replacements": replacements,
        "initial_source_tokens": sum(x["proof_source_tokens"] for x in plan["initial"]),
        "selected_source_tokens": sum(x["proof_source_tokens"] for x in selected.values()),
        "tasks": list(selected.values()), "attempts": attempts, "next_slot": next_slot,
        "baseline_search_complete": False, "package_attribution_ready": False,
        "globally_shortest": False, "model_search_verified": False,
        "definition_optimization_performed": False, "generation_usage": None,
        "generation_usage_status": "supplied_local_not_independently_metered",
        "actual_provider_calls": 0, "scope": "Finite supplied-local workflow only; no assertion of "
        "existing-tool exhaustion, sufficient baseline optimization, causal attribution or model performance."}
    return root, plan, selected, summary


def report(root):
    return _state(root)[3]


def next_request(root):
    root, plan, selected, state = _state(root)
    return _request(root, plan, state["next_slot"], selected) if state["next_slot"] else None


def submit(root, submission, *, lean=None):
    response = _response(submission)
    root = Path(root).resolve()
    with session_lock(root):
        request = next_request(root)
        if request is None or response["request_sha256"] != request["request_sha256"]:
            raise CorpusError("search response belongs to a stale or unavailable request")
        _, plan = _load(root)
        slot = plan["schedule"][request["slot"] - 1]
        pending = {"slot": request["slot"], "request_sha256": request["request_sha256"],
                   "response_sha256": digest(canonical(response))}
        with (root / "issued.jsonl").open("r+b") as journal:
            journal.seek(0, 2)
            journal.write(canonical(seal(pending)) + b"\n")
            journal.flush()
            os.fsync(journal.fileno())
        save_new(root / "reservations" / f"{request['slot']:04d}.json", seal(pending))
        artifact = root / "attempts" / f"{request['slot']:04d}"
        artifact.mkdir()
        save_new(artifact / "response.json", response)
        result = {"reservation_sha256": digest(canonical(pending)), "action": response["action"]}
        if response["action"] == "candidate":
            checked = submit_attempt(root / slot["session"], _inner_submission(request, response),
                                     lean=lean or str(REPO / "scripts/lean_sandbox.py"))
            result["inner_result_sha256"] = digest((Path(checked["artifact"]) / "result.json").read_bytes())
        save_new(artifact / "result.json", seal(result))
    return report(root)
