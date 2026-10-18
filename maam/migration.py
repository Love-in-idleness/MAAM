"""Task-local Lean migrations over frozen theory packages.

The controller is trusted. Lean runs as code: this is an experiment protocol,
not an operating-system sandbox for adversarial programs.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .corpus import CorpusError
from .theory import CHECKER, CORE_AXIOMS, digest, inside, names, nonempty_string, read_object


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as out:
        out.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def seal(value):
    return {**value, "seal_sha256": digest(canonical(value))}


def unseal(path):
    value = read_object(path)
    expected = value.pop("seal_sha256", None)
    if expected != digest(canonical(value)):
        raise CorpusError(f"record fingerprint mismatch: {path}")
    return value


def load_suite(path):
    path = Path(path).resolve()
    data = read_object(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("phase") != "migration_calibration":
        raise CorpusError("expected migration_calibration suite schema 1")
    nonempty_string(data.get("suite_id"), "suite_id")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data.get("lean_version", "")):
        raise CorpusError("suite must pin an exact Lean version")
    base = data.get("base", {})
    base_modules = names(base.get("modules"), "base.modules")
    if base.get("allowed_axioms") != CORE_AXIOMS or base.get("allowed_core_prefixes") != ["Init"]:
        raise CorpusError("suite must use the fixed Init/core axiom policy")
    package_path = inside(path.parent, data.get("package"), "package")
    if package_path == path or package_path.name == "suite.json":
        raise CorpusError("package path conflicts with the suite manifest")
    package = read_object(package_path)
    if (package.get("schema_version") != 1 or package.get("base_id") != base.get("id")
            or package.get("status") != "proved_extension" or package.get("conjectures") != []):
        raise CorpusError("package must be a proved extension of this base")
    nonempty_string(package.get("package_id"), "package_id")
    package_modules = names(package.get("modules"), "package.modules")
    names(package.get("declarations"), "package.declarations")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise CorpusError("suite tasks must be nonempty")
    ids, goals, modules, families = [], [], [], {"development": set(), "reserved": set()}
    for task in tasks:
        if not isinstance(task, dict):
            raise CorpusError("task must be an object")
        task_id = task.get("id", "")
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", task_id):
            raise CorpusError("task id must be a safe lowercase identifier")
        if task.get("split") not in families:
            raise CorpusError("task split must be development or reserved")
        families[task["split"]].add(nonempty_string(task.get("family"), "task.family"))
        names([task.get("module"), task.get("goal")], "task module/goal")
        ids.append(task_id)
        modules.append(task["module"])
        goals.append(task["goal"])
    if len(set(ids)) != len(ids) or len(set(goals)) != len(goals):
        raise CorpusError("duplicate task id or goal")
    if families["development"] & families["reserved"]:
        raise CorpusError("a reasoning family crosses the development/reserved split")
    all_modules = base_modules + package_modules + modules
    names(all_modules, "all modules")
    if any(m.split(".")[0] in {"Init", "Lean", "Std", "Proof"} for m in all_modules):
        raise CorpusError("suite modules must not shadow core or generated Proof module")
    sources = data.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(all_modules):
        raise CorpusError("sources must list every base, candidate and task module exactly once")
    blobs, hashes, source_paths = {}, {}, []
    for module, item in sources.items():
        if not isinstance(item, dict):
            raise CorpusError("source descriptor must be an object")
        source = inside(path.parent, item.get("path"), "source path")
        if source.suffix != ".lean":
            raise CorpusError("source must be a .lean file")
        content = source.read_bytes()
        if item.get("sha256") != digest(content):
            raise CorpusError(f"frozen source fingerprint mismatch: {module}")
        blobs[module], hashes[module] = content, digest(content)
        source_paths.append(source)
    if len(set(source_paths)) != len(source_paths):
        raise CorpusError("different modules must have different source paths")
    budget = data.get("budget", {})
    for field in ("max_attempts_per_task", "max_proof_bytes", "max_heartbeats",
                  "per_command_timeout_seconds", "per_attempt_timeout_seconds"):
        if type(budget.get(field)) is not int or budget[field] <= 0:
            raise CorpusError(f"budget.{field} must be a positive integer")
    fingerprints = {
        "suite_sha256": digest(path.read_bytes()),
        "package_sha256": digest(package_path.read_bytes()),
        "source_sha256": dict(sorted(hashes.items())),
        "evaluator_sha256": digest(Path(__file__).read_bytes()),
        "reference_evaluator_sha256": digest(Path(__file__).with_name("theory.py").read_bytes()),
        "checker_sha256": digest(CHECKER.read_bytes()),
    }
    return {"manifest": data, "package": package, "blobs": blobs, "fingerprints": fingerprints}


def start_session(suite, output, *, condition, solver_id, mode="interactive_agent"):
    frozen = load_suite(suite)
    if condition not in {"baseline", "treatment"} or mode not in {"interactive_agent", "supplied_reference"}:
        raise CorpusError("invalid condition or solver mode")
    nonempty_string(solver_id, "solver_id")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    snapshot = root / "snapshot"
    snapshot.mkdir()
    source_root = Path(suite).resolve().parent
    manifest = frozen["manifest"]
    paths = [manifest["package"]] + [v["path"] for v in manifest["sources"].values()]
    for relative in paths:
        dest = inside(snapshot, relative, "snapshot source")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(inside(source_root, relative, "source").read_bytes())
    (snapshot / "suite.json").write_bytes(Path(suite).read_bytes())
    record = {
        "schema_version": 1, "condition": condition,
        "solver": {"id": solver_id, "mode": mode}, "fingerprints": frozen["fingerprints"],
        "provenance": {"code_commit": os.environ.get("GITHUB_SHA"),
                       "workflow_run_id": os.environ.get("GITHUB_RUN_ID")},
    }
    save_new(root / "session.json", seal(record))
    (root / "attempts").mkdir()
    (root / "reservations").mkdir()
    return {"status": "session_created", "session": str(root), **record}


def load_session(path):
    root = Path(path).resolve()
    session = unseal(root / "session.json")
    frozen = load_suite(root / "snapshot/suite.json")
    if session["fingerprints"] != frozen["fingerprints"]:
        raise CorpusError("session snapshot or evaluator changed; start a new session")
    if session["condition"] not in {"baseline", "treatment"}:
        raise CorpusError("invalid session condition")
    return root, session, frozen


def task_request(path, task_id):
    _, session, frozen = load_session(path)
    data = frozen["manifest"]
    matches = [t for t in data["tasks"] if t["id"] == task_id]
    if len(matches) != 1:
        raise CorpusError(f"unknown task: {task_id}")
    task = matches[0]
    modules = data["base"]["modules"] + [task["module"]]
    if session["condition"] == "treatment":
        modules += frozen["package"]["modules"]
    request = {
        "schema_version": 1, "suite_id": data["suite_id"],
        "session_sha256": digest(canonical(session)),
        "task": task, "condition": session["condition"], "solver": session["solver"],
        "lean_version": data["lean_version"], "budget": data["budget"],
        "sources": [{"module": m, "sha256": digest(frozen["blobs"][m]),
                     "content": frozen["blobs"][m].decode("utf-8")} for m in modules],
        "contract": {"target": "Submission.solve", "expected_goal": task["goal"],
                     "proof": "Lean term after :=, usually by followed by tactics",
                     "bridge": "Explain how the original goal uses the candidate, or why it does not",
                     "forbidden": "Do not change the goal, frozen files, imports, axioms or budgets"},
    }
    return {**request, "request_sha256": digest(canonical(request))}


@contextmanager
def session_lock(root):
    lock = root / "controller.lock"
    try:
        with lock.open("x") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError as exc:
        raise CorpusError("session locked; inspect an interrupted controller before removing its lock") from exc
    try:
        yield
    finally:
        lock.unlink()


def proof_source(request, proof):
    imports = [s["module"] for s in request["sources"]]
    return ("\n".join("import " + m for m in imports) +
            f"\n\nnamespace Submission\ntheorem solve : {request['task']['goal']} :=\n" +
            proof + "\nend Submission\n")


class VerificationFailure(Exception):
    def __init__(self, kind, stage, message):
        self.kind, self.stage, self.message = kind, stage, message


def verify_attempt(frozen, request, source, artifact, *, lean="lean"):
    """Compile only the selected condition/task; audit all local declarations."""
    data, package = frozen["manifest"], frozen["package"]
    budget = data["budget"]
    result = {"status": "pending", "trace": [], "audit": None}
    executable = shutil.which(lean)
    if executable is None:
        return {**result, "status": "inconclusive", "failure": {
            "kind": "environment_unavailable", "stage": "toolchain", "message": f"{lean} is not installed"}}
    deadline = time.monotonic() + budget["per_attempt_timeout_seconds"]
    env = os.environ.copy()
    env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v" + data["lean_version"]
    with tempfile.TemporaryDirectory(prefix="maam-attempt-") as temp:
        work = Path(temp)
        env["LEAN_PATH"] = str(work)

        def command(argv, stage):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VerificationFailure("budget_exhausted", stage, "attempt verification budget exhausted")
            started = time.monotonic()
            timed_out = False
            try:
                proc = subprocess.run(argv, cwd=work, env=env, capture_output=True,
                                      timeout=min(remaining, budget["per_command_timeout_seconds"]), check=False)
                stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, returncode, timed_out = exc.stdout or b"", exc.stderr or b"", None, True
            logfiles = {}
            for suffix, content in (("stdout", stdout), ("stderr", stderr)):
                filename = f"command-{len(result['trace']):02d}.{suffix}"
                (artifact / filename).write_bytes(content)
                logfiles[suffix] = {"path": filename, "sha256": digest(content)}
            result["trace"].append({"stage": stage, "seconds": time.monotonic() - started,
                                    "returncode": returncode, "timed_out": timed_out, "logs": logfiles})
            if timed_out or returncode:
                raise VerificationFailure("budget_exhausted" if timed_out else "verification_failed", stage,
                                          (stdout + stderr).decode("utf-8", errors="replace")[-8000:])
            return stdout.decode("utf-8", errors="replace")

        try:
            version = command([executable, "--version"], "toolchain")
            match = re.search(r"version (\d+\.\d+\.\d+)", version)
            if match is None or match.group(1) != data["lean_version"]:
                raise VerificationFailure("environment_unavailable", "toolchain", version)
            result["toolchain"] = version.strip()
            modules = [s["module"] for s in request["sources"]]
            for module in modules + ["Proof"]:
                dest = work.joinpath(*module.split(".")).with_suffix(".lean")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.encode() if module == "Proof" else frozen["blobs"][module])
                relative = Path(*module.split("."))
                command([executable, f"-DmaxHeartbeats={budget['max_heartbeats']}", "-o",
                         str(relative.with_suffix(".olean")), str(relative.with_suffix(".lean"))], "compile:" + module)
            charged = (package["modules"] if request["condition"] == "treatment" else []) + ["Proof"]
            required = package["declarations"] if request["condition"] == "treatment" else []
            config = {
                "moduleName": "Proof", "allowedModules": ["Init"] + modules + ["Proof"],
                "auditedModules": modules + ["Proof"], "allowedAxioms": CORE_AXIOMS,
                "packageModules": package["modules"] if required else [], "requiredDeclarations": required,
                "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"]}],
                "sources": [{"moduleName": m, "path": str(work.joinpath(*m.split(".")).with_suffix(".lean"))}
                            for m in charged],
            }
            (work / "audit-input.json").write_text(json.dumps(config))
            command([executable, "--run", str(CHECKER), "audit-input.json", "audit-output.json"], "audit")
            audit = read_object(work / "audit-output.json")
            measured = [s.get("module") for s in audit.get("sources", [])]
            targets = audit.get("targets", [])
            if (audit.get("lean_version") != data["lean_version"] or audit.get("module") != "Proof"
                    or len(measured) != len(charged) or set(measured) != set(charged)
                    or audit.get("package_declarations") != required
                    or not set(audit.get("axioms_used", [])) <= set(CORE_AXIOMS)
                    or len(targets) != 1 or targets[0].get("name") != "Submission.solve"
                    or targets[0].get("expected") != request["task"]["goal"]
                    or targets[0].get("goal_preserved") is not True):
                raise CorpusError("audit does not match the frozen attempt")
            row = targets[0]["source"]
            if row["declaration_tokens"] != row["signature_tokens"] + row["body_tokens"] + 1:
                raise CorpusError("inconsistent source partition")
            result.update(status="verified", audit=audit)
        except VerificationFailure as exc:
            result.update(status="rejected" if exc.kind == "verification_failed" else "inconclusive",
                          failure={"kind": exc.kind, "stage": exc.stage, "message": exc.message})
        except (CorpusError, OSError, ValueError) as exc:
            result.update(status="inconclusive", failure={
                "kind": "controller_error", "stage": "controller", "message": str(exc)})
    return result


def submit_attempt(path, submission, *, lean="lean"):
    root, _, frozen = load_session(path)
    if not isinstance(submission, dict):
        raise CorpusError("submission must be an object")
    if set(submission) - {"task_id", "request_sha256", "proof", "bridge", "generation"}:
        raise CorpusError("submission has unsupported fields; targets and budgets are controller-owned")
    task_id = submission.get("task_id")
    request = task_request(path, task_id)
    if submission.get("request_sha256") != request["request_sha256"]:
        raise CorpusError("submission belongs to a different task, condition or frozen session")
    proof = nonempty_string(submission.get("proof"), "proof")
    nonempty_string(submission.get("bridge"), "bridge")
    if len(proof.encode()) > frozen["manifest"]["budget"]["max_proof_bytes"]:
        raise CorpusError("proof exceeds the frozen response-size budget")
    with session_lock(root):
        task_folder = root / "attempts" / task_id
        task_folder.mkdir(exist_ok=True)
        previous = list((root / "reservations").glob(task_id + "-*.json"))
        limit = frozen["manifest"]["budget"]["max_attempts_per_task"]
        if len(previous) >= limit:
            raise CorpusError("frozen attempt budget exhausted")
        number = len(previous) + 1
        attempt = task_folder / f"{number:03d}"
        source = proof_source(request, proof)
        pending = {"task_id": task_id, "attempt": number, "request_sha256": request["request_sha256"],
                   "proof_sha256": digest(source.encode()), "submission_sha256": digest(canonical(submission)),
                   "generation_usage": "caller supplied; not independently verified"}
        # Reserve before Lean starts. Interruptions consume the same attempt slot.
        save_new(root / "reservations" / f"{task_id}-{number:03d}.json", seal(pending))
        attempt.mkdir(exist_ok=False)
        save_new(attempt / "submission.json", submission)
        (attempt / "Proof.lean").write_text(source, encoding="utf-8")
        save_new(attempt / "pending.json", seal(pending))
        try:
            result = {**pending, **verify_attempt(frozen, request, source, attempt, lean=lean)}
        except (CorpusError, OSError, ValueError) as exc:
            result = {**pending, "status": "inconclusive", "trace": [], "audit": None,
                      "failure": {"kind": "controller_error", "stage": "controller", "message": str(exc)}}
        save_new(attempt / "result.json", seal(result))
        return {**result, "artifact": str(attempt)}


def session_report(path):
    root, session, frozen = load_session(path)
    rows = []
    for task in frozen["manifest"]["tasks"]:
        folder = root / "attempts" / task["id"]
        attempts, successes = [], []
        reserved = sorted((root / "reservations").glob(task["id"] + "-*.json"))
        if len(reserved) > frozen["manifest"]["budget"]["max_attempts_per_task"]:
            raise CorpusError("recorded attempts exceed the frozen budget")
        expected_dirs = {f"{i:03d}" for i in range(1, len(reserved) + 1)}
        if folder.exists() and {p.name for p in folder.iterdir()} - expected_dirs:
            raise CorpusError("attempt artifact has no reservation")
        for number, reservation in enumerate(reserved, 1):
            pending = unseal(reservation)
            attempt = folder / f"{number:03d}"
            request = task_request(path, task["id"])
            if (pending["task_id"] != task["id"] or pending["attempt"] != number
                    or pending["request_sha256"] != request["request_sha256"]):
                raise CorpusError("attempt reservation does not match its task or request")
            if not (attempt / "result.json").exists():
                attempts.append({"attempt": number, "status": "incomplete", "failure": None,
                                 "artifact": str(attempt.relative_to(root))})
                continue
            if (unseal(attempt / "pending.json") != pending
                    or pending["proof_sha256"] != digest((attempt / "Proof.lean").read_bytes())
                    or pending["submission_sha256"] != digest(canonical(read_object(attempt / "submission.json")))):
                raise CorpusError("attempt source, submission or request fingerprint changed")
            result = unseal(attempt / "result.json") if (attempt / "result.json").exists() else {
                **pending, "status": "incomplete", "audit": None, "trace": []}
            if any(result.get(k) != v for k, v in pending.items()):
                raise CorpusError("attempt result does not match its reservation")
            for command in result["trace"]:
                for log in command["logs"].values():
                    if digest(inside(attempt, log["path"], "log path").read_bytes()) != log["sha256"]:
                        raise CorpusError("attempt command log fingerprint changed")
            attempts.append({"attempt": pending["attempt"], "status": result["status"],
                             "failure": result.get("failure"), "artifact": str(attempt.relative_to(root))})
            if result["status"] == "verified":
                audit = result["audit"]
                source = {s["module"]: s["source_tokens"] for s in audit["sources"]}
                successes.append({"attempt": pending["attempt"], "target": audit["targets"][0],
                                  "proof_source_tokens": source["Proof"],
                                  "package_source_tokens": sum(v for k, v in source.items() if k != "Proof")})
        best = min(successes, key=lambda a: (a["proof_source_tokens"], a["target"]["proof_expr_nodes"], a["attempt"])) if successes else None
        rows.append({**task, "attempts": attempts, "status": "verified" if best else "not_observed_solved",
                     "selected": best})
    return {"schema_version": 1, "status": "session_summary", "condition": session["condition"],
            "solver": session["solver"], "fingerprints": session["fingerprints"],
            "budget": frozen["manifest"]["budget"], "tasks": rows,
            "selection": "least full proof-module source tokens among verified attempts within frozen budget",
            "held_out_evaluation": False, "training_eligible": False,
            "unsolved_meaning": "no verified witness observed under this budget; mathematical value remains unknown"}


def compare_sessions(baseline, treatment):
    left, right = session_report(baseline), session_report(treatment)
    if left["condition"] != "baseline" or right["condition"] != "treatment":
        raise CorpusError("comparison requires baseline then treatment")
    if any(left[field] != right[field] for field in ("fingerprints", "budget", "solver")):
        raise CorpusError("comparison requires identical frozen suite, solver identity/mode and budgets")
    solved = [{t["id"] for t in report["tasks"] if t["selected"]} for report in (left, right)]
    common = solved[0] & solved[1]
    costs, rows, package_cost = [], [], None
    for report in (left, right):
        chosen = [t["selected"] for t in report["tasks"] if t["id"] in common]
        packages = {r["package_source_tokens"] for r in chosen}
        if len(packages) > 1:
            raise CorpusError("package cost differs across tasks in a frozen session")
        fixed = next(iter(packages), 0)
        if report["condition"] == "treatment":
            package_cost = fixed if common else None
        costs.append(sum(r["proof_source_tokens"] for r in chosen) + fixed)
    for a, b in zip(left["tasks"], right["tasks"]):
        if a["id"] != b["id"]:
            raise CorpusError("comparison task order differs")
        before, after = a["selected"], b["selected"]
        rows.append({"id": a["id"], "split": a["split"], "family": a["family"],
                     "baseline": a["status"], "treatment": b["status"],
                     "local_body_tokens_saved": before["target"]["source"]["body_tokens"] - after["target"]["source"]["body_tokens"] if before and after else None,
                     "local_expr_nodes_saved": before["target"]["proof_expr_nodes"] - after["target"]["proof_expr_nodes"] if before and after else None})
    return {"schema_version": 1, "status": "observed_comparison", "fingerprints": left["fingerprints"],
            "solver": left["solver"], "budget": left["budget"], "tasks": rows,
            "coverage": {"baseline": sorted(solved[0]), "treatment": sorted(solved[1]),
                         "relation": "same" if solved[0] == solved[1] else "treatment_superset" if solved[0] < solved[1] else "baseline_superset" if solved[1] < solved[0] else "incomparable"},
            "common_task_source_ledger": {"task_ids": sorted(common),
                "baseline_tokens": costs[0] if common else None,
                "treatment_including_package_tokens": costs[1] if common else None,
                "package_tokens_charged_once": package_cost,
                "net_tokens_saved": costs[0] - costs[1] if common else None,
                "scope": "common solved tasks only; full proof modules and full candidate once; shared base and statements cancel"},
            "held_out_evaluation": False, "generation_budget_verified": False, "training_eligible": False,
            "judgement": "contextual evidence from observed attempts; no scalar mathematical-interest verdict",
            "provenance": {"baseline": unseal(Path(baseline) / "session.json")["provenance"],
                           "treatment": unseal(Path(treatment) / "session.json")["provenance"]}}
