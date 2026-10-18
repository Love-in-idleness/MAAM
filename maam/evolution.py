"""Append-only package versions and task-local, later-use experiments.

This controller records observed reuse, not causal value or metered LLM search.
Earlier evaluator modules stay unchanged so their archives remain replayable.
"""
from __future__ import annotations

from itertools import combinations
import json
from pathlib import Path
import re
import shutil
import tempfile

from .ablation import (cost, frontier_relation, measure_attempt, package_uses,
                       portfolio, validate_module)
from .corpus import CorpusError
from .independent import bundle, now, restore_bundle
from .migration import (load_session, load_suite, proof_source, save_new, seal,
                        session_report, start_session, submit_attempt, task_request, unseal)
from .theory import digest, inside, read_object

SCOPE_FLAGS = ("held_out_evaluation", "generation_budget_verified", "training_eligible",
               "fair_model_performance_claim", "autonomous_discovery_claim")


def frozen_path(root, descriptor):
    path = inside(root, descriptor["path"], "frozen file")
    if digest(path.read_bytes()) != descriptor["sha256"]:
        raise CorpusError("frozen file changed: " + str(path))
    return path


def load_study(path):
    path = Path(path).resolve()
    data = read_object(path)
    if data.get("schema_version") != 1 or data.get("phase") != "version_reuse_calibration":
        raise CorpusError("expected version_reuse_calibration schema 1")
    if any(data.get("scope", {}).get(k) is not False for k in SCOPE_FLAGS):
        raise CorpusError("this study cannot certify generation fairness, held-out value or training")
    if data["solver"]["mode"] != "interactive_agent":
        raise CorpusError("expected fresh interactive solving contexts")
    rounds = data["rounds"]
    if [r["index"] for r in rounds] != list(range(len(rounds))) or len(rounds) < 3:
        raise CorpusError("rounds must be consecutive, including construction and later use")
    versions, files = {}, {path.name}
    for item in data["versions"]:
        key = item["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key in versions:
            raise CorpusError("invalid or duplicate version id")
        package_path = frozen_path(path.parent, item["package"])
        package = read_object(package_path)
        sources = item["sources"]
        if set(sources) != set(package["modules"]):
            raise CorpusError("version sources must cover its whole package")
        for descriptor in sources.values():
            frozen_path(path.parent, descriptor)
            files.add(descriptor["path"])
        files.add(item["package"]["path"])
        parent = item["parent"]
        if type(item["introduced_round"]) is not int or not 0 <= item["introduced_round"] < len(rounds):
            raise CorpusError("invalid introduction round")
        if parent is not None:
            if parent not in versions:
                raise CorpusError("parent must be an earlier version; cycles are forbidden")
            old = versions[parent]
            if item["introduced_round"] <= old["introduced_round"]:
                raise CorpusError("a child must follow its parent round")
            if (package["base_id"] != old["package_data"]["base_id"]
                    or any(sources.get(m) != d for m, d in old["sources"].items())
                    or not set(old["package_data"]["declarations"]) <= set(package["declarations"])):
                raise CorpusError("append-only versions must preserve parent modules and declarations")
        versions[key] = {**item, "package_data": package}
    variants, shared = {}, None
    for variant in data["variants"]:
        key = variant["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key in variants:
            raise CorpusError("invalid or duplicate variant")
        suite_path = frozen_path(path.parent, variant["suite"])
        frozen = load_suite(suite_path)
        suite = frozen["manifest"]
        modules = suite["base"]["modules"] + [t["module"] for t in suite["tasks"]]
        common = {"base": suite["base"], "tasks": suite["tasks"], "budget": suite["budget"],
                  "lean_version": suite["lean_version"],
                  "sources": {m: frozen["fingerprints"]["source_sha256"][m] for m in modules}}
        if shared is not None and shared != common:
            raise CorpusError("variants must share foundation, tasks, toolchain and budgets")
        shared = common
        version = variant["version"]
        if variant["condition"] == "baseline":
            if version is not None:
                raise CorpusError("baseline cannot supply a package version")
        elif variant["condition"] == "treatment" and version in versions:
            entry = versions[version]
            if (frozen["package"] != entry["package_data"]
                    or any(suite["sources"].get(m) != d for m, d in entry["sources"].items())):
                raise CorpusError("suite does not supply the registered version")
            if entry["introduced_round"] >= data["evaluation_round"]:
                raise CorpusError("later-use evaluation must follow package introduction")
        else:
            raise CorpusError("unknown condition or package version")
        files.update([variant["suite"]["path"], suite["package"]])
        files.update(d["path"] for d in suite["sources"].values())
        variants[key] = {**variant, "suite_path": suite_path, "frozen": frozen}
    if sum(v["condition"] == "baseline" for v in variants.values()) != 1 or len(variants) < 2:
        raise CorpusError("one baseline and at least one package condition are required")
    if {v["version"] for v in variants.values() if v["version"]} != set(versions):
        raise CorpusError("each registered version needs an evaluated condition")
    if data["evaluation_round"] != len(rounds) - 1:
        raise CorpusError("evaluation must be the final frozen round")
    order = data["launch_order"]
    expected = {(v, t["id"]) for v in variants for t in shared["tasks"]}
    if (len(order) != len(expected) or {(r["variant"], r["task_id"]) for r in order} != expected
            or len({r["worker"] for r in order}) != len(order)
            or any(not re.fullmatch(r"[a-z][a-z0-9]*", r["worker"]) for r in order)):
        raise CorpusError("launch order must cover each task/variant once with unique workers")
    for key in ("per_command_timeout_seconds", "total_timeout_seconds", "max_heartbeats"):
        if type(data["measurement_budget"].get(key)) is not int or data["measurement_budget"][key] <= 0:
            raise CorpusError("invalid measurement budget")
    if type(data["max_frontier_states"]) is not int or data["max_frontier_states"] < 1:
        raise CorpusError("invalid portfolio budget")
    return {"manifest": data, "versions": versions, "variants": variants,
            "shared": shared, "files": sorted(files), "path": path}


def evaluator_fingerprints():
    folder = Path(__file__).parent
    return {name: digest((folder / name).read_bytes()) for name in (
        "evolution.py", "migration.py", "theory.py", "PackageCheck.lean",
        "ablation.py", "Inventory.lean", "independent.py")}


def prepare(study_path, root, workers, skill, freeze_commit, *, construction=None, runtime=None):
    study = load_study(study_path)
    root, workers, skill = map(lambda p: Path(p).resolve(), (root, workers, skill))
    if root == workers or root in workers.parents or workers in root.parents:
        raise CorpusError("controller and worker directories must be separate")
    if not re.fullmatch(r"[0-9a-f]{40}", freeze_commit):
        raise CorpusError("an explicit frozen Git commit is required")
    actual = {str(p.relative_to(skill)): digest(p.read_bytes()) for p in skill.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts}
    data = study["manifest"]
    if actual != data["worker_skill_sha256"]:
        raise CorpusError("worker skill differs from the frozen skill")
    root.mkdir(parents=True, exist_ok=False)
    workers.mkdir(parents=True, exist_ok=False)
    for name in study["files"]:
        dest = root / "input" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(study["path"].parent / name, dest)
    shutil.copytree(skill, workers / "skill", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(workers / "skill", root / "worker-skill")
    for name in ("prompts", "launches", "returns", "raw-submissions", "feedback"):
        (root / name).mkdir()
    for key, variant in study["variants"].items():
        start_session(root / "input" / variant["suite"]["path"], root / key,
                      condition=variant["condition"], solver_id=data["solver"]["id"])
    for row in data["launch_order"]:
        folder = workers / row["worker"]
        folder.mkdir()
        save_new(folder / "request.json", task_request(root / row["variant"], row["task_id"]))
        (root / "prompts" / (row["worker"] + ".txt")).write_text(data["prompt_template"].format(
            skill_root=str(workers / "skill"), worker_root=str(folder)))
    save_new(root / "run.json", seal({"schema_version": 1, "freeze_commit": freeze_commit,
        "study_file": study["path"].name, "study_sha256": digest(study["path"].read_bytes()),
        "evaluators": evaluator_fingerprints(), "worker_root": str(workers),
        "prepared_at": now(), "construction": construction, "runtime": runtime}))
    return {"status": "prepared", "workers": len(data["launch_order"])}


def run_record(root):
    root = Path(root)
    record = unseal(root / "run.json")
    study = load_study(root / "input" / record["study_file"])
    if (digest(study["path"].read_bytes()) != record["study_sha256"]
            or evaluator_fingerprints() != record["evaluators"]):
        raise CorpusError("frozen study or evaluator changed")
    return record, study


def register(root, worker, agent_id):
    root = Path(root)
    record, study = run_record(root)
    order = study["manifest"]["launch_order"]
    rows = [r for r in order if r["worker"] == worker]
    if len(rows) != 1:
        raise CorpusError("unknown worker")
    row = rows[0]
    previous = sorted((root / "launches").glob("*.json"))
    if (len(previous) != order.index(row) or not isinstance(agent_id, str) or not agent_id
            or any(unseal(p)["agent_id"] == agent_id for p in previous)):
        raise CorpusError("use fresh contexts in the frozen order")
    prompt = study["manifest"]["prompt_template"].format(
        skill_root=str(Path(record["worker_root"]) / "skill"),
        worker_root=str(Path(record["worker_root"]) / worker))
    if prompt != (root / "prompts" / (worker + ".txt")).read_text():
        raise CorpusError("worker prompt changed")
    value = {**row, "index": order.index(row), "agent_id": agent_id,
             "fork_turns": "none", "model_override": None, "prompt": prompt,
             "registered_at": now(), "timestamp_scope": "registration after spawn returned"}
    save_new(root / "launches" / (worker + ".json"), seal(value))
    return value


def verify_return(root, worker, number, *, lean="lean"):
    root = Path(root)
    record, _ = run_record(root)
    if shutil.which(lean) is None or shutil.which("lean") is None:
        raise CorpusError("warm pinned Lean and expose child lean on PATH before submitting")
    row = unseal(root / "launches" / (worker + ".json"))
    session = root / row["variant"]
    task = next(t for t in session_report(session)["tasks"] if t["id"] == row["task_id"])
    limit = session_report(session)["budget"]["max_attempts_per_task"]
    if (type(number) is not int or number > limit or task["selected"] is not None
            or len(task["attempts"]) + 1 != number):
        raise CorpusError("stop after first success; preserve consecutive attempts")
    folder = Path(record["worker_root"]) / worker
    request = read_object(folder / "request.json")
    if request != task_request(session, row["task_id"]):
        raise CorpusError("worker request changed")
    raw = (folder / f"submission-{number:02d}.json").read_bytes()
    submission = json.loads(raw)
    if (submission["proof"] != (folder / f"proof-{number:02d}.lean").read_text()
            or submission["bridge"] != (folder / f"bridge-{number:02d}.txt").read_text().strip()):
        raise CorpusError("returned proof or bridge differs from packaged submission")
    stem = f"{worker}-{number:03d}.json"
    with (root / "raw-submissions" / stem).open("xb") as out:
        out.write(raw)
    save_new(root / "returns" / stem, seal({"worker": worker, "attempt": number,
        "request": request, "submission": submission, "raw_sha256": digest(raw), "received_at": now()}))
    result = submit_attempt(session, submission, lean=lean)
    remaining = request["budget"]["max_attempts_per_task"] - number
    feedback = {"worker": worker, "attempt": number, "status": result["status"],
                "failure": result.get("failure"), "remaining_attempts": remaining,
                "stop": result["status"] == "verified" or remaining == 0}
    save_new(root / "feedback" / stem, seal(feedback))
    return feedback


def measure(root, *, lean="lean"):
    root = Path(root)
    _, study = run_record(root)
    outcomes = []
    for key in study["variants"]:
        session = root / key
        _, _, frozen = load_session(session)
        for task in session_report(session)["tasks"]:
            if task["selected"] is None:
                continue
            attempt = session / "attempts" / task["id"] / f"{task['selected']['attempt']:03d}"
            if not (attempt / "measurement/result.json").exists():
                result = measure_attempt(frozen, task_request(session, task["id"]), attempt,
                                         study["manifest"]["measurement_budget"], lean=lean)
                outcomes.append({"variant": key, "task": task["id"], "status": result["status"]})
                print(key, task["id"], result["status"], flush=True)
    return outcomes


def dependency_paths(proof, packages):
    declarations = {d["name"]: d for m in [proof] + packages for d in m["declarations"]}
    candidates = {d["name"] for m in packages for d in m["declarations"]}
    queue, paths = [["Submission.solve"]], {"Submission.solve": ["Submission.solve"]}
    for chain in queue:
        for name in declarations.get(chain[-1], {}).get("direct_dependencies", []):
            if name not in paths:
                paths[name] = chain + [name]
                queue.append(paths[name])
    return {name: paths[name] for name in sorted(candidates & paths.keys())}


def measured_variant(root, key, variant):
    session = Path(root) / key
    report = session_report(session)
    _, _, frozen = load_session(session)
    rows, components, packages, uses = [], None, None, []
    seconds = {"verification": 0.0, "inventory": 0.0}
    for task in report["tasks"]:
        row = {"id": task["id"], "attempts": []}
        for event in task["attempts"]:
            option = {"attempt": event["attempt"], "status": event["status"], "cost": None}
            row["attempts"].append(option)
            if event["status"] == "incomplete":
                continue
            attempt = session / event["artifact"]
            result = unseal(attempt / "result.json")
            submission = read_object(attempt / "submission.json")
            request = task_request(session, task["id"])
            if digest(proof_source(request, submission["proof"]).encode()) != result["proof_sha256"]:
                raise CorpusError("proof differs from its canonical submitted term")
            seconds["verification"] += sum(c["seconds"] for c in result["trace"])
            measured_path = attempt / "measurement/result.json"
            if result["status"] != "verified" or not measured_path.exists():
                continue
            measured = unseal(measured_path)
            for command in measured["trace"]:
                for log in command["logs"].values():
                    if digest(inside(attempt / "measurement", log["path"], "log").read_bytes()) != log["sha256"]:
                        raise CorpusError("inventory log changed")
            seconds["inventory"] += sum(c["seconds"] for c in measured["trace"])
            if (measured["proof_sha256"] != result["proof_sha256"]
                    or measured["formal_result_sha256"] != digest((attempt / "result.json").read_bytes())):
                raise CorpusError("inventory is not bound to its verified proof")
            if measured["status"] != "measured":
                continue
            modules = measured["inventory"]["modules"]
            expected = (frozen["package"]["modules"] if variant["condition"] == "treatment" else []) + ["Proof"]
            if [m["module"] for m in modules] != expected:
                raise CorpusError("inventory modules differ from the frozen version")
            for module in modules:
                validate_module(module)
            proof = modules[-1]
            target = result["audit"]["targets"][0]
            decl = next(d for d in proof["declarations"] if d["name"] == "Submission.solve")
            if (decl["signature_expr_nodes"] != target["signature_expr_nodes"]
                    or decl["value_expr_nodes"] != target["proof_expr_nodes"]):
                raise CorpusError("inventory target differs from the correctness audit")
            source = {s["module"]: s["source_tokens"] for s in result["audit"]["sources"]}
            current = {m["module"]: {**cost(source[m["module"]], m["expr_nodes"]),
                "sha256": frozen["fingerprints"]["source_sha256"][m["module"]]} for m in modules[:-1]}
            if components is not None and (components != current or packages != modules[:-1]):
                raise CorpusError("frozen package cost changed across tasks")
            components, packages = current, modules[:-1]
            paths = dependency_paths(proof, packages)
            if sorted(paths) != package_uses(proof, packages):
                raise CorpusError("dependency path traversal disagrees with package-use audit")
            option.update(cost=cost(source["Proof"], proof["expr_nodes"]), dependency_paths=paths)
            for module in packages:
                for declaration in module["declarations"]:
                    name = declaration["name"]
                    if name in paths:
                        uses.append({"task": task["id"], "attempt": event["attempt"],
                                     "module": module["module"], "declaration": name, "path": paths[name]})
        rows.append(row)
    package_cost = None if components is None else cost(
        sum(v["source_tokens"] for v in components.values()), sum(v["expr_nodes"] for v in components.values()))
    return {"id": key, "version": variant["version"], "tasks": rows,
            "components": components, "package_cost": package_cost,
            "uses": uses, "verification_seconds": seconds}


def summarize(root):
    root = Path(root)
    record, study = run_record(root)
    data = study["manifest"]
    actual_skill = {str(p.relative_to(root / "worker-skill")): digest(p.read_bytes())
                    for p in (root / "worker-skill").rglob("*") if p.is_file()}
    if actual_skill != data["worker_skill_sha256"]:
        raise CorpusError("archived worker skill changed")
    reports = {k: session_report(root / k) for k in study["variants"]}
    expected, agents, failures, complete = set(), set(), [], True
    for index, row in enumerate(data["launch_order"]):
        launch_path = root / "launches" / (row["worker"] + ".json")
        if not launch_path.exists():
            complete = False
            continue
        launch = unseal(launch_path)
        prompt = data["prompt_template"].format(skill_root=str(Path(record["worker_root"]) / "skill"),
                    worker_root=str(Path(record["worker_root"]) / row["worker"]))
        if (any(launch[k] != v for k, v in row.items()) or launch["index"] != index
                or launch["fork_turns"] != "none" or launch["model_override"] is not None
                or launch["agent_id"] in agents or launch["prompt"] != prompt
                or (root / "prompts" / (row["worker"] + ".txt")).read_text() != prompt):
            raise CorpusError("launch violates the fresh-context protocol")
        agents.add(launch["agent_id"])
        task = next(t for t in reports[row["variant"]]["tasks"] if t["id"] == row["task_id"])
        request = task_request(root / row["variant"], row["task_id"])
        complete &= bool(task["selected"] or len(task["attempts"]) == request["budget"]["max_attempts_per_task"])
        succeeded = False
        for event in task["attempts"]:
            if succeeded or event["status"] == "incomplete":
                raise CorpusError("unfinished attempts or attempts after success cannot be finalized")
            stem = f"{row['worker']}-{event['attempt']:03d}.json"
            expected.add(stem)
            returned = unseal(root / "returns" / stem)
            feedback = unseal(root / "feedback" / stem)
            raw = (root / "raw-submissions" / stem).read_bytes()
            submission = read_object(root / row["variant"] / event["artifact"] / "submission.json")
            remaining = request["budget"]["max_attempts_per_task"] - event["attempt"]
            if (returned["worker"] != row["worker"] or returned["attempt"] != event["attempt"]
                    or returned["request"] != request or returned["submission"] != submission
                    or digest(raw) != returned["raw_sha256"] or json.loads(raw) != submission
                    or feedback != {"worker": row["worker"], "attempt": event["attempt"],
                        "status": event["status"], "failure": event["failure"],
                        "remaining_attempts": remaining, "stop": event["status"] == "verified" or remaining == 0}):
                raise CorpusError("returned proof or own-condition feedback changed")
            succeeded = event["status"] == "verified"
            if not succeeded:
                failures.append({**row, **event})
    for folder in ("returns", "raw-submissions", "feedback"):
        if {p.name for p in (root / folder).iterdir()} != expected:
            raise CorpusError("extra or missing attempt records")
    if {p.stem for p in (root / "launches").iterdir()} - {r["worker"] for r in data["launch_order"]}:
        raise CorpusError("unregistered worker record")
    variants = [measured_variant(root, k, v) for k, v in study["variants"].items()]
    coverage = {v["id"]: {"verified": [r["id"] for r in v["tasks"] if any(a["status"] == "verified" for a in r["attempts"])],
                "measured": [r["id"] for r in v["tasks"] if any(a["cost"] is not None for a in r["attempts"])]} for v in variants}
    complete &= all(c["verified"] == c["measured"] for c in coverage.values())
    pairs = []
    for left, right in combinations(variants, 2):
        common = [t["id"] for t in study["shared"]["tasks"] if all(t["id"] in coverage[v["id"]]["measured"] for v in (left, right))]
        a, b = set(coverage[left["id"]]["verified"]), set(coverage[right["id"]]["verified"])
        lf, rf = (portfolio(v["tasks"], v["package_cost"], common, data["max_frontier_states"]) for v in (left, right))
        pairs.append({"left": left["id"], "right": right["id"], "common_tasks": common,
            "coverage_relation": "same" if a == b else "left_superset" if a > b else "right_superset" if b > a else "incomparable",
            "cost_relation": frontier_relation(lf, rf), "left_costs": lf, "right_costs": rf})
    by_version = {v["version"]: v for v in variants if v["version"]}
    version_ledger, delayed = [], []
    for key, entry in study["versions"].items():
        evidence = by_version[key]
        inherited = {} if entry["parent"] is None else study["versions"][entry["parent"]]["sources"]
        added = [m for m in entry["sources"] if m not in inherited]
        components = evidence["components"]
        if entry["parent"] is not None and components is not None:
            old = by_version[entry["parent"]]["components"]
            if old is not None and any(components[m] != old[m] for m in inherited):
                raise CorpusError("inherited component costs changed across versions")
        incremental = None if components is None else cost(
            sum(components[m]["source_tokens"] for m in added), sum(components[m]["expr_nodes"] for m in added))
        version_ledger.append({"version": key, "parent": entry["parent"],
            "introduced_round": entry["introduced_round"], "added_modules": added,
            "incremental_representation_cost": incremental, "whole_package_cost": evidence["package_cost"]})
        for use in evidence["uses"]:
            if use["module"] in added:
                delayed.append({"version": key, "introduced_round": entry["introduced_round"],
                                "used_round": data["evaluation_round"], **use})
    return {"schema_version": 1, "status": "completed" if complete else "incomplete",
        "study_id": data["study_id"], "freeze_commit": record["freeze_commit"],
        "study_sha256": record["study_sha256"], "evaluators": record["evaluators"],
        "rounds": data["rounds"], "registered_workers": len(agents), "attempts": len(expected),
        "failures": failures, "coverage": coverage, "variants": variants, "pairs": pairs,
        "version_ledger": version_ledger, "later_uses": delayed,
        "construction": record["construction"], "generation": data["solver"]["generation"],
        "scope": data["scope"],
        "interpretation": "Observed dependency paths include declaration types and are evidence of later reuse, not a causal value estimate. Whole packages are charged once per comparison; inherited modules are not charged twice. Generation and construction search costs remain unknown where unobserved."}


def export_run(root, output):
    summary = summarize(root)
    if summary["status"] != "completed":
        raise CorpusError("cannot export an incomplete cohort or missing inventories")
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _, study = run_record(root)
    save_new(output / "summary.json", summary)
    for key in study["variants"]:
        save_new(output / (key + ".json"), bundle(root / key))
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp)
        for source in root.iterdir():
            if source.name not in study["variants"]:
                if source.is_dir():
                    shutil.copytree(source, target / source.name)
                else:
                    shutil.copyfile(source, target / source.name)
        save_new(output / "controller.json", bundle(target))
    return summary


def restore_archive(archive, root):
    archive, root = Path(archive), Path(root)
    root.mkdir(parents=True, exist_ok=False)
    restore_bundle(read_object(archive / "controller.json"), root)
    _, study = run_record(root)
    for key in study["variants"]:
        restore_bundle(read_object(archive / (key + ".json")), root / key)
    result = summarize(root)
    if result != read_object(archive / "summary.json"):
        raise CorpusError("summary differs from complete archived evidence")
    return result


def replay_archive(archive, output, *, lean="lean"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temp:
        original = Path(temp) / "original"
        summary = restore_archive(archive, original)
        _, study = run_record(original)
        for key, variant in study["variants"].items():
            start_session(variant["suite_path"], output / key, condition=variant["condition"],
                          solver_id="evolution-archive-replay", mode="supplied_reference")
        cases = []
        for row in study["manifest"]["launch_order"]:
            key, tid = row["variant"], row["task_id"]
            old_task = next(t for t in session_report(original / key)["tasks"] if t["id"] == tid)
            for event in old_task["attempts"]:
                old_path = original / key / event["artifact"]
                old = unseal(old_path / "result.json")
                submission = read_object(old_path / "submission.json")
                request = task_request(output / key, tid)
                submission["request_sha256"] = request["request_sha256"]
                new = submit_attempt(output / key, submission, lean=lean)
                matched = new["status"] == old["status"] and new["proof_sha256"] == old["proof_sha256"]
                if old["status"] == "verified":
                    _, _, frozen = load_session(output / key)
                    measured = measure_attempt(frozen, request, new["artifact"], study["manifest"]["measurement_budget"], lean=lean)
                    expected = unseal(old_path / "measurement/result.json")
                    matched &= measured["status"] == expected["status"] == "measured" and measured["inventory"] == expected["inventory"]
                else:
                    matched &= all(new.get("failure", {}).get(k) == old.get("failure", {}).get(k) for k in ("kind", "stage"))
                cases.append({**row, "attempt": event["attempt"], "original_status": old["status"],
                              "status": new["status"], "matched": bool(matched)})
                print(key, tid, event["attempt"], new["status"], bool(matched), flush=True)
        result = {"status": "passed" if cases and all(c["matched"] for c in cases) else "failed",
                  "attempts": len(cases), "cases": cases, "original_scope": summary["scope"],
                  "summary_sha256": digest((Path(archive) / "summary.json").read_bytes()),
                  "scope": "Recheck archived proofs and complete inventories; no new model generation"}
        save_new(output / "validation.json", result)
        return result
