"""Replayable execution of a small frozen set of existing-tool rewrites."""
import json
import os
from pathlib import Path

from . import baseline_methods as methods, baseline_search as search
from .corpus import CorpusError
from .migration import canonical, save_new, seal, session_lock, unseal
from .theory import digest

REPO = Path(__file__).resolve().parents[1]
TOOLS = tuple(sorted(set(search.TOOLS) | {
    "maam/baseline_methods.py", "maam/baseline_execution.py", "scripts/control_baseline_execution.py"}))


def _tools():
    return {name: digest((REPO / name).read_bytes()) for name in TOOLS}


def prepare_execution(search_root, output):
    source = Path(search_root).resolve()
    state = search.report(source)
    plan = unseal(source / "plan.json")
    policy = plan["policy"]
    if (state["attempts"] or state["status"] != "in_progress"
            or policy["max_sweeps"] != 1 or policy["stable_sweeps"] != 1
            or len(plan["schedule"]) > 4
            or any(methods.METHODS.get(m["name"]) != m["instructions"] for m in policy["methods"])):
        raise CorpusError("execution requires a fresh one-sweep search with at most four declared rewrite scans")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    value = {"schema_version": 1, "search_root": str(source),
             "search_plan_sha256": digest((source / "plan.json").read_bytes()),
             "max_scans": len(plan["schedule"]), "tool_sha256": _tools()}
    save_new(root / "plan.json", seal(value))
    (root / "generated").mkdir()
    (root / "outcomes").mkdir()
    with (root / "issued.jsonl").open("xb") as stream:
        stream.write(canonical(seal({"plan_sha256": digest(canonical(value))})) + b"\n")
    return report(root)


def _issued(root, plan):
    try:
        rows = [json.loads(line) for line in (root / "issued.jsonl").read_bytes().splitlines()]
    except (OSError, ValueError) as exc:
        raise CorpusError("execution journal is missing or unreadable") from exc
    for row in rows:
        if not isinstance(row, dict):
            raise CorpusError("invalid execution journal")
        fingerprint = row.pop("seal_sha256", None)
        if fingerprint != digest(canonical(row)):
            raise CorpusError("execution journal changed")
    if not rows or rows[0] != {"plan_sha256": digest(canonical(plan))}:
        raise CorpusError("execution journal belongs to another plan")
    for number, row in enumerate(rows[1:], 1):
        if (set(row) != {"slot", "request_sha256", "method"} or row["slot"] != number
                or row["method"] not in methods.METHODS):
            raise CorpusError("execution slots differ from the declared schedule")
    if len(rows) - 1 > plan["max_scans"]:
        raise CorpusError("execution exceeds its frozen limit")
    return rows[1:]


def _load(root):
    root = Path(root).resolve()
    plan = unseal(root / "plan.json")
    if (set(plan) != {"schema_version", "search_root", "search_plan_sha256", "max_scans", "tool_sha256"}
            or plan["schema_version"] != 1 or type(plan["max_scans"]) is not int):
        raise CorpusError("invalid execution plan")
    source = Path(plan["search_root"])
    if (plan["tool_sha256"] != _tools()
            or plan["search_plan_sha256"] != digest((source / "plan.json").read_bytes())):
        raise CorpusError("execution code or search plan changed")
    search_plan = unseal(source / "plan.json")
    policy = search_plan["policy"]
    if (not 1 <= plan["max_scans"] <= 4 or plan["max_scans"] != len(search_plan["schedule"])
            or policy["max_sweeps"] != 1 or policy["stable_sweeps"] != 1
            or any(methods.METHODS.get(m["name"]) != m["instructions"] for m in policy["methods"])):
        raise CorpusError("declared execution methods changed")
    return root, plan, source


def report(output):
    root, plan, source = _load(output)
    state = search.report(source)
    issued = _issued(root, plan)
    search_plan = unseal(source / "plan.json")
    inner_issued = search._issued(source, search_plan)
    if len(inner_issued) > len(issued):
        raise CorpusError("search contains a response outside the execution journal")
    names = {f"{i:04d}.json" for i in range(1, len(issued) + 1)}
    for folder in ("generated", "outcomes"):
        if {p.name for p in (root / folder).iterdir()} - names:
            raise CorpusError("execution evidence has no issued slot")
    counts = dict(scans=0, candidates=0, retains=0, verified=0, rejected=0, inconclusive=0,
                  replacements=len(state["replacements"]))
    attempts, interrupted = [], False
    for index, pending in enumerate(issued):
        if interrupted:
            raise CorpusError("execution continued after an incomplete record")
        number = index + 1
        generated = root / "generated" / f"{number:04d}.json"
        outcome = root / "outcomes" / f"{number:04d}.json"
        row = {"slot": number, "method": pending["method"], "status": "incomplete"}
        if not generated.exists():
            if outcome.exists():
                raise CorpusError("outcome is missing its generation record")
            interrupted = True
            attempts.append(row)
            continue
        value = unseal(generated)
        if set(value) != {"slot", "request", "response", "evidence"} or value["slot"] != number:
            raise CorpusError("generation record has an invalid shape")
        request = dict(value["request"])
        fingerprint = request.pop("request_sha256", None)
        expected_slot = search_plan["schedule"][index]
        if (fingerprint != digest(canonical(request)) or fingerprint != pending["request_sha256"]
                or request["slot"] != number or request["method"] != expected_slot["method"]
                or request["task_id"] != expected_slot["task_id"]
                or request["method"]["name"] != pending["method"]):
            raise CorpusError("generation request differs from its issued method or task")
        response, evidence = methods.generate(value["request"])
        if (response, evidence) != (value["response"], value["evidence"]):
            raise CorpusError("deterministic method replay differs from its recorded output")
        counts["scans"] += 1
        counts["candidates" if response["action"] == "candidate" else "retains"] += 1
        row.update(task_id=request["task_id"], matched=evidence["matched"], action=response["action"])
        if index < len(inner_issued):
            if (inner_issued[index]["request_sha256"] != fingerprint
                    or inner_issued[index]["response_sha256"] != digest(canonical(response))):
                raise CorpusError("search response does not match generated evidence")
        if not outcome.exists():
            interrupted = True
        else:
            result = unseal(outcome)
            if index >= len(inner_issued) or index >= len(state["attempts"]):
                raise CorpusError("execution outcome has no search attempt")
            response_path = source / "attempts" / f"{number:04d}" / "response.json"
            result_path = source / "attempts" / f"{number:04d}" / "result.json"
            if (result != {"slot": number, "generated_sha256": digest(generated.read_bytes()),
                           "search_response_sha256": digest(response_path.read_bytes()),
                           "search_result_sha256": digest(result_path.read_bytes())}
                    or json.loads(response_path.read_text()) != response):
                raise CorpusError("execution outcome differs from the checked search records")
            status = state["attempts"][index]["status"]
            row["status"] = status
            if status in ("verified", "rejected"):
                counts[status] += 1
            elif status != "retained":
                counts["inconclusive"] += 1
                interrupted = True
        attempts.append(row)
    if state["status"] == "interrupted_or_inconclusive":
        interrupted = True
    complete = len(attempts) == plan["max_scans"] and not interrupted
    if not complete and not interrupted and state["next_slot"] is None:
        raise CorpusError("search stopped before its declared deterministic methods completed")
    return {"schema_version": 1, "status": "interrupted_or_inconclusive" if interrupted
            else "declared_methods_executed" if complete else "in_progress",
            "search_status": state["status"], "search_root": str(source),
            "deterministic_methods_executed": complete, "counts": counts, "attempts": attempts,
            "initial_source_tokens": state["initial_source_tokens"],
            "selected_source_tokens": state["selected_source_tokens"],
            "baseline_search_complete": False, "package_attribution_ready": False,
            "globally_shortest": False, "model_search_verified": False,
            "definition_optimization_performed": False,
            "generation_usage": None, "actual_provider_calls": 0,
            "scope": "Exact execution/replay of declared local rewrite scans; generated candidates "
                     "are untrusted until Lean verification. No claim of tool exhaustion, sufficient "
                     "baseline preparation, globally shortest proofs or concept attribution."}


def execute_next(output):
    root = Path(output).resolve()
    with session_lock(root):
        state = report(root)
        if state["status"] != "in_progress":
            raise CorpusError("execution has no available step; incomplete work cannot be retried")
        _, _, source = _load(root)
        request = search.next_request(source)
        pending = {"slot": request["slot"], "request_sha256": request["request_sha256"],
                   "method": request["method"]["name"]}
        with (root / "issued.jsonl").open("r+b") as journal:
            journal.seek(0, 2)
            journal.write(canonical(seal(pending)) + b"\n")
            journal.flush()
            os.fsync(journal.fileno())
        response, evidence = methods.generate(request)
        generated = root / "generated" / f"{request['slot']:04d}.json"
        save_new(generated, seal({"slot": request["slot"], "request": request,
                                  "response": response, "evidence": evidence}))
        search.submit(source, response)
        attempt = source / "attempts" / f"{request['slot']:04d}"
        save_new(root / "outcomes" / f"{request['slot']:04d}.json", seal({"slot": request["slot"],
            "generated_sha256": digest(generated.read_bytes()),
            "search_response_sha256": digest((attempt / "response.json").read_bytes()),
            "search_result_sha256": digest((attempt / "result.json").read_bytes())}))
    return report(root)
