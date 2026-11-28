"""Bounded, typed extraction of shared local lemmas from archived Lean proofs."""

from collections import defaultdict
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import indent

from .independent import restore_bundle
from .migration import canonical, load_session, load_suite, save_new, seal, session_report, unseal
from .proof_portfolio import METRICS, SHARED, compile_route, imports, project, proof_module, theorem_name
from .theory import CorpusError, digest, read_object

EVALUATORS = ("proof_refactor.py", "proof_portfolio.py", "RefactorSites.lean", "Inventory.lean",
              "PackageCheck.lean", "precompression.py", "migration.py", "theory.py")


def evaluator_fingerprints():
    return {name: digest(Path(__file__).with_name(name).read_bytes()) for name in EVALUATORS}


def archive_proofs(path, frozen, condition):
    with TemporaryDirectory(prefix="maam-refactor-archive-") as folder:
        directory = Path(folder)
        restore_bundle(read_object(path), directory)
        _, session, archived = load_session(directory)
        manifest = frozen["manifest"]
        task_modules = [t["module"] for t in manifest["tasks"]]
        fixed = manifest["base"]["modules"] + task_modules
        if condition == "treatment":
            fixed += frozen["package"]["modules"]
        if (session["condition"] != condition or archived["manifest"]["base"] != manifest["base"]
                or archived["manifest"]["lean_version"] != manifest["lean_version"]
                or archived["manifest"]["tasks"] != manifest["tasks"]
                or any(archived["blobs"].get(m) != frozen["blobs"][m] for m in fixed)
                or (condition == "treatment" and archived["package"] != frozen["package"])):
            raise CorpusError("archived proofs use different frozen inputs")
        terms, receipts = {}, {}
        for task in session_report(directory)["tasks"]:
            if task["selected"] is None:
                raise CorpusError("a complete verified historical portfolio is required")
            tid = task["id"]
            number = task["selected"]["attempt"]
            attempt = directory / "attempts" / tid / f"{number:03d}"
            terms[tid] = read_object(attempt / "submission.json")["proof"]
            receipts[tid] = {"attempt": number, "proof_sha256": unseal(attempt / "result.json")["proof_sha256"]}
    return terms, receipts


def splice(term, edits):
    """Splice Lean's UTF-8 byte offsets, rejecting overlapping or stale spans."""
    data = term.encode()
    end = len(data)
    for site, replacement in sorted(edits, key=lambda edit: edit[0]["start"], reverse=True):
        start, stop = site["start"], site["stop"]
        if not 0 <= start < stop <= end or not data[start:stop].startswith(b"have "):
            raise CorpusError("invalid or overlapping local proof spans")
        if not replacement:
            line_start = data.rfind(b"\n", 0, start) + 1
            line_end = data.find(b"\n", stop, end)
            if line_end >= 0 and not data[line_start:start].strip() and not data[stop:line_end].strip():
                start, stop = line_start, line_end + 1
        data = data[:start] + replacement.encode() + data[stop:]
        end = start
    return data.decode()


def compact_local(term, sites):
    edits = []
    for site in sites:
        candidate = f"have {site['name']} : {site['type']} := {site['term']}"
        candidate = candidate.replace("\n", "\n    ")
        if not site["live"]:
            # Delete the tactic contents while preserving the following line and indentation.
            candidate = ""
        if len(candidate.encode()) < site["stop"] - site["start"]:
            edits.append((site, candidate))
    return splice(term, edits)


def call_arguments(anchor, target):
    args = []
    for binder in anchor["binders"]:
        if binder["index"] is not None:
            options = [target["support"][binder["index"]]]
        else:
            options = [row["name"] for row in target["context"] if row["key"] == binder["key"]]
        if len(options) != 1 or not options[0].isidentifier():
            return None
        args.append(options[0])
    return args


def shared_candidates(terms, sites, scope):
    """Rank source-backed candidates with alpha-equivalent typed conclusion shapes."""
    groups = defaultdict(list)
    for tid in scope:
        for site in sites[tid]:
            if site["live"] and site["name"].isidentifier():
                groups[tuple(site["shape"])].append((tid, site))
    candidates = []
    for group in groups.values():
        alternatives = []
        for tid, anchor in group:
            if not anchor["eligible"] or any(not b["name"].isidentifier() for b in anchor["binders"]):
                continue
            calls = []
            for target_id, site in group:
                arguments = call_arguments(anchor, site)
                if arguments is not None:
                    calls.append((target_id, site, arguments))
            if len(calls) < 2 or (len(scope) > 1 and len({c[0] for c in calls}) < 2):
                continue
            tail = terms[tid].encode()[anchor["after_name"]:anchor["stop"]].decode()
            line_start = terms[tid].encode().rfind(b"\n", 0, anchor["start"]) + 1
            padding = " " * (anchor["start"] - line_start)
            lines = tail.splitlines()
            tail = "\n".join([lines[0], *(line.removeprefix(padding) for line in lines[1:])])
            binders = "".join(f"\n    ({b['name']} : {b['type']})" for b in anchor["binders"])
            body = binders + tail
            rough_saving = sum(site["stop"] - site["start"] - len(" ".join(args))
                               - len(site["name"]) - 26 for _, site, args in calls) - len(body.encode())
            alternatives.append({"seed": (tid, anchor), "calls": calls, "body": body,
                                 "rough_saving": rough_saving})
        if alternatives:
            candidates.append(max(alternatives, key=lambda c: c["rough_saving"]))
    return sorted(candidates, key=lambda c: -c["rough_saving"])


def apply_shared(terms, sites, candidates, base, *, local=False):
    edits, declarations, evidence = defaultdict(list), [], []
    arguments = defaultdict(set)
    for i, candidate in enumerate(candidates, 1):
        name = f"shared_{i}"
        qualified = name if local else f"Refactored.{name}"
        seed_id, seed = candidate["seed"]
        calls = []
        for tid, site, args in sorted(candidate["calls"], key=lambda call: call[1]["start"]):
            application = " ".join([qualified, *args])
            replacement = f"have {site['name']} := {application}"
            if local and not calls:
                helper = "have " + name + candidate["body"]
                replacement = helper.replace("\n", "\n  ") + "\n  " + replacement
            edits[tid].append((site, replacement))
            arguments[tid].update(args)
            calls.append({"task": tid, "local_name": site["name"], "arguments": args,
                          "source_start_byte": site["start"]})
        declarations.append(f"theorem {name}{candidate['body']}\n")
        evidence.append({"name": qualified, "seed_task": seed_id, "seed_local_name": seed["name"],
                         "seed_source_start_byte": seed["start"], "call_sites": calls})
    uses, removed = tuple(edits), []
    for tid in uses:
        replaced = {s["name"] for s, _ in edits[tid]}
        if local:
            # A copied local helper can still refer to an earlier local declaration.
            continue
        for site in sites[tid]:
            if (site["name"] not in replaced | arguments[tid] and not site["in_body"]
                    and site["users"] and set(site["users"]) <= replaced):
                edits[tid].append((site, ""))
                removed.append({"task": tid, "local_name": site["name"], "former_users": site["users"]})
    changed = {tid: splice(term, edits.get(tid, ())) for tid, term in terms.items()}
    shared = None if local or not declarations else (imports(base) + "\nnamespace Refactored\n\n"
              + "\n".join(declarations) + "\nend Refactored\n")
    return changed, shared, uses, {"lemmas": evidence, "removed_bindings": removed}


def reachable_uses(inventory, tids, modules):
    table = {d["name"]: d["direct_dependencies"] for m in inventory["modules"] for d in m["declarations"]}
    candidates = {d["name"] for m in inventory["modules"] if m["module"] in modules for d in m["declarations"]}
    paths = {}
    for tid in tids:
        root = theorem_name(tid)
        queue, seen = [[root]], {root}
        for path in queue:
            for name in dict.fromkeys(table.get(path[-1], [])):
                if name not in seen:
                    seen.add(name)
                    queue.append([*path, name])
        paths[tid] = [p for p in queue if p[-1] in candidates]
    return paths


def status(route):
    value = {k: route[k] for k in ("status", "identity", "audit_sha256", "inventory_sha256", "failure") if k in route}
    value["lean_commands"] = len(route["commands"])
    value["lean_seconds"] = round(sum(c["seconds"] for c in route["commands"]), 6)
    return value


def min_route(routes, ids, metric, *, mode="complete"):
    measured = [(name, project(route, ids, mode)) for name, route in routes.items()]
    name, cost = min(measured, key=lambda entry: entry[1][metric])
    return {"cost": cost[metric], "route": name}


def cohort_results(ids, pools, supplied, mandatory):
    rows = []
    for n in range(1, len(ids) + 1):
        for cohort in combinations(ids, n):
            metrics = {}
            for key in METRICS:
                costs = {stage: min_route(routes, cohort, key) for stage, routes in pools.items()}
                archive = project(supplied, cohort)[key]
                metrics[key] = {**costs, "archive_v2": archive,
                    "mandatory_treatment": min_route(mandatory, cohort, key, mode="mandatory") if mandatory else None,
                    "installed_treatment": min_route(pools["treatment"], cohort, key, mode="installed"),
                    "joint_saving_over_individual": costs["individual"]["cost"] - costs["prepared"]["cost"],
                    "archive_v2_saving_over_joint": costs["prepared"]["cost"] - archive,
                    "candidate_provision_difference": costs["control"]["cost"] - costs["treatment"]["cost"]}
            rows.append({"targets": list(cohort), "metrics": metrics})
    return rows


def research_run(suite_path, archives, workdir, *, lean="lean"):
    """Recheck one public development cohort and run a finite paired rewrite schedule."""
    evaluators = evaluator_fingerprints()
    frozen = load_suite(suite_path)
    tasks = frozen["manifest"]["tasks"]
    if not 2 <= len(tasks) <= 8 or any(t["split"] != "development" for t in tasks):
        raise CorpusError("the refactoring pilot requires two to eight development targets")
    if frozen["manifest"]["budget"]["max_attempts_per_task"] < 3:
        raise CorpusError("this pilot uses three preparation slots under the frozen budget")
    ids = [t["id"] for t in tasks]
    work = Path(workdir).resolve()
    work.mkdir(parents=True, exist_ok=False)
    archives = Path(archives).resolve()
    baseline_path, treatment_path = archives / "baseline.json", archives / "v2.json"
    old, old_receipts = archive_proofs(baseline_path, frozen, "baseline")
    prepared, evidence, attempted, states = {}, {}, {}, {}

    def verify(label, terms, shared=None, uses=(), *, candidate=(), installed=False, inspect=False):
        result = compile_route(frozen, tasks, terms, work / label, lean=lean, shared=shared,
                               uses_shared=uses, uses_candidate=candidate, install_candidate=installed, inspect=inspect)
        attempted[label] = status(result)
        if result["status"] == "verified":
            states[label] = (terms, shared, uses)
            if shared is not None:
                inventory = read_object(work / label / "inventory.json")
                attempted[label]["shared_dependencies"] = reachable_uses(inventory, ids, [SHARED])
        return result

    historical = verify("historical", old, inspect=True)
    if historical["status"] != "verified":
        raise CorpusError("could not recheck archived baseline; inspect historical verification")
    original_sites = historical["sites"]
    compact = {tid: compact_local(old[tid], original_sites[tid]) for tid in ids}
    individual = {"historical": historical}
    base = frozen["manifest"]["base"]["modules"]
    if compact != old:
        result = verify("individual-1", compact, inspect=True)
        if result["status"] == "verified":
            individual["individual-1"] = result
            # Preserve the shortest observed proof for each goal under the primary source metric.
            retained = {tid: compact[tid] if result["tokens"][proof_module(tid)] <
                        historical["tokens"][proof_module(tid)] else old[tid] for tid in ids}
            if retained not in (old, compact):
                merged = verify("individual-1-retained", retained, inspect=True)
                if merged["status"] == "verified":
                    individual["individual-1-retained"] = merged
    else:
        attempted["individual-1"] = {"status": "retained", "reason": "No shorter local expression found."}
    origin = min_route(individual, ids, "source_tokens")["route"]
    start = states[origin][0]
    start_sites = individual[origin]["sites"]
    local = {tid: shared_candidates(start, start_sites, [tid]) for tid in ids}
    for count in (1, 2):
        label = f"individual-{count + 1}"
        revised, details = {}, []
        for tid in ids:
            change, _, _, log = apply_shared({tid: start[tid]}, start_sites, local[tid][:count], base, local=True)
            revised.update(change)
            details.extend(log["lemmas"])
        if not details:
            attempted[label] = {"status": "retained", "reason": "No repeated typed goal within one proof."}
            continue
        result = verify(label, revised, inspect=True)
        evidence[label] = {"lemmas": details, "removed_bindings": []}
        if result["status"] == "verified":
            individual[label] = result

    prepared.update(individual)
    proposals = shared_candidates(start, start_sites, ids)
    for count in (1, 2):
        label = f"joint-{count + 1}"
        revised, helper, uses, details = apply_shared(start, start_sites, proposals[:count], base)
        evidence[label] = details
        if not details["lemmas"]:
            attempted[label] = {"status": "retained", "reason": "No reusable typed local statement."}
            continue
        result = verify(label, revised, helper, uses, inspect=True)
        if result["status"] != "verified":
            continue
        actual_use = attempted[label]["shared_dependencies"]
        if sum(bool(v) for v in actual_use.values()) < 2:
            raise CorpusError("the proposed shared lemma was not reached from at least two verified original goals")
        prepared[label] = result

    basis = min_route(prepared, ids, "source_tokens")["route"]
    terms, helper, shared_uses = states[basis]
    common = seal({"chosen_for_continuation": basis,
                   "routes": {name: route["identity"] for name, route in prepared.items()}})
    save_new(work / "frozen-preparation.json", common)

    # Two conditions run exactly the same finite reproof operations from the verified source.
    sites = prepared[basis]["sites"]
    changes = [
        ("compact", {tid: compact_local(terms[tid], sites[tid]) for tid in ids}, shared_uses),
    ]
    pending = [(tid, site) for tid in ids for site in sites[tid] if site["live"]]
    if pending:
        tid, site = max(pending, key=lambda item: item[1]["stop"] - item[1]["start"])
        tactic = f"have {site['name']} : {site['type']} := by exact?".replace("\n", "\n    ")
        available = tuple(dict.fromkeys([*shared_uses, *([tid] if helper else [])]))
        changes.append(("reprove", {**terms, tid: splice(terms[tid], [(site, tactic)])}, available))
    control, treatment, mandatory = dict(prepared), dict(prepared), {}
    for method, revised, available in changes:
        for label, pool, exposures in (("control", control, ()), ("treatment", treatment, tuple(ids))):
            name = f"{label}-{method}"
            result = verify(name, revised, helper, available, candidate=exposures)
            if result["status"] == "verified":
                pool[name] = result
            if exposures and result["status"] == "verified":
                mandatory[name] = result
                deps = reachable_uses(read_object(work / name / "inventory.json"), ids, result["candidate_modules"])
                attempted[name]["candidate_dependencies"] = deps
                detached = f"{name}-without-package"
                replay = verify(detached, revised, helper, available)
                if replay["status"] == "verified":
                    pool[detached] = replay
                elif 0 < sum(bool(v) for v in deps.values()) < len(ids):
                    reduced = f"{name}-with-needed-imports"
                    replay = verify(reduced, revised, helper, available,
                                    candidate=[tid for tid in ids if deps[tid]])
                    if replay["status"] == "verified":
                        pool[reduced] = mandatory[reduced] = replay

    # Recheck the actual union with the full package for every distinct package-free route.
    delivered = set()
    for label, route in treatment.items():
        identity = digest(canonical(route["identity"]))
        if route["candidate_modules"] or identity in delivered:
            continue
        delivered.add(identity)
        name = label + "-delivered-with-package"
        proof_terms, auxiliary_module, used = states[label]
        forced = verify(name, proof_terms, auxiliary_module, used, installed=True)
        if forced["status"] == "verified":
            mandatory[name] = forced

    # Only the archival comparator receives the supplied old treatment answers.
    supplied_terms, supplied_receipts = archive_proofs(treatment_path, frozen, "treatment")
    supplied = verify("archive-v2", supplied_terms, candidate=ids)
    if supplied["status"] != "verified":
        raise CorpusError("could not recheck archived treatment; inspect archive-v2 verification")
    attempted["archive-v2"]["candidate_dependencies"] = reachable_uses(
        read_object(work / "archive-v2" / "inventory.json"), ids, supplied["candidate_modules"])
    verify("archive-v2-without-package", supplied_terms)
    pools = {"historical": {"historical": historical}, "individual": individual,
             "prepared": prepared, "control": control, "treatment": treatment}
    combined = {**control, **treatment, **mandatory, "archive-v2": supplied}
    if evaluator_fingerprints() != evaluators:
        raise CorpusError("refactoring evaluators changed during the run")
    report = {
        "schema_version": 1, "status": "completed_development_pilot", "tasks": ids,
        "input_fingerprints": frozen["fingerprints"],
        "evaluators": evaluators,
        "archive_sha256": {p.name: digest(p.read_bytes()) for p in (baseline_path, treatment_path)},
        "archive_receipts": {"historical": old_receipts, "archive_v2": supplied_receipts},
        "preparation_sha256": digest(canonical(common)), "continuation_from": basis,
        "attempts": attempted, "shared_proposals": evidence,
        "routes": {name: {"costs": project(route, ids, "mandatory" if name in mandatory and name not in treatment else "complete"),
                           "module_tokens": route["tokens"],
                           "module_expr_nodes": route["nodes"]} for name, route in combined.items()},
        "cohorts": cohort_results(ids, pools, supplied, mandatory),
        "scope": {"preparation_slots_per_scope": 3, "continuation_slots_per_condition": len(changes),
                  "provider_calls": 0, "provider_generation_usage": None, "held_out_evaluation": False,
                  "training_eligible": False, "global_minimum_established": False},
    }
    save_new(work / "report.json", report)
    return report
