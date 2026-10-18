"""Controller records for fresh-context solving; no model-budget claims.

Context isolation is a controller instruction, not filesystem access control.
Archive checksums bind records but are not signed attestations of generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

from .ablation import (cost, frontier_relation, measure_attempt, package_uses,
                       portfolio, validate_module)
from .corpus import CorpusError
from .migration import (canonical, compare_sessions, load_session, load_suite,
                        proof_source, save_new, seal, session_report,
                        start_session, submit_attempt, task_request, unseal)
from .theory import digest, inside, read_object

MEASUREMENT_BUDGET = {"per_command_timeout_seconds": 60,
                      "total_timeout_seconds": 180, "max_heartbeats": 200000}


def now():
    return datetime.now(timezone.utc).isoformat()


def load_protocol(path):
    path = Path(path).resolve()
    data = read_object(path)
    if data.get("schema_version") != 1:
        raise CorpusError("expected independent protocol schema 1")
    suite = inside(path.parent, data["suite"]["path"], "suite")
    if digest(suite.read_bytes()) != data["suite"]["sha256"]:
        raise CorpusError("independent protocol suite fingerprint changed")
    frozen = load_suite(suite)
    if data["study_id"] != frozen["manifest"]["suite_id"]:
        raise CorpusError("protocol and suite identities differ")
    order = data["launch_order"]
    expected = {(c, t["id"]) for c in ("baseline", "treatment")
                for t in frozen["manifest"]["tasks"]}
    if (len(order) != len(expected)
            or {(r["condition"], r["task_id"]) for r in order} != expected
            or len({r["worker"] for r in order}) != len(order)):
        raise CorpusError("launch order must cover each task/condition exactly once")
    for row in order:
        if not row["worker"].isalnum():
            raise CorpusError("unsafe worker identifier")
    if any(data["scope"].get(k) is not False for k in (
            "held_out_evaluation", "generation_budget_verified", "training_eligible",
            "fair_model_performance_claim")):
        raise CorpusError("this protocol cannot certify unobserved generation controls")
    if data["solver"]["mode"] != "interactive_agent":
        raise CorpusError("fresh solving requires interactive-agent provenance")
    return data, suite


def run_record(root):
    root = Path(root)
    record = unseal(root / "run.json")
    protocol_path = Path(__file__).resolve().parents[1] / "experiments/hom_kernel_independent/protocol.json"
    protocol, suite = load_protocol(protocol_path)
    if record["protocol"] != protocol or record["protocol_sha256"] != digest(protocol_path.read_bytes()):
        raise CorpusError("live run protocol differs from its frozen protocol")
    return record, protocol, suite


def prepare_run(protocol_path, root, workers, skill, *, freeze_commit, runtime=None):
    protocol, suite = load_protocol(protocol_path)
    root, workers, skill = Path(root).resolve(), Path(workers).resolve(), Path(skill).resolve()
    if root == workers or root in workers.parents or workers in root.parents:
        raise CorpusError("keep controller sessions separate from worker directories")
    actual = {str(p.relative_to(skill)): digest(p.read_bytes()) for p in skill.rglob("*")
              if p.is_file() and "__pycache__" not in str(p)}
    if actual != protocol["worker_skill_sha256"]:
        raise CorpusError("worker skill differs from the frozen skill")
    if not isinstance(freeze_commit, str) or len(freeze_commit) != 40 or any(c not in "0123456789abcdef" for c in freeze_commit):
        raise CorpusError("record the explicit Git commit frozen before generation")
    root.mkdir(parents=True, exist_ok=False)
    workers.mkdir(parents=True, exist_ok=False)
    copied_skill = workers / "skill"
    shutil.copytree(skill, copied_skill, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(copied_skill, root / "worker-skill")
    for condition in ("baseline", "treatment"):
        start_session(suite, root / condition, condition=condition, solver_id=protocol["solver"]["id"])
    for name in ("prompts", "launches", "returns", "raw-submissions", "feedback", "messages"):
        (root / name).mkdir()
    for row in protocol["launch_order"]:
        worker = workers / row["worker"]
        worker.mkdir()
        save_new(worker / "request.json", task_request(root / row["condition"], row["task_id"]))
        prompt = protocol["prompt_template"].format(skill_root=str(copied_skill), worker_root=str(worker))
        (root / "prompts" / (row["worker"] + ".txt")).write_text(prompt)
    save_new(root / "run.json", seal({"schema_version": 1, "study_id": protocol["study_id"],
        "freeze_commit": freeze_commit, "protocol_sha256": digest(Path(protocol_path).read_bytes()),
        "prepared_at": now(), "worker_root": str(workers), "skill_root": str(copied_skill),
        "runtime": runtime, "protocol": protocol}))
    return {"status": "prepared", "workers": len(protocol["launch_order"]), "root": str(root)}


def register_launch(root, worker, agent_id):
    root = Path(root)
    record, protocol, _ = run_record(root)
    row = next(r for r in protocol["launch_order"] if r["worker"] == worker)
    index = protocol["launch_order"].index(row)
    existing = sorted((root / "launches").glob("*.json"))
    if len(existing) != index:
        raise CorpusError("workers must be registered in the frozen launch order")
    if not isinstance(agent_id, str) or not agent_id:
        raise CorpusError("agent identifier must be explicit")
    if any(unseal(p)["agent_id"] == agent_id for p in existing):
        raise CorpusError("a fresh context is required for each task/condition")
    prompt = (root / "prompts" / (worker + ".txt")).read_text()
    expected = protocol["prompt_template"].format(
        skill_root=record["skill_root"], worker_root=str(Path(record["worker_root"]) / worker))
    if prompt != expected:
        raise CorpusError("worker prompt differs from the frozen template")
    value = {**row, "launch_index": index, "agent_id": agent_id,
             "fork_turns": "none", "model_override": None, "prompt": prompt,
             "registered_at": now(), "timestamp_scope": "controller registration after spawn returned"}
    save_new(root / "launches" / (worker + ".json"), seal(value))
    return value


def verify_return(root, worker, number, *, lean="lean"):
    root = Path(root)
    record, protocol, _ = run_record(root)
    if shutil.which(lean) is None or shutil.which("lean") is None:
        raise CorpusError("warm pinned Lean and expose lean on PATH for auditor child processes before submitting")
    launch = unseal(root / "launches" / (worker + ".json"))
    session = root / launch["condition"]
    task = next(t for t in session_report(session)["tasks"] if t["id"] == launch["task_id"])
    if task["selected"] is not None or len(task["attempts"]) + 1 != number:
        raise CorpusError("stop after success; attempt numbers must be consecutive")
    folder = Path(record["worker_root"]) / worker
    request = read_object(folder / "request.json")
    if request != task_request(session, launch["task_id"]):
        raise CorpusError("worker request changed")
    submission_path = folder / f"submission-{number:02d}.json"
    submission = read_object(submission_path)
    raw_folder = root / "raw-submissions"
    raw_folder.mkdir(exist_ok=True)
    raw_path = raw_folder / f"{worker}-{number:03d}.json"
    if raw_path.exists():
        if raw_path.read_bytes() != submission_path.read_bytes():
            raise CorpusError("an interrupted raw return changed")
    else:
        with raw_path.open("xb") as out:
            out.write(submission_path.read_bytes())
    proof = (folder / f"proof-{number:02d}.lean").read_text()
    bridge = (folder / f"bridge-{number:02d}.txt").read_text().strip()
    if submission["proof"] != proof or submission["bridge"] != bridge:
        raise CorpusError("packaged proof or bridge differs from returned files")
    returned = {"worker": worker, "attempt": number, "received_at": now(),
                "request": request, "submission": submission,
                "submission_file_sha256": digest(submission_path.read_bytes())}
    returned_path = root / "returns" / f"{worker}-{number:03d}.json"
    if returned_path.exists():
        prior = unseal(returned_path)
        if any(prior[k] != returned[k] for k in returned if k != "received_at"):
            raise CorpusError("an interrupted pre-verification return changed")
    else:
        save_new(returned_path, seal(returned))
    result = submit_attempt(session, submission, lean=lean)
    remaining = request["budget"]["max_attempts_per_task"] - number
    feedback = {"worker": worker, "attempt": number, "status": result["status"],
                "failure": result.get("failure"), "remaining_attempts": remaining,
                "stop": result["status"] == "verified" or remaining == 0}
    save_new(root / "feedback" / f"{worker}-{number:03d}.json", seal(feedback))
    return feedback


def infrastructure_failure(result):
    """Narrow classifier for the observed host setup failure, not proof failure."""
    failure = result.get("failure") or {}
    return (result.get("status") == "rejected" and failure.get("stage") == "audit"
            and "could not execute external process 'lean'" in failure.get("message", ""))


def measure_verified(root, *, lean="lean"):
    root = Path(root)
    outcomes = []
    for condition in ("baseline", "treatment"):
        session = root / condition
        _, _, frozen = load_session(session)
        for task in session_report(session)["tasks"]:
            if task["selected"] is None:
                continue
            number = task["selected"]["attempt"]
            attempt = session / "attempts" / task["id"] / f"{number:03d}"
            if not (attempt / "measurement/result.json").exists():
                result = measure_attempt(frozen, task_request(session, task["id"]), attempt,
                                         MEASUREMENT_BUDGET, lean=lean)
                outcomes.append({"condition": condition, "task": task["id"], "status": result["status"]})
                print(condition, task["id"], result["status"], flush=True)
    return outcomes


def measured_variant(root, condition):
    session = Path(root) / condition
    report = session_report(session)
    rows, package_cost, packages = [], None, None
    for task in report["tasks"]:
        row = {"id": task["id"], "attempts": []}
        for event in task["attempts"]:
            attempt = session / event["artifact"]
            result = unseal(attempt / "result.json")
            submission = read_object(attempt / "submission.json")
            request = task_request(session, task["id"])
            if digest(proof_source(request, submission["proof"]).encode()) != result["proof_sha256"]:
                raise CorpusError("recorded proof is not the canonical submitted term")
            option = {"attempt": event["attempt"], "cost": None}
            measurement_path = attempt / "measurement/result.json"
            if result["status"] == "verified" and measurement_path.exists():
                measurement = unseal(measurement_path)
                for command in measurement["trace"]:
                    for log in command["logs"].values():
                        if digest(inside(attempt / "measurement", log["path"], "measurement log").read_bytes()) != log["sha256"]:
                            raise CorpusError("measurement command log changed")
                if (measurement["proof_sha256"] != result["proof_sha256"]
                        or measurement["formal_result_sha256"] != digest((attempt / "result.json").read_bytes())):
                    raise CorpusError("measurement is not bound to the formal attempt")
                if measurement["status"] == "measured":
                    modules = measurement["inventory"]["modules"]
                    expected = (["Candidate"] if condition == "treatment" else []) + ["Proof"]
                    if [m["module"] for m in modules] != expected:
                        raise CorpusError("inventory modules differ from this condition")
                    for module in modules:
                        validate_module(module)
                    proof = modules[-1]
                    current_packages = modules[:-1]
                    sources = {s["module"]: s["source_tokens"] for s in result["audit"]["sources"]}
                    fixed = cost(sum(v for k, v in sources.items() if k != "Proof"),
                                 sum(m["expr_nodes"] for m in current_packages))
                    if packages is not None and (packages != current_packages or package_cost != fixed):
                        raise CorpusError("frozen package cost changed between goals")
                    packages, package_cost = current_packages, fixed
                    target = result["audit"]["targets"][0]
                    decl = next(d for d in proof["declarations"] if d["name"] == "Submission.solve")
                    if (decl["value_expr_nodes"] != target["proof_expr_nodes"]
                            or decl["signature_expr_nodes"] != target["signature_expr_nodes"]):
                        raise CorpusError("target inventory differs from correctness audit")
                    option.update(cost=cost(sources["Proof"], proof["expr_nodes"]),
                                  used_package_declarations=package_uses(proof, current_packages))
            row["attempts"].append(option)
        rows.append(row)
    return {"id": condition, "tasks": rows, "package_cost": package_cost}


def summarize(root):
    root = Path(root)
    record, protocol, _ = run_record(root)
    archived_skill = root / "worker-skill"
    skill_files = {str(p.relative_to(archived_skill)): digest(p.read_bytes())
                   for p in archived_skill.rglob("*") if p.is_file()}
    if skill_files != protocol["worker_skill_sha256"]:
        raise CorpusError("archived worker skill differs from the frozen skill")
    reports = {c: session_report(root / c) for c in ("baseline", "treatment")}
    agent_ids, complete, attempt_count = set(), True, 0
    failures, infrastructure = [], []
    expected_records = set()
    for i, row in enumerate(protocol["launch_order"]):
        path = root / "launches" / (row["worker"] + ".json")
        if not path.exists():
            complete = False
            continue
        launch = unseal(path)
        expected_prompt = protocol["prompt_template"].format(
            skill_root=record["skill_root"], worker_root=str(Path(record["worker_root"]) / row["worker"]))
        if (any(launch[k] != v for k, v in row.items()) or launch["launch_index"] != i
                or launch["fork_turns"] != "none" or launch["model_override"] is not None
                or launch["agent_id"] in agent_ids or launch["prompt"] != expected_prompt):
            raise CorpusError("launch record violates task-local protocol")
        agent_ids.add(launch["agent_id"])
        task = next(t for t in reports[row["condition"]]["tasks"] if t["id"] == row["task_id"])
        attempts = task["attempts"]
        complete &= bool(task["selected"] or len(attempts) == reports[row["condition"]]["budget"]["max_attempts_per_task"])
        succeeded = False
        for event in attempts:
            if succeeded or event["status"] == "incomplete":
                raise CorpusError("attempts after success or incomplete verification cannot be finalized")
            number = event["attempt"]
            attempt_count += 1
            stem = f"{row['worker']}-{number:03d}.json"
            expected_records.add(stem)
            returned = unseal(root / "returns" / stem)
            feedback = unseal(root / "feedback" / stem)
            raw = (root / "raw-submissions" / stem).read_bytes()
            if (digest(raw) != returned["submission_file_sha256"]
                    or json.loads(raw) != returned["submission"]):
                raise CorpusError("returned artifact raw bytes differ from the original submission")
            request = task_request(root / row["condition"], row["task_id"])
            submission = read_object(root / row["condition"] / event["artifact"] / "submission.json")
            if (returned["worker"] != row["worker"] or returned["attempt"] != number
                    or returned["request"] != request or returned["submission"] != submission
                    or feedback["worker"] != row["worker"] or feedback["attempt"] != number
                    or feedback["status"] != event["status"] or feedback["failure"] != event["failure"]
                    or feedback["remaining_attempts"] != request["budget"]["max_attempts_per_task"] - number
                    or feedback["stop"] != (event["status"] == "verified" or feedback["remaining_attempts"] == 0)):
                raise CorpusError("returned artifact or own-condition feedback differs from its verified attempt")
            succeeded = event["status"] == "verified"
            if not succeeded:
                item = {"worker": row["worker"], "condition": row["condition"], "task": row["task_id"], **event}
                (infrastructure if infrastructure_failure(event) else failures).append(item)
    for name in ("returns", "raw-submissions", "feedback"):
        if {p.name for p in (root / name).iterdir()} != expected_records:
            raise CorpusError("extra or missing returned-attempt/feedback records")
    if {p.stem for p in (root / "launches").iterdir()} - {r["worker"] for r in protocol["launch_order"]}:
        raise CorpusError("launch records contain a worker outside the frozen cohort")
    variants = [measured_variant(root, c) for c in ("baseline", "treatment")]
    common = [t["id"] for t in variants[0]["tasks"] if all(
        any(a["cost"] is not None for a in next(r for r in v["tasks"] if r["id"] == t["id"])["attempts"])
        for v in variants)]
    frontiers = {v["id"]: portfolio(v["tasks"], v["package_cost"], common, 10000) for v in variants}
    return {"schema_version": 1, "status": "completed" if complete else "incomplete",
            "study_id": protocol["study_id"], "freeze_commit": record["freeze_commit"],
            "protocol_sha256": record["protocol_sha256"], "registered_workers": len(agent_ids),
            "attempts": attempt_count, "proof_or_other_failures": failures, "infrastructure_failures": infrastructure,
            "comparison": compare_sessions(root / "baseline", root / "treatment"),
            "common_measured_tasks": common, "observed_witness_costs": frontiers,
            "cost_relation": frontier_relation(frontiers["baseline"], frontiers["treatment"]),
            "variants": variants, "scope": protocol["scope"],
            "interpretation": "Observed witnesses under fixed submission/Lean budgets. Generation cost and exact model revision unknown; no fair model-performance or training preference claim."}


def bundle(folder):
    folder = Path(folder)
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            if path.is_symlink():
                raise CorpusError("bundle must not contain symlinks")
            files[str(path.relative_to(folder))] = path.read_text(encoding="utf-8")
    return seal({"files": files})


def restore_bundle(value, folder):
    folder = Path(folder)
    unsigned = {k: v for k, v in value.items() if k != "seal_sha256"}
    if digest(canonical(unsigned)) != value.get("seal_sha256"):
        raise CorpusError("bundle fingerprint mismatch")
    for name, content in value["files"].items():
        dest = inside(folder, name, "bundle member")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as out:
            out.write(content)


def export_run(root, output):
    summary = summarize(root)
    if summary["status"] != "completed":
        raise CorpusError("cannot finalize an incomplete solving cohort")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save_new(output / "summary.json", summary)
    for condition in ("baseline", "treatment"):
        save_new(output / (condition + ".json"), bundle(Path(root) / condition))
    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp)
        for name in sorted(p.name for p in Path(root).iterdir() if p.name not in {"baseline", "treatment"}):
            source = Path(root) / name
            if source.is_dir():
                shutil.copytree(source, dest / name)
            else:
                shutil.copyfile(source, dest / name)
        save_new(output / "controller.json", bundle(dest))
    return summary


def restore_archive(archive, root):
    archive, root = Path(archive), Path(root)
    root.mkdir(parents=True, exist_ok=False)
    restore_bundle(read_object(archive / "controller.json"), root)
    for condition in ("baseline", "treatment"):
        restore_bundle(read_object(archive / (condition + ".json")), root / condition)
    observed = summarize(root)
    if observed != read_object(archive / "summary.json"):
        raise CorpusError("archived comparison does not replay from complete attempts")
    return observed


def replay_archive(archive, output, *, lean="lean"):
    """Recompile preserved outputs; this does not rerun LLM generation."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temp:
        original = Path(temp) / "original"
        summary = restore_archive(archive, original)
        _, protocol, suite = run_record(original)
        for condition in ("baseline", "treatment"):
            start_session(suite, output / condition, condition=condition,
                          solver_id="replay-of-" + protocol["solver"]["id"], mode="supplied_reference")
        cases = []
        for row in protocol["launch_order"]:
            condition, task = row["condition"], row["task_id"]
            old_session, new_session = original / condition, output / condition
            old_report = next(t for t in session_report(old_session)["tasks"] if t["id"] == task)
            for event in old_report["attempts"]:
                old_attempt = old_session / event["artifact"]
                old = unseal(old_attempt / "result.json")
                submission = read_object(old_attempt / "submission.json")
                submission["request_sha256"] = task_request(new_session, task)["request_sha256"]
                result = submit_attempt(new_session, submission, lean=lean)
                setup_failure = infrastructure_failure(old)
                matched = result["proof_sha256"] == old["proof_sha256"]
                matched &= result["status"] == ("verified" if setup_failure else old["status"])
                if old["status"] == "verified":
                    _, _, frozen = load_session(new_session)
                    measured = measure_attempt(frozen, task_request(new_session, task), result["artifact"],
                                               MEASUREMENT_BUDGET, lean=lean)
                    expected = unseal(old_attempt / "measurement/result.json")
                    matched &= measured["status"] == expected["status"] == "measured" and measured["inventory"] == expected["inventory"]
                elif not setup_failure:
                    matched &= all(result.get("failure", {}).get(k) == old.get("failure", {}).get(k) for k in ("kind", "stage"))
                case = {"worker": row["worker"], "task": task, "condition": condition,
                        "attempt": event["attempt"], "original_status": old["status"],
                        "original_infrastructure_failure": setup_failure,
                        "status": result["status"], "matched": bool(matched)}
                cases.append(case)
                print(row["worker"], event["attempt"], result["status"], bool(matched), flush=True)
        result = {"status": "passed" if all(c["matched"] for c in cases) else "failed",
                  "cases": cases, "attempts": len(cases), "original_summary_sha256": digest((Path(archive) / "summary.json").read_bytes()),
                  "original_scope": summary["scope"], "scope": "Lean/inventory replay of archived outputs; no new LLM generation"}
        save_new(output / "validation.json", result)
        return result
