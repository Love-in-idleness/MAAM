"""Verified finite proof portfolios, whole-package costs and contextual orders."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .corpus import CorpusError
from .migration import (canonical, load_suite, proof_source, save_new, seal,
                        start_session, submit_attempt, task_request, unseal)
from .theory import CHECKER, digest, inside, read_object

INVENTORY = Path(__file__).with_name("Inventory.lean")


def frozen_file(root, descriptor, label):
    if not isinstance(descriptor, dict):
        raise CorpusError(f"{label} must be a frozen file descriptor")
    path = inside(root, descriptor.get("path"), label)
    if descriptor.get("sha256") != digest(path.read_bytes()):
        raise CorpusError(f"{label} fingerprint mismatch")
    return path


def load_study(path):
    path = Path(path).resolve()
    data = read_object(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("phase") != "package_ablation_calibration":
        raise CorpusError("expected package_ablation_calibration schema 1")
    if not isinstance(data.get("study_id"), str) or not data["study_id"]:
        raise CorpusError("study_id must be nonempty")
    if type(data.get("max_frontier_states")) is not int or data["max_frontier_states"] < 1:
        raise CorpusError("max_frontier_states must be a positive integer")
    budget = data.get("measurement_budget", {})
    for field in ("per_command_timeout_seconds", "total_timeout_seconds", "max_heartbeats"):
        if type(budget.get(field)) is not int or budget[field] <= 0:
            raise CorpusError("invalid measurement budget")
    variants = data.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        raise CorpusError("ablation needs at least two variants")
    loaded, identities, shared = [], [], None
    for variant in variants:
        if not isinstance(variant, dict) or not re.fullmatch(r"[a-z][a-z0-9_]*", variant.get("id", "")):
            raise CorpusError("invalid variant id")
        identities.append(variant["id"])
        if variant.get("condition") not in {"baseline", "treatment"}:
            raise CorpusError("invalid ablation condition")
        suite_path = frozen_file(path.parent, variant.get("suite"), "suite")
        frozen = load_suite(suite_path)
        suite = frozen["manifest"]
        modules = suite["base"]["modules"] + [t["module"] for t in suite["tasks"]]
        invariant = {"base": suite["base"], "tasks": suite["tasks"], "budget": suite["budget"],
                     "lean_version": suite["lean_version"],
                     "sources": {m: frozen["fingerprints"]["source_sha256"][m] for m in modules}}
        if shared is None:
            shared = invariant
        elif invariant != shared:
            raise CorpusError("ablation variants must share identical foundation, goals, splits, toolchain and budgets")
        witnesses_path = frozen_file(path.parent, variant.get("witnesses"), "witnesses")
        witnesses = read_object(witnesses_path)
        pools = witnesses.get("tasks")
        if witnesses.get("schema_version") != 1 or not isinstance(pools, dict) or set(pools) != {t["id"] for t in suite["tasks"]}:
            raise CorpusError("witnesses must list every frozen task exactly once")
        for pool in pools.values():
            if not isinstance(pool, list) or not 1 <= len(pool) <= suite["budget"]["max_attempts_per_task"]:
                raise CorpusError("supplied proof pool exceeds the frozen attempt cap")
            for witness in pool:
                if not isinstance(witness, dict) or set(witness) != {"label", "proof", "bridge"}:
                    raise CorpusError("witness requires label, proof and bridge")
                if any(not isinstance(v, str) or not v.strip() for v in witness.values()):
                    raise CorpusError("witness fields must be nonempty strings")
                if len(witness["proof"].encode()) > suite["budget"]["max_proof_bytes"]:
                    raise CorpusError("witness exceeds response-size budget")
        loaded.append({"variant": variant, "suite_path": suite_path, "frozen": frozen, "pools": pools})
    if len(set(identities)) != len(identities) or sum(v["condition"] == "baseline" for v in variants) != 1:
        raise CorpusError("variants need unique ids and exactly one baseline")
    # Retaining every baseline witness is an enforced control, not a prompt request.
    baseline = next(v for v in loaded if v["variant"]["condition"] == "baseline")
    for variant in loaded:
        for tid, pool in baseline["pools"].items():
            if not {w["proof"] for w in pool} <= {w["proof"] for w in variant["pools"][tid]}:
                raise CorpusError("each variant must retain all raw baseline proofs")
    fingerprints = {
        "study_sha256": digest(path.read_bytes()),
        "evaluator_sha256": digest(Path(__file__).read_bytes()),
        "inventory_sha256": digest(INVENTORY.read_bytes()),
        "checker_sha256": digest(CHECKER.read_bytes()),
        "variants": {v["variant"]["id"]: {"suite": v["frozen"]["fingerprints"],
            "witnesses_sha256": v["variant"]["witnesses"]["sha256"]} for v in loaded},
    }
    return {"manifest": data, "loaded": loaded, "shared": shared, "fingerprints": fingerprints}


def measure_attempt(frozen, request, attempt, budget, *, lean="lean"):
    """Fresh second compilation, bound to the already audited exact proof bytes."""
    attempt = Path(attempt)
    evidence = unseal(attempt / "result.json")
    source = (attempt / "Proof.lean").read_bytes()
    if evidence["status"] != "verified" or digest(source) != evidence["proof_sha256"]:
        raise CorpusError("inventory requires an unchanged verified proof")
    output = attempt / "measurement"
    output.mkdir(exist_ok=False)
    result = {"status": "pending", "trace": [], "inventory": None,
              "proof_sha256": digest(source), "formal_result_sha256": digest((attempt / "result.json").read_bytes())}
    executable = shutil.which(lean)
    if executable is None:
        result.update(status="inconclusive", failure="Lean is unavailable for inventory")
        save_new(output / "result.json", seal(result))
        return result
    deadline = time.monotonic() + budget["total_timeout_seconds"]
    env = os.environ.copy()
    env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v" + frozen["manifest"]["lean_version"]
    with tempfile.TemporaryDirectory(prefix="maam-inventory-") as temp:
        work = Path(temp)
        env["LEAN_PATH"] = str(work)

        def command(argv, stage):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("inventory total budget exhausted")
            started, timed_out = time.monotonic(), False
            try:
                proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, check=False,
                                      timeout=min(remaining, budget["per_command_timeout_seconds"]))
                stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, code, timed_out = exc.stdout or b"", exc.stderr or b"", None, True
            logs = {}
            for name, content in (("stdout", stdout), ("stderr", stderr)):
                filename = f"command-{len(result['trace']):02d}.{name}"
                (output / filename).write_bytes(content)
                logs[name] = {"path": filename, "sha256": digest(content)}
            result["trace"].append({"stage": stage, "returncode": code, "timed_out": timed_out,
                                    "seconds": time.monotonic() - started, "logs": logs})
            if timed_out:
                raise TimeoutError("inventory command timed out: " + stage)
            if code:
                raise CorpusError((stdout + stderr).decode(errors="replace")[-8000:])
            return stdout.decode(errors="replace")

        try:
            version = command([executable, "--version"], "toolchain")
            if not re.search(r"version " + re.escape(frozen["manifest"]["lean_version"]) + r"\b", version):
                raise CorpusError("inventory toolchain mismatch")
            modules = [s["module"] for s in request["sources"]]
            for module in modules + ["Proof"]:
                relative = Path(*module.split("."))
                path = work / relative.with_suffix(".lean")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(source if module == "Proof" else frozen["blobs"][module])
                command([executable, f"-DmaxHeartbeats={budget['max_heartbeats']}", "-o",
                         str(relative.with_suffix(".olean")), str(relative.with_suffix(".lean"))], "compile:" + module)
            charged = (frozen["package"]["modules"] if request["condition"] == "treatment" else []) + ["Proof"]
            save_new(work / "input.json", {"moduleName": "Proof", "allowedModules": ["Init"] + modules + ["Proof"],
                                           "chargedModules": charged})
            command([executable, "--run", str(INVENTORY), "input.json", "output.json"], "inventory")
            inventory = read_object(work / "output.json")
            if (inventory.get("lean_version") != frozen["manifest"]["lean_version"]
                    or inventory.get("module") != "Proof"
                    or [m["module"] for m in inventory.get("modules", [])] != charged):
                raise CorpusError("inventory does not match the frozen attempt")
            for module in inventory["modules"]:
                validate_module(module)
            proof_module = next(m for m in inventory["modules"] if m["module"] == "Proof")
            target = next((d for d in proof_module["declarations"] if d["name"] == "Submission.solve"), None)
            audited = evidence["audit"]["targets"][0]
            if target is None or any(target[k] != audited[j] for k, j in (
                    ("signature_expr_nodes", "signature_expr_nodes"), ("value_expr_nodes", "proof_expr_nodes"))):
                raise CorpusError("inventory target differs from the formal audit")
            result.update(status="measured", inventory=inventory)
        except (TimeoutError, CorpusError, OSError, ValueError) as exc:
            result.update(status="inconclusive", failure=str(exc))
    save_new(output / "result.json", seal(result))
    return result


def validate_module(module):
    declarations = module.get("declarations", [])
    if not declarations or len({d["name"] for d in declarations}) != len(declarations):
        raise CorpusError("inventory declarations are empty or duplicated")
    for decl in declarations:
        if any(type(decl.get(k)) is not int or decl[k] < 0 for k in ("signature_expr_nodes", "value_expr_nodes")):
            raise CorpusError("invalid expression inventory count")
    if (module.get("declaration_count") != len(declarations)
            or module.get("expr_nodes") != sum(d["signature_expr_nodes"] + d["value_expr_nodes"] for d in declarations)):
        raise CorpusError("expression inventory total is inconsistent")


def cost(source_tokens, expr_nodes):
    if any(type(x) is not int or x < 0 for x in (source_tokens, expr_nodes)):
        raise CorpusError("cost coordinates must be nonnegative integers")
    return {"source_tokens": source_tokens, "expr_nodes": expr_nodes}


def weakly_better(a, b):
    return all(a[k] <= b[k] for k in ("source_tokens", "expr_nodes"))


def pareto(points):
    """One deterministic witness for each nondominated two-dimensional cost."""
    ordered = sorted(points, key=lambda p: (p["source_tokens"], p["expr_nodes"], canonical(p)))
    frontier, smallest_expr = [], None
    for point in ordered:
        cost(point["source_tokens"], point["expr_nodes"])
        if smallest_expr is None or point["expr_nodes"] < smallest_expr:
            frontier.append(point)
            smallest_expr = point["expr_nodes"]
    return frontier


def portfolio(rows, package_cost, task_ids, max_states):
    if not task_ids:
        return {"status": "no_common_tasks", "points": []}
    frontier = [{**cost(0, 0), "choices": []}]
    lookup = {r["id"]: r for r in rows}
    for tid in task_ids:
        options = [a for a in lookup[tid]["attempts"] if a.get("cost") is not None]
        if not options:
            return {"status": "missing_measured_witness", "points": []}
        candidates = [{**cost(p["source_tokens"] + a["cost"]["source_tokens"],
                              p["expr_nodes"] + a["cost"]["expr_nodes"]),
                       "choices": p["choices"] + [{"task": tid, "attempt": a["attempt"]}]}
                      for p in frontier for a in options]
        frontier = pareto(candidates)
        if len(frontier) > max_states:
            return {"status": "frontier_budget_exhausted", "points": [], "task": tid}
    return {"status": "exact_finite_portfolio", "points": [
        {**p, **cost(p["source_tokens"] + package_cost["source_tokens"],
                    p["expr_nodes"] + package_cost["expr_nodes"])} for p in frontier]}


def frontier_relation(left, right):
    if left["status"] != "exact_finite_portfolio" or right["status"] != "exact_finite_portfolio":
        return "undetermined"
    a, b = left["points"], right["points"]
    ab = all(any(weakly_better(x, y) for x in a) for y in b)
    ba = all(any(weakly_better(y, x) for y in b) for x in a)
    return "equivalent" if ab and ba else "left_dominates" if ab else "right_dominates" if ba else "incomparable"


def package_uses(proof_module, package_modules):
    declarations = {d["name"]: d for m in [proof_module] + package_modules for d in m["declarations"]}
    candidates = {d["name"] for m in package_modules for d in m["declarations"]}
    pending, seen = ["Submission.solve"], set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in declarations:
            pending.extend(declarations[name]["direct_dependencies"])
    return sorted(candidates & seen)


def run_variant(study, loaded, output, lean):
    variant, frozen = loaded["variant"], loaded["frozen"]
    session = output / variant["id"]
    start_session(loaded["suite_path"], session, condition=variant["condition"],
                  solver_id="ablation-supplied-portfolios-v1", mode="supplied_reference")
    rows, package_modules, package_cost = [], None, None
    for task in frozen["manifest"]["tasks"]:
        attempts = []
        for witness in loaded["pools"][task["id"]]:
            request = task_request(session, task["id"])
            result = submit_attempt(session, {"task_id": task["id"], "request_sha256": request["request_sha256"],
                "proof": witness["proof"], "bridge": witness["bridge"],
                "generation": {"mode": "supplied_reference", "label": witness["label"]}}, lean=lean)
            row = {"attempt": result["attempt"], "label": witness["label"], "formal_status": result["status"],
                   "formal_failure": result.get("failure"), "measurement_status": "not_run",
                   "proof_sha256": result["proof_sha256"], "cost": None}
            if result["status"] == "verified":
                measurement = measure_attempt(frozen, request, result["artifact"], study["manifest"]["measurement_budget"], lean=lean)
                row.update(measurement_status=measurement["status"], measurement_failure=measurement.get("failure"))
                if measurement["status"] == "measured":
                    modules = measurement["inventory"]["modules"]
                    proof_module = next(m for m in modules if m["module"] == "Proof")
                    packages = [m for m in modules if m["module"] != "Proof"]
                    sources = {s["module"]: s["source_tokens"] for s in result["audit"]["sources"]}
                    fixed = cost(sum(v for k, v in sources.items() if k != "Proof"), sum(m["expr_nodes"] for m in packages))
                    if package_modules is not None and (package_modules != packages or package_cost != fixed):
                        raise CorpusError("frozen package inventory changed between attempts")
                    package_modules, package_cost = packages, fixed
                    row.update(cost=cost(sources["Proof"], proof_module["expr_nodes"]),
                               target=result["audit"]["targets"][0], proof_inventory=proof_module,
                               used_package_declarations=package_uses(proof_module, packages),
                               formal_result_sha256=measurement["formal_result_sha256"],
                               measurement_result_sha256=digest((Path(result["artifact"])/"measurement/result.json").read_bytes()))
            attempts.append(row)
            print(variant["id"], task["id"], row["attempt"], row["formal_status"], row["measurement_status"], flush=True)
        rows.append({**task, "attempts": attempts})
    result = {"id": variant["id"], "condition": variant["condition"], "tasks": rows,
              "suite_fingerprints": frozen["fingerprints"], "package_cost": package_cost,
              "package_inventory": package_modules,
              "provenance": unseal(session/"session.json")["provenance"]}
    save_new(output/(variant["id"]+".json"), result)
    return result


def analyse_variants(study, variants):
    task_ids = [t["id"] for t in study["shared"]["tasks"]]
    by_id = {v["id"]: v for v in variants}
    if set(by_id) != {v["variant"]["id"] for v in study["loaded"]}:
        raise CorpusError("variant evidence set does not match the frozen study")
    for loaded in study["loaded"]:
        validate_variant(loaded, by_id[loaded["variant"]["id"]])
    coverage = {}
    for variant in variants:
        coverage[variant["id"]] = {
            "verified": [t["id"] for t in variant["tasks"] if any(a["formal_status"] == "verified" for a in t["attempts"])],
            "measured": [t["id"] for t in variant["tasks"] if any(a["cost"] is not None for a in t["attempts"])],
            "verified_attempts": sum(a["formal_status"] == "verified" for t in variant["tasks"] for a in t["attempts"]),
            "measured_attempts": sum(a["cost"] is not None for t in variant["tasks"] for a in t["attempts"])}
    common = [tid for tid in task_ids if all(tid in c["measured"] for c in coverage.values())]
    cap = study["manifest"]["max_frontier_states"]
    frontiers = {v["id"]: portfolio(v["tasks"], v["package_cost"], common, cap) for v in variants}
    pairs = []
    for left, right in combinations(variants, 2):
        a, b = set(coverage[left["id"]]["verified"]), set(coverage[right["id"]]["verified"])
        overlap = [tid for tid in task_ids if tid in coverage[left["id"]]["measured"] and tid in coverage[right["id"]]["measured"]]
        lf, rf = (portfolio(v["tasks"], v["package_cost"], overlap, cap) for v in (left, right))
        pairs.append({"left": left["id"], "right": right["id"], "common_measured_tasks": overlap,
                      "coverage_relation": "same" if a == b else "left_superset" if a > b else "right_superset" if b > a else "incomparable",
                      "cost_relation": frontier_relation(lf, rf), "left_frontier": lf, "right_frontier": rf})
    return {"schema_version": 1, "status": "observed_ablation", "study_id": study["manifest"]["study_id"],
            "fingerprints": study["fingerprints"], "coverage": coverage, "common_measured_tasks": common,
            "package_costs": {v["id"]: v["package_cost"] for v in variants}, "frontiers": frontiers, "pairs": pairs,
            "protocol": {"source": "all parsed tokens in proof modules plus full package once",
                         "expressions": "all charged declaration types and available values, including compiler auxiliaries, plus full package once; constants are not inlined",
                         "scope": "exact nondominated costs over supplied finite portfolios on common measured goals; not globally shortest proofs or intrinsic mathematical value",
                         "raw_fallbacks_retained": True, "search_performed": False},
            "held_out_evaluation": False, "generation_budget_verified": False, "training_eligible": False,
            "provenance": {v["id"]: v["provenance"] for v in variants}}


def validate_variant(loaded, evidence):
    variant, frozen = loaded["variant"], loaded["frozen"]
    if (evidence["id"] != variant["id"] or evidence["condition"] != variant["condition"]
            or evidence["suite_fingerprints"] != frozen["fingerprints"]):
        raise CorpusError("variant evidence fingerprint or condition mismatch")
    tasks = frozen["manifest"]["tasks"]
    if [r["id"] for r in evidence["tasks"]] != [t["id"] for t in tasks]:
        raise CorpusError("variant evidence has a different task set")
    packages = evidence["package_inventory"]
    if packages is not None:
        expected = frozen["package"]["modules"] if variant["condition"] == "treatment" else []
        if [m["module"] for m in packages] != expected:
            raise CorpusError("package inventory modules differ from the frozen condition")
        for module in packages:
            validate_module(module)
        fixed = evidence["package_cost"]
        cost(fixed["source_tokens"], fixed["expr_nodes"])
        if fixed["expr_nodes"] != sum(m["expr_nodes"] for m in packages):
            raise CorpusError("package expression ledger is inconsistent")
        if not packages and fixed != cost(0, 0):
            raise CorpusError("baseline must not charge a candidate package")
    for task, row in zip(tasks, evidence["tasks"]):
        if any(row[k] != task[k] for k in task):
            raise CorpusError("task evidence changed the frozen goal or split")
        pool = loaded["pools"][task["id"]]
        if len(row["attempts"]) != len(pool):
            raise CorpusError("attempt evidence is missing from the frozen portfolio")
        modules = frozen["manifest"]["base"]["modules"] + [task["module"]]
        if variant["condition"] == "treatment":
            modules += frozen["package"]["modules"]
        for i, (attempt, witness) in enumerate(zip(row["attempts"], pool), 1):
            request = {"sources": [{"module": m} for m in modules], "task": task}
            if (attempt["attempt"] != i or attempt["label"] != witness["label"]
                    or attempt["proof_sha256"] != digest(proof_source(request, witness["proof"]).encode())):
                raise CorpusError("attempt evidence does not match its frozen witness")
            if attempt["cost"] is None:
                if attempt["measurement_status"] == "measured":
                    raise CorpusError("measured attempt has no cost evidence")
                continue
            if attempt["formal_status"] != "verified" or attempt["measurement_status"] != "measured" or packages is None:
                raise CorpusError("cost comparison requires both proof verification and inventory")
            measurement = attempt["proof_inventory"]
            validate_module(measurement)
            if measurement["module"] != "Proof" or attempt["cost"]["expr_nodes"] != measurement["expr_nodes"]:
                raise CorpusError("proof expression ledger is inconsistent")
            target = attempt["target"]
            if target["name"] != "Submission.solve" or target["expected"] != task["goal"] or target["goal_preserved"] is not True:
                raise CorpusError("attempt audit changed the original goal")
            decl = next((d for d in measurement["declarations"] if d["name"] == target["name"]), None)
            if decl is None or decl["value_expr_nodes"] != target["proof_expr_nodes"] or decl["signature_expr_nodes"] != target["signature_expr_nodes"]:
                raise CorpusError("target expression audit and inventory differ")
            src = target["source"]
            cost(attempt["cost"]["source_tokens"], attempt["cost"]["expr_nodes"])
            if (src["declaration_tokens"] != src["signature_tokens"] + src["body_tokens"] + 1
                    or attempt["cost"]["source_tokens"] < src["declaration_tokens"]):
                raise CorpusError("proof source ledger is inconsistent")
            if attempt["used_package_declarations"] != package_uses(measurement, packages):
                raise CorpusError("candidate use evidence differs from its declaration graph")


def run_study(path, workdir, *, lean="lean", workers=2):
    study = load_study(path)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise CorpusError("workers must be between 1 and 4")
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=False)
    save_new(root/"frozen-study.json", {"manifest": study["manifest"], "fingerprints": study["fingerprints"]})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_variant, study, loaded, root, lean) for loaded in study["loaded"]]
        variants = [future.result() for future in futures]
    comparison = analyse_variants(study, variants)
    save_new(root/"comparison.json", comparison)
    return comparison
