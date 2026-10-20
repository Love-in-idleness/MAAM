"""Inventory existing baseline certificates; this does not perform optimisation."""
from pathlib import Path

from .corpus import CorpusError
from .migration import canonical, load_session, session_report, task_request, unseal
from .theory import digest, read_object

REPO = Path(__file__).resolve().parents[1]
METRIC = "full_proof_module_source_tokens"


def inventory_baseline(sessions, task_ids):
    """Replay baseline evidence and keep the first strictly shortest certificate.

    All recorded failures remain visible. Candidate metadata is bound by session
    provenance, but deliberately excluded from the original knowledge identity.
    No API receipts or keys are opened, and no new proof is checked or generated.
    """
    if not isinstance(sessions, (list, tuple)) or not sessions:
        raise CorpusError("provide at least one baseline session")
    if (not isinstance(task_ids, (list, tuple)) or not 1 <= len(task_ids) <= 4
            or any(not isinstance(t, str) or not t for t in task_ids)
            or len(set(task_ids)) != len(task_ids)):
        raise CorpusError("provide one to four distinct development task ids")
    roots = [Path(path).resolve() for path in sessions]
    if len(set(roots)) != len(roots):
        raise CorpusError("baseline session roots must be distinct")
    rows = {t: {"task_id": t, "sessions": [], "selected": None} for t in task_ids}
    knowledge, provenance = None, []
    for index, path in enumerate(roots):
        root, session, frozen = load_session(path)
        if session["condition"] != "baseline":
            raise CorpusError("only baseline sessions may prepare original knowledge")
        report = session_report(root)
        manifest = frozen["manifest"]
        tasks = {task["id"]: task for task in manifest["tasks"]}
        if any(t not in tasks or tasks[t]["split"] != "development" for t in task_ids):
            raise CorpusError("all requested tasks must be existing development goals")
        modules = list(dict.fromkeys(manifest["base"]["modules"]
                                    + [tasks[t]["module"] for t in task_ids]))
        identity = {"lean_version": manifest["lean_version"], "base": manifest["base"],
                    "tasks": [tasks[t] for t in task_ids],
                    "source_sha256": {m: digest(frozen["blobs"][m]) for m in modules}}
        if knowledge is None:
            knowledge = identity
        elif knowledge != identity:
            raise CorpusError("baseline knowledge, goals or toolchain differ")
        provenance.append({"session_index": index, "root": str(root),
            "session_sha256": digest((root / "session.json").read_bytes()),
            "solver": session["solver"], "budget": manifest["budget"],
            "available_sources": [{"module": m, "sha256": identity["source_sha256"][m],
                "path": str(root / "snapshot" / manifest["sources"][m]["path"])} for m in modules],
            "generation_usage": None, "generation_usage_status": "not_inspected_unknown"})
        # session_report replays completed artifacts/logs; also bind any surviving
        # interrupted artifacts, without treating missing files as completed work.
        for task in report["tasks"]:
            request = task_request(root, task["id"])
            for attempt in task["attempts"]:
                artifact = root / attempt["artifact"]
                pending = unseal(root / "reservations" /
                                 f"{task['id']}-{attempt['attempt']:03d}.json")
                if ((artifact / "pending.json").exists()
                        and unseal(artifact / "pending.json") != pending):
                    raise CorpusError("interrupted attempt reservation changed")
                if ((artifact / "Proof.lean").exists()
                        and digest((artifact / "Proof.lean").read_bytes()) != pending["proof_sha256"]):
                    raise CorpusError("attempt proof fingerprint changed")
                if ((artifact / "submission.json").exists()
                        and digest(canonical(read_object(artifact / "submission.json")))
                        != pending["submission_sha256"]):
                    raise CorpusError("attempt submission fingerprint changed")
            if task["id"] not in rows:
                continue
            row = rows[task["id"]]
            row["sessions"].append({"session_index": index, "status": task["status"],
                                    "attempts": task["attempts"]})
            selected = task["selected"]
            if selected is None:
                continue
            tokens, target = selected["proof_source_tokens"], selected["target"]
            if (type(tokens) is not int or tokens < 0 or selected["package_source_tokens"] != 0
                    or target.get("name") != "Submission.solve"
                    or target.get("expected") != tasks[task["id"]]["goal"]
                    or target.get("goal_preserved") is not True):
                raise CorpusError("baseline witness must preserve its original audited goal")
            artifact = root / "attempts" / task["id"] / f"{selected['attempt']:03d}"
            witness = {"session_index": index, "attempt": selected["attempt"],
                "artifact": str(artifact), "proof_source_tokens": tokens,
                "proof_sha256": digest((artifact / "Proof.lean").read_bytes()),
                "result_sha256": digest((artifact / "result.json").read_bytes()),
                "request_sha256": request["request_sha256"], "target": target,
                "original_import_context": [{"module": s["module"], "sha256": s["sha256"]}
                                            for s in request["sources"]]}
            if row["selected"] is None or tokens < row["selected"]["proof_source_tokens"]:
                row["selected"] = witness
    missing = [t for t in task_ids if rows[t]["selected"] is None]
    tools = {p: digest((REPO / p).read_bytes()) for p in (
        "maam/baseline.py", "maam/migration.py", "maam/theory.py",
        "maam/PackageCheck.lean", "scripts/lean_sandbox.py")}
    metric = {"name": METRIC, "measured_field": "audit.sources[Proof].source_tokens",
              "checker_sha256": tools["maam/PackageCheck.lean"]}
    certificates = [rows[t]["selected"] for t in task_ids]
    return {"schema_version": 1,
        "status": "known_baseline_pool_frozen" if not missing else "baseline_witnesses_missing",
        "knowledge": knowledge, "knowledge_sha256": digest(canonical(knowledge)),
        "source_metric": metric, "source_metric_sha256": digest(canonical(metric)),
        "tool_sha256": tools, "sessions": provenance, "tasks": list(rows.values()),
        "selected_certificates_sha256": digest(canonical(certificates)), "missing_tasks": missing,
        "selection": "strictly shortest recorded verified source; ties keep first session",
        "generation_usage": None, "generation_usage_status": "not_inspected_unknown",
        "baseline_search_complete": False, "package_attribution_ready": False,
        "globally_shortest": False, "new_lean_verification_performed": False,
        "scope": "Offline inventory of previously audited witnesses, not proof of existing-tool "
                 "saturation or a new proof-search experiment; failures and interruptions remain "
                 "in their original sessions. Generation costs are not replayed by this inventory; "
                 "consult original generation ledgers. No package gain can yet be attributed "
                 "to introducing new concepts."}
