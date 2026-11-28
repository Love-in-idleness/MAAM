"""Bounded grouped proof requests over the existing frozen migration verifier.

Helpers are local Lean tactics shared by all component proofs. The controller
constructs the conjunction and fixes its component goals. This module records
supplied/interactive attempts, not independent model-generation usage.
"""
import json
from pathlib import Path
import re
import tempfile
from textwrap import indent
from uuid import uuid4

from .corpus import CorpusError
from .migration import (canonical, load_session, load_suite, save_new, seal,
                        session_lock, session_report, start_session, submit_attempt,
                        task_request, unseal)
from .precompression import compare_study
from .theory import digest, inside, names, nonempty_string, read_object

PHASES = ("preparation", "control", "treatment")
SESSIONS = ("historical", "candidate_check", *PHASES)
TOOLS = ("grouped_search.py", "migration.py", "theory.py", "PackageCheck.lean",
         "precompression.py", "attribution.py", "grouped_methods.py")


def _tools():
    return {name: digest(Path(__file__).with_name(name).read_bytes()) for name in TOOLS}


def assemble(targets, helpers, proofs):
    """A shared local context followed by controller-owned conjunction assembly."""
    if not isinstance(helpers, str) or not isinstance(proofs, dict):
        raise CorpusError("helpers must be text and proofs must be a target-to-term map")
    if set(proofs) != {t["id"] for t in targets}:
        raise CorpusError("proofs must cover every original group target exactly once")
    terms = []
    for target in targets:
        term = nonempty_string(proofs[target["id"]], "component proof")
        terms.append(f"(show {target['goal']} from\n{indent(term, '  ')}\n)")
    expression = terms[-1]
    for term in reversed(terms[:-1]):
        expression = "And.intro\n" + indent(term, "  ") + "\n" + indent(expression, "  ")
    context = indent(helpers, "  ") + "\n" if helpers.strip() else ""
    return "by\n" + context + indent("exact\n" + indent(expression, "  "), "  ")


def _suite(plan_path, snapshot):
    plan_path = Path(plan_path).resolve()
    plan = read_object(plan_path)
    if type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise CorpusError("expected grouped search schema 1")
    if plan.get("phase") != "grouped_precompression_search":
        raise CorpusError("expected grouped_precompression_search phase")
    nonempty_string(plan.get("id"), "plan id")
    targets = plan.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 8:
        raise CorpusError("group requires one to eight original targets")
    for target in targets:
        if (not isinstance(target, dict) or set(target) != {"id", "goal"}
                or not isinstance(target["id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_]*", target["id"])):
            raise CorpusError("target requires a safe id and a fixed goal name")
    names([t["goal"] for t in targets], "original goals")
    if len({t["id"] for t in targets}) != len(targets):
        raise CorpusError("duplicate group target id")
    base = plan.get("base", {})
    package = plan.get("candidate", {})
    if not isinstance(base, dict) or not isinstance(package, dict):
        raise CorpusError("base and candidate must be objects")
    modules = names(base.get("modules"), "base modules") + names(package.get("modules"), "candidate modules")
    if not isinstance(plan.get("sources"), dict) or set(plan["sources"]) != set(modules):
        raise CorpusError("sources must cover the base and package exactly")
    snapshot.mkdir(parents=True, exist_ok=False)
    descriptors = {}
    for module in modules:
        item = plan["sources"][module]
        if not isinstance(item, dict):
            raise CorpusError("source requires path and sha256")
        content = inside(plan_path.parent, item.get("path"), "source").read_bytes()
        if item.get("sha256") != digest(content):
            raise CorpusError("group source fingerprint mismatch")
        dest = snapshot.joinpath(*module.split(".")).with_suffix(".lean")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        descriptors[module] = {"path": str(dest.relative_to(snapshot)), "sha256": digest(content)}
    conjunction = " ∧ ".join(t["goal"] for t in targets)
    group = "\n".join("import " + m for m in base["modules"])
    group += f"\n\nnamespace GroupGoal\ndef goal : Prop := {conjunction}\nend GroupGoal\n"
    (snapshot / "GroupGoal.lean").write_text(group)
    descriptors["GroupGoal"] = {"path": "GroupGoal.lean", "sha256": digest(group.encode())}
    save_new(snapshot / "package.json", package)
    suite = {"schema_version": 1, "phase": "migration_calibration", "suite_id": plan["id"],
             "lean_version": plan.get("lean_version"), "base": base, "package": "package.json",
             "sources": descriptors, "tasks": [{"id": "group", "split": "development",
                 "family": "grouped", "module": "GroupGoal", "goal": "GroupGoal.goal"}],
             "budget": plan.get("budget")}
    save_new(snapshot / "suite.json", suite)
    load_suite(snapshot / "suite.json")
    return plan


def start(plan_path, output, *, solver_id, mode="supplied_reference", lean="lean"):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    plan = _suite(plan_path, root / "snapshot")
    initial = plan.get("historical", {})
    proof = assemble(plan["targets"], initial.get("helpers"), initial.get("proofs"))
    record = {"schema_version": 1, "group_id": uuid4().hex,
              "plan_sha256": digest(Path(plan_path).read_bytes()),
              "suite_fingerprints": load_suite(root / "snapshot/suite.json")["fingerprints"],
              "targets": plan["targets"], "tools": _tools(),
              "solver_id": nonempty_string(solver_id, "solver id"), "mode": mode}
    save_new(root / "group.json", seal(record))
    for phase in SESSIONS:
        start_session(root / "snapshot/suite.json", root / phase,
                      condition="treatment" if phase in {"treatment", "candidate_check"} else "baseline",
                      solver_id=solver_id, mode=mode)
    (root / "requests").mkdir()
    (root / "decisions").mkdir()
    (root / "journal.jsonl").write_bytes(b"")
    for phase in ("historical", "candidate_check"):
        request = task_request(root / phase, "group")
        result = submit_attempt(root / phase, {"task_id": "group",
            "request_sha256": request["request_sha256"], "proof": proof,
            "bridge": "Controller-assembled preflight proof of every original target."}, lean=lean)
        if result["status"] != "verified":
            raise CorpusError(f"{phase} preflight was not verified; inspect retained logs")
    return report(root)


def _load(root):
    root = Path(root).resolve()
    record = unseal(root / "group.json")
    if record["tools"] != _tools():
        raise CorpusError("group controller or evaluator changed; start a new group")
    identities = []
    for phase in SESSIONS:
        _, session, _ = load_session(root / phase)
        condition = "treatment" if phase in {"candidate_check", "treatment"} else "baseline"
        if (session["condition"] != condition or session["solver"] != {
                "id": record["solver_id"], "mode": record["mode"]}
                or session["fingerprints"] != record["suite_fingerprints"]):
            raise CorpusError("phase condition, solver or suite differs from the frozen group")
        identities.append((session["fingerprints"], session["solver"]))
        summary = session_report(root / phase)
        if phase in {"historical", "candidate_check"} and summary["tasks"][0]["selected"] is None:
            raise CorpusError("historical proof and complete candidate preflights must be verified")
    if any(i != identities[0] for i in identities[1:]):
        raise CorpusError("group phases differ in source identity, solver or budget")
    if load_suite(root / "snapshot/suite.json")["fingerprints"] != identities[0][0]:
        raise CorpusError("group snapshot differs from its phase snapshots")
    events, previous = [], None
    for line in (root / "journal.jsonl").read_bytes().splitlines():
        event = json.loads(line)
        signature = event.pop("seal_sha256", None)
        if signature != digest(canonical(event)) or event["previous"] != previous:
            raise CorpusError("group journal fingerprint mismatch")
        for path, expected in event["files"].items():
            if digest(inside(root, path, "journal evidence").read_bytes()) != expected:
                raise CorpusError("group decision or request evidence changed")
        previous = signature
        events.append(event)
    return root, record, events


def _event(root, events, kind, *, phase=None, slot=None, files=()):
    previous = digest(canonical(events[-1])) if events else None
    event = {"kind": kind, "phase": phase, "slot": slot, "previous": previous,
             "files": {path: digest((root / path).read_bytes()) for path in files}}
    with (root / "journal.jsonl").open("ab") as handle:
        handle.write(canonical(seal(event)) + b"\n")


def _requests(root, events, phase):
    return [unseal(root / next(iter(e["files"]))) for e in events
            if e["kind"] == "issued" and e["phase"] == phase]


def _outcomes(root, events, phase):
    return [unseal(root / next(iter(e["files"]))) for e in events
            if e["kind"] == "completed" and e["phase"] == phase]


def _cap(root):
    return load_suite(root / "snapshot/suite.json")["manifest"]["budget"]["max_attempts_per_task"]


def _verified(root, phase):
    summary = session_report(root / phase)
    return [a for a in summary["tasks"][0]["attempts"] if a["status"] == "verified"]


def _prepared(root):
    return [{"phase": phase, "artifact": a["artifact"],
             "proof": read_object(root / phase / a["artifact"] / "submission.json")["proof"]}
            for phase in ("historical", "preparation") for a in _verified(root, phase)]


def request(root, phase):
    root, record, _ = _load(root)
    if phase not in PHASES:
        raise CorpusError("invalid grouped search phase")
    with session_lock(root):
        _, _, events = _load(root)
        frozen = any(e["kind"] == "frozen" for e in events)
        if (phase == "preparation") == frozen:
            raise CorpusError("preparation must finish and freeze before either comparison arm")
        issued, outcomes = _requests(root, events, phase), _outcomes(root, events, phase)
        if len(issued) > len(outcomes):
            pending = issued[-1]
            if any(e["kind"] == "submitted" and e["phase"] == phase and e["slot"] == pending["slot"] for e in events):
                raise CorpusError("interrupted submitted slot; inspect evidence before continuing")
            return pending
        if len(issued) >= _cap(root):
            raise CorpusError("grouped phase attempt budget exhausted")
        common = _prepared(root)
        inner = task_request(root / phase, "group")
        value = {"schema_version": 1, "phase": phase, "slot": len(issued) + 1,
                 "group_sha256": digest(canonical(record)), "inner_request": inner,
                 "targets": record["targets"], "incumbents": common,
                 "prepared_sha256": digest(canonical(common)),
                 "prior_feedback": outcomes,
                 "contract": "Submit local Lean helper tactics and one term per original target. "
                     "All helpers are charged once in the combined proof. Do not change goals, "
                     "imports, axioms or budgets. Old tools may invent equivalent helpers."}
        value = {**value, "request_sha256": digest(canonical(value))}
        path = f"requests/{phase}-{value['slot']:03d}.json"
        save_new(root / path, seal(value))
        _event(root, events, "issued", phase=phase, slot=value["slot"], files=[path])
        return value


def submit(root, phase, response, *, lean="lean"):
    root, record, _ = _load(root)
    if not isinstance(response, dict) or response.get("action") not in {"candidate", "retain"}:
        raise CorpusError("expected a candidate or retain response")
    fields = ({"action", "request_sha256", "helpers", "proofs", "bridge"}
              if response["action"] == "candidate" else {"action", "request_sha256", "reason"})
    if set(response) != fields:
        raise CorpusError("unsupported grouped response fields")
    if response["action"] == "candidate":
        proof = assemble(record["targets"], response["helpers"], response["proofs"])
        nonempty_string(response["bridge"], "bridge")
    else:
        proof = None
        nonempty_string(response["reason"], "retain reason")
    with session_lock(root):
        _, _, events = _load(root)
        issued, outcomes = _requests(root, events, phase), _outcomes(root, events, phase)
        if len(issued) != len(outcomes) + 1:
            raise CorpusError("issue a fresh grouped request before submitting")
        current = issued[-1]
        if current["request_sha256"] != response["request_sha256"]:
            raise CorpusError("group response belongs to a different request or phase")
        limit = current["inner_request"]["budget"]["max_proof_bytes"]
        if len(canonical(response)) > limit or (proof is not None and len(proof.encode()) > limit):
            raise CorpusError("group response exceeds the shared byte budget")
        prefix = f"decisions/{phase}-{current['slot']:03d}"
        save_new(root / (prefix + ".response.json"), seal(response))
        _event(root, events, "submitted", phase=phase, slot=current["slot"],
               files=[prefix + ".response.json"])
        result = {"phase": phase, "slot": current["slot"], "status": "interrupted",
                  "request_sha256": current["request_sha256"], "generation_usage": None}
        try:
            if proof is None:
                result["status"] = "retained"
            else:
                inner = current["inner_request"]
                checked = submit_attempt(root / phase, {"task_id": "group",
                    "request_sha256": inner["request_sha256"], "proof": proof,
                    "bridge": response["bridge"]}, lean=lean)
                result.update(status=checked["status"], failure=checked.get("failure"),
                              artifact=str(Path(checked["artifact"]).relative_to(root)))
        finally:
            save_new(root / (prefix + ".result.json"), seal(result))
            _, _, updated = _load(root)
            _event(root, updated, "completed", phase=phase, slot=current["slot"],
                   files=[prefix + ".result.json"])
        return result


def freeze(root):
    root, _, _ = _load(root)
    with session_lock(root):
        _, _, events = _load(root)
        if any(e["kind"] == "frozen" for e in events):
            raise CorpusError("preparation is already frozen")
        if len(_outcomes(root, events, "preparation")) != _cap(root):
            raise CorpusError("finish the declared preparation attempt schedule first")
        save_new(root / "prepared.json", seal({"incumbents": _prepared(root)}))
        _event(root, events, "frozen", files=["prepared.json"])
    return report(root)


def report(root):
    root, record, events = _load(root)
    frozen = any(e["kind"] == "frozen" for e in events)
    if frozen and unseal(root / "prepared.json")["incumbents"] != _prepared(root):
        raise CorpusError("prepared proof pool changed after freezing")
    stages = {p: {"issued": len(_requests(root, events, p)),
                  "outcomes": _outcomes(root, events, p)} for p in PHASES}
    complete = frozen and all(len(stages[p]["outcomes"]) == _cap(root) for p in PHASES)
    _, _, suite = load_session(root / "historical")
    manifest = suite["manifest"]
    background = manifest["base"]["modules"] + ["GroupGoal"]
    package = suite["package"]["modules"]
    sources = {m: suite["blobs"][m] for m in background + package}
    routes = []
    for phase in ("historical", *PHASES):
        for attempt in _verified(root, phase):
            labels = (f"GroupMeasured.Route{i:04d}" for i in range(len(sources) + 1))
            module = next(label for label in labels if label not in sources)
            sources[module] = (root / phase / attempt["artifact"] / "Proof.lean").read_bytes()
            routes.append({"id": module, "stage": "prepared" if phase == "preparation" else phase,
                           "modules": ([*package] if phase == "treatment" else []) + [module],
                           "targets": [t["goal"] for t in record["targets"]]})
    if not routes:
        raise CorpusError("a verified historical incumbent is required")
    with tempfile.TemporaryDirectory(prefix="maam-group-measure-") as temp:
        folder = Path(temp)
        descriptors = {}
        for number, (module, source) in enumerate(sources.items()):
            filename = f"source-{number:04d}.lean"
            (folder / filename).write_bytes(source)
            descriptors[module] = {"path": filename, "sha256": digest(source)}
        study = {"schema_version": 1, "phase": "precompression_source_portfolios",
                 "study_id": manifest["suite_id"], "background_modules": background,
                 "candidate": {"id": suite["package"]["package_id"], "modules": package},
                 "targets": [t["goal"] for t in record["targets"]],
                 "sources": descriptors, "routes": routes}
        save_new(folder / "study.json", study)
        comparison = compare_study(folder / "study.json")
    return {"schema_version": 1, "status": "grouped_schedule_complete" if complete else "grouped_search_in_progress",
            "targets": record["targets"], "solver_id": record["solver_id"], "mode": record["mode"],
            "fingerprints": {"group_sha256": digest(canonical(record)), "tools": record["tools"],
                             "suite": record["suite_fingerprints"]},
            "preparation_frozen": frozen, "attempt_cap_per_stage": _cap(root), "stages": stages,
            "verified_complete_routes": len(routes), "measurement": comparison,
            "formal_scope": "controller-assembled conjunction of all fixed original goal constants",
            "generation_usage": None, "generation_budget_verified": False,
            "information_separation_established": False, "training_eligible": False,
            "scope": "Condition-specific requests and equal attempt/verification caps. "
                "External model isolation, metered generation and mathematical discovery are not certified."}
