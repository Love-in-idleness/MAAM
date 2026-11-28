"""One bounded guidance-only DeepSeek trial; historical evaluators stay unchanged."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from zoneinfo import ZoneInfo

from . import deepseek, migration as mig
from .corpus import CorpusError
from .generation import observation
from .lean_sandbox import lean_sandbox, probe
from .live_calibration import read_private_key
from .theory import CHECKER, digest, read_object
from .transfer import commit_for
from scripts.measure_compressed_reference import measure_sources

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "experiments/method_use_v1/protocol.json"
TOOLS = ("maam/method_use.py", "scripts/control_method_use.py", "maam/lean_sandbox.py",
         "maam/migration.py", "maam/theory.py", "maam/PackageCheck.lean", "maam/generation.py",
         "maam/deepseek.py", "maam/live_calibration.py", "maam/transfer.py", "maam/corpus.py",
         "scripts/measure_compressed_reference.py", "scripts/check_theory_package.py")
INSTRUCTIONS = (
    "Solve the single Lean 4.24.0 goal using the supplied sources. Return only a JSON object "
    "with exactly one string field, proof, containing the complete Proof.lean source. "
    "Import precisely the listed modules and define Submission.solve with precisely the supplied "
    "goal type. Do not change the goal, imports, axioms, or frozen sources. No sorry, admit, "
    "new axioms, external tools, file access or networking. Any compliant proof is accepted. "
    "A repair request includes only your own previous candidate and its checker diagnostic."
)
FORMAT = {"type": "json_schema", "name": "complete_lean_proof", "strict": True, "schema": {
    "type": "object", "properties": {"proof": {"type": "string"}},
    "required": ["proof"], "additionalProperties": False}}


def _hashes():
    return {name: digest((REPO / name).read_bytes()) for name in TOOLS}


def _cost(config, inputs, outputs):
    return ((Decimal(inputs) * Decimal(config["input_usd_per_million"]) +
             Decimal(outputs) * Decimal(config["output_usd_per_million"])) *
            Decimal(config["cost_margin"]) / 1_000_000)


def _protocol(path):
    protocol = read_object(Path(path))
    expected = {"schema_version", "experiment_id", "suite", "references", "guide", "math_condition",
                "conditions", "repetitions", "task_ids", "role_task_ids", "config"}
    if (set(protocol) != expected or protocol["schema_version"] != 1
            or protocol["experiment_id"] != "method-use-v1" or protocol["math_condition"] != "treatment"
            or protocol["conditions"] != ["A", "B"] or protocol["repetitions"] != 2
            or protocol["task_ids"] != [f"u0{i}" for i in range(1, 7)]
            or protocol["role_task_ids"] != {"positive": [f"u0{i}" for i in range(1, 5)],
                                           "boundary": ["u05", "u06"]}):
        raise CorpusError("protocol differs from the reviewed six-task guidance trial")
    config = protocol["config"]
    required = {"provider": "deepseek", "model": "deepseek-flash", "reasoning_effort": "low",
                "input_reservation": 16384, "max_output_tokens": 32768,
                "call_deadline_seconds": 180, "max_calls": 48, "max_cost_usd": "5",
                "input_usd_per_million": "0.30", "output_usd_per_million": "1.20",
                "cost_margin": "1.25"}
    if (not isinstance(config, dict) or set(config) != set(required) | {"pricing_checked_on"}
            or any(config[k] != v or type(config[k]) is not type(v) for k, v in required.items())):
        raise CorpusError("model or budget differs from the reviewed protocol")
    if _cost(config, 48 * 16384, 48 * 32768) > Decimal(config["max_cost_usd"]):
        raise CorpusError("whole-round reservation exceeds spending ceiling")
    for field in ("suite", "references", "guide"):
        if protocol[field] != {"suite": "suite.json", "references": "reference_proofs.json",
                              "guide": "guide.txt"}[field]:
            raise CorpusError("pilot input paths changed")
    return protocol


def _schedule(protocol):
    return [{"task_id": task, "arm": arm, "repetition": rep}
            for task in protocol["task_ids"] for rep in (1, 2)
            for arm in (("A", "B") if rep == 1 else ("B", "A"))]


def payload_for(request, arm, guide, config, history=None):
    """Construct the provider whitelist instead of serializing internal requests."""
    content = {"lean_version": request["lean_version"],
               "sources": [{"module": row["module"], "content": row["content"]}
                           for row in request["sources"]],
               "target": {"declaration": "Submission.solve", "type": request["task"]["goal"]},
               "output_contract": {"proof": "complete Proof.lean source", "imports": [
                   row["module"] for row in request["sources"]]}}
    if arm == "B":
        content["guide"] = guide
    elif arm != "A":
        raise CorpusError("unknown guidance arm")
    if history is not None:
        content["repair"] = history
    return {"model": config["model"], "store": False, "instructions": INSTRUCTIONS,
            "input": mig.canonical(content).decode(), "reasoning": {"effort": config["reasoning_effort"]},
            "max_output_tokens": config["max_output_tokens"], "text": {"format": FORMAT}}


def _load(root):
    root = Path(root).resolve()
    plan = mig.unseal(root / "plan.json")
    if plan["tool_sha256"] != _hashes():
        raise CorpusError("pilot tools changed; do not resume frozen calls")
    for name, sha in plan["input_sha256"].items():
        if digest((root / "inputs" / name).read_bytes()) != sha:
            raise CorpusError("pilot input snapshot changed")
    if _protocol(root / "inputs/protocol.json") != plan["protocol"]:
        raise CorpusError("protocol snapshot differs from plan")
    if (plan["schedule"] != _schedule(plan["protocol"])
            or plan["execution_mode"] not in {"provider", "offline_fixture"}):
        raise CorpusError("pilot schedule or evidence mode changed")
    _, _, frozen = mig.load_session(root / "math")
    if frozen["fingerprints"] != plan["math_fingerprints"]:
        raise CorpusError("mathematical snapshot differs from the frozen plan")
    guide = (root / "inputs/guide.txt").read_text()
    return root, plan, frozen, guide


def prepare(protocol_path, output, *, verify_commit=True):
    path = Path(protocol_path).resolve()
    if verify_commit and Path(output).resolve() != (REPO / "data/method-use-v1").resolve():
        raise CorpusError("this approved live round has one ledger: data/method-use-v1; do not reset its allowance")
    protocol = _protocol(path)
    files = [p for p in path.parent.rglob("*") if p.is_file() and p.suffix not in {".olean", ".ilean"}]
    commit = commit_for(files + [REPO / name for name in TOOLS]) if verify_commit else None
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / "inputs"
    inputs.mkdir()
    for name in ("protocol.json", protocol["guide"], protocol["references"]):
        shutil.copyfile(path.parent / name, inputs / name)
    guide = (inputs / protocol["guide"]).read_text()
    if not guide.strip() or len(guide.split()) > 400 or "/home/" in guide:
        raise CorpusError("guide must be generic English under 400 words without private paths")
    mig.start_session(path.parent / protocol["suite"], root / "math", condition="treatment",
                      solver_id="common-mathematical-context", mode="interactive_agent")
    _, _, frozen = mig.load_session(root / "math")
    plan = {"schema_version": 1, "protocol": protocol, "schedule": _schedule(protocol),
            "execution_mode": "provider" if verify_commit else "offline_fixture",
            "math_fingerprints": frozen["fingerprints"],
            "source_commit": commit, "tool_sha256": _hashes(),
            "input_sha256": {p.name: digest(p.read_bytes()) for p in inputs.iterdir()},
            "whole_round_reserved_cost_usd": str(_cost(protocol["config"], 48 * 16384, 48 * 32768)),
            "provider_revision_documented": "DeepSeek-V4.1-Flash-1017",
            "pricing_source": "https://api-docs.deepseek.com/quick_start/pricing/"}
    mig.save_new(root / "plan.json", mig.seal(plan))
    (root / "events").mkdir()
    (root / "issued.jsonl").write_bytes(mig.canonical(mig.seal({"plan_sha256": digest(mig.canonical(plan))})) + b"\n")
    return {"status": "needs_preflight", "sessions": 24, "max_calls": 48,
            "whole_round_reserved_cost_usd": plan["whole_round_reserved_cost_usd"]}


def preflight(output):
    started = time.monotonic()
    root, plan, frozen, guide = _load(output)
    evidence = {"sandbox": probe(), "references": {}}
    refs = read_object(root / "inputs/reference_proofs.json")["tasks"]
    folder = root / "preflight"
    folder.mkdir(exist_ok=False)
    with lean_sandbox() as lean:
        for task in plan["protocol"]["task_ids"]:
            request = mig.task_request(root / "math", task)
            source = mig.proof_source(request, refs[task]["proof"])
            artifact = folder / task
            artifact.mkdir()
            (artifact / "Proof.lean").write_text(source)
            result = mig.verify_attempt(frozen, request, source, artifact, lean=str(lean))
            mig.save_new(artifact / "verification.json", result)
            evidence["references"][task] = {"source_sha256": digest(source.encode()),
                "result_sha256": digest(mig.canonical(result)), "status": result["status"]}
            a, b = (payload_for(request, arm, guide, plan["protocol"]["config"]) for arm in ("A", "B"))
            ca, cb = json.loads(a["input"]), json.loads(b["input"])
            if cb.pop("guide") != guide or ca != cb:
                raise CorpusError("paired mathematical payloads differ")
            for payload in (a, b):
                deepseek.input_allowance(payload, 16384)
    evidence["status"] = "verified" if all(r["status"] == "verified" for r in evidence["references"].values()) else "failed"
    evidence["elapsed_seconds"] = time.monotonic() - started
    mig.save_new(root / "preflight.json", mig.seal(evidence))
    return evidence


def _decision(raw, config):
    observed = observation(raw)
    usage = observed["usage"]
    if usage is None:
        return {"kind": "unknown_usage", "halt": True}
    if observed["reported_model"] != config["model"]:
        return {"kind": "model_mismatch", "halt": True}
    if usage["input_tokens"] > config["input_reservation"] or usage["output_tokens"] > config["max_output_tokens"]:
        return {"kind": "usage_limit_exceeded", "halt": True}
    body = json.loads(raw)
    if body.get("status") != "completed":
        return {"kind": "provider_incomplete", "terminal": True}
    try:
        candidate = json.loads(observed["output"])
        if (not isinstance(candidate, dict) or set(candidate) != {"proof"}
                or not isinstance(candidate["proof"], str) or not candidate["proof"].strip()):
            raise ValueError
        if len(candidate["proof"].encode()) > 32768:
            return {"kind": "proof_byte_limit", "terminal": False}
        return {"kind": "candidate", "source": candidate["proof"]}
    except (ValueError, TypeError):
        return {"kind": "invalid_model_output", "terminal": False}


def _child_call(folder, transport, key, payload, seconds):
    try:
        status, request_id, raw = transport(key, payload, seconds)
        if key and request_id and (key in request_id or key[:20] in request_id):
            raise OSError("credential_echo_blocked")
        (folder / "response.bin").write_bytes(raw)
        mig.save_new(folder / "result.json", {"ok": True, "status": status, "request_id": request_id})
    except Exception as exc:
        message = str(exc)
        safe = message if re.fullmatch(r"provider_http_[0-9]{3}|credential_echo_blocked|credential_in_payload_blocked|provider_response_too_large", message) else "provider_request_failed"
        mig.save_new(folder / "result.json", {"ok": False, "error": safe})


def bounded_response(key, payload, seconds, *, transport=deepseek.response):
    """Kill timed-out transport processes; never leave a spending thread behind."""
    deadline = time.monotonic() + seconds
    context = multiprocessing.get_context("fork")
    with tempfile.TemporaryDirectory(prefix="maam-provider-call-") as temporary:
        folder = Path(temporary)
        process = context.Process(target=_child_call, args=(folder, transport, key, payload, seconds))
        process.start()
        try:
            process.join(timeout=max(0, deadline - time.monotonic()))
            if process.is_alive() or time.monotonic() > deadline:
                raise OSError("provider_deadline_exceeded")
            if process.exitcode != 0 or not (folder / "result.json").exists():
                raise OSError("provider_request_failed")
            result = read_object(folder / "result.json")
            if not result["ok"]:
                raise OSError(result["error"])
            return result["status"], result["request_id"], (folder / "response.bin").read_bytes()
        finally:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()


def _preflight_record(root, plan):
    evidence = mig.unseal(root / "preflight.json")
    if evidence["status"] != "verified" or set(evidence["references"]) != set(plan["protocol"]["task_ids"]):
        raise CorpusError("all six sandboxed references must pass before generation")
    refs = read_object(root / "inputs/reference_proofs.json")["tasks"]
    for task, row in evidence["references"].items():
        source = mig.proof_source(mig.task_request(root / "math", task), refs[task]["proof"])
        result = read_object(root / "preflight" / task / "verification.json")
        _check_logs(root / "preflight" / task, result)
        if (row["source_sha256"] != digest(source.encode()) or row["status"] != "verified"
                or digest(mig.canonical(result)) != row["result_sha256"] or result["status"] != "verified"
                or (root / "preflight" / task / "Proof.lean").read_text() != source):
            raise CorpusError("reference evidence changed")
    return evidence


def _check_logs(folder, result):
    for command in result["trace"]:
        for row in command["logs"].values():
            name = row["path"]
            if Path(name).name != name or digest((folder / name).read_bytes()) != row["sha256"]:
                raise CorpusError("verification command evidence changed")


def _repair(row, verification=None):
    # No provider reasoning, unrelated sessions, or private host paths enter repair.
    diagnostic = row["kind"]
    if verification is not None:
        diagnostic = verification.get("failure", {}).get("message", diagnostic)
        diagnostic = diagnostic.replace(str(CHECKER), "PackageCheck.lean")
        diagnostic = re.sub(r"/tmp/maam-attempt-[^/\s:]+", "/work", diagnostic)
        if "/home/" in diagnostic:
            diagnostic = verification.get("failure", {}).get("kind", "verification_failed")
    return {"previous_candidate": row.get("candidate_output", ""), "checker_error": diagnostic}


def report(output):
    root, plan, frozen, guide = _load(output)
    preflight_evidence = _preflight_record(root, plan)
    config = plan["protocol"]["config"]
    journal = [json.loads(line) for line in (root / "issued.jsonl").read_bytes().splitlines()]
    for row in journal:
        if row.pop("seal_sha256", None) != digest(mig.canonical(row)):
            raise CorpusError("event journal changed")
    if not journal or journal[0] != {"plan_sha256": digest(mig.canonical(plan))} or len(journal) > 49:
        raise CorpusError("event journal differs from plan")
    if {p.name for p in (root / "events").iterdir()} != {f"{i:03d}" for i in range(1, len(journal))}:
        raise CorpusError("incomplete event setup; do not resend")
    sessions = [{**row, "status": "pending", "attempts": []} for row in plan["schedule"]]
    cursor, attempt, history, halt = 0, 1, None, None
    calls, totals = [], {k: 0 for k in ("input_tokens", "output_tokens", "total_tokens")}
    usage_known = True
    verified_sources = {arm: {} for arm in ("A", "B")}
    for number, issued in enumerate(journal[1:], 1):
        if halt or cursor >= 24:
            raise CorpusError("events continued after a stopping condition")
        session = sessions[cursor]
        request = mig.task_request(root / "math", session["task_id"])
        payload = payload_for(request, session["arm"], guide, config, history)
        try:
            deepseek.input_allowance(payload, config["input_reservation"])
            sent = True
        except OSError:
            sent = False
        expected = {"event": number, "session": cursor, "attempt": attempt, "sent": sent,
                    "math_request_sha256": request["request_sha256"],
                    "payload_sha256": digest(mig.canonical(payload)),
                    "input_reservation": 16384 if sent else 0, "output_reservation": 32768 if sent else 0}
        folder = root / "events" / f"{number:03d}"
        if issued != expected or read_object(folder / "payload.json") != payload:
            raise CorpusError("event differs from frozen request and context")
        row = {"event": number, "attempt": attempt, "sent": sent, "kind": "interrupted", "usage": None}
        verification = None
        outcome = None
        if not sent:
            outcome = {"kind": "input_budget", "terminal": True}
        elif (folder / "receipt.json").exists():
            receipt = mig.unseal(folder / "receipt.json")
            if (receipt["reservation_sha256"] != digest(mig.canonical(issued))
                    or receipt["transport_kind"] != plan["execution_mode"]):
                raise CorpusError("receipt differs from reservation")
            row.update(requested_model=config["model"], elapsed_seconds=receipt["elapsed_seconds"],
                       provider_request_id=receipt.get("provider_request_id"))
            if receipt["error"]:
                if receipt["error"] not in {"provider_request_failed", "provider_deadline_exceeded"}:
                    raise CorpusError("invalid transport error")
                row["provider_error_code"] = receipt.get("provider_error_code")
                outcome = {"kind": receipt["error"], "halt": True}
            else:
                raw = (folder / "response.bin").read_bytes()
                observed = observation(raw)
                if (receipt["http_status"] != 200 or receipt["raw_sha256"] != digest(raw)
                        or receipt["observation"] != observed):
                    raise CorpusError("raw provider response or metering changed")
                row["usage"] = observed["usage"]
                row["reported_model"] = observed["reported_model"]
                row["provider_response_id"] = observed["response_id"]
                row["candidate_output"] = observed["output"]
                outcome = _decision(raw, config)
                if outcome["kind"] == "candidate":
                    source = outcome.pop("source")
                    if (folder / "Proof.lean").read_text() != source:
                        raise CorpusError("Lean candidate is not the preserved provider output")
                    if (folder / "verification.json").exists():
                        verification = read_object(folder / "verification.json")
                        _check_logs(folder, verification)
                        row["verification_seconds"] = sum(c["seconds"] for c in verification["trace"])
                        row["verification_failure"] = verification.get("failure")
                        if verification["status"] == "verified":
                            dependencies = verification["audit"]["targets"][0]["direct_proof_dependencies"]
                            row["method_application_evidence"] = {
                                "named_lemma_direct_dependency": "MethodUse.left_factor" in dependencies,
                                "direct_proof_dependencies": dependencies,
                                "absence_means": "No direct named dependency; inline or indirect use is unclassified."}
                        outcome = {"kind": verification["status"],
                                   "verification_sha256": digest(mig.canonical(verification))}
                    else:
                        outcome = None
            if row["usage"] is None:
                usage_known = False
            else:
                for key in totals:
                    totals[key] += row["usage"][key]
        elif sent:
            usage_known = False
        if outcome is None or not (folder / "outcome.json").exists():
            halt = "incomplete_event_do_not_resend"
            session["status"] = "interrupted"
        else:
            if mig.unseal(folder / "outcome.json") != outcome:
                raise CorpusError("event outcome differs from raw evidence")
            row["kind"] = outcome["kind"]
            if outcome.get("halt"):
                halt = outcome["kind"]
                session["status"] = "stopped"
            elif outcome["kind"] == "verified":
                session["status"] = "verified"
                verified_sources[session["arm"]].setdefault(session["task_id"], []).append(
                    (folder / "Proof.lean", verification))
            elif outcome.get("terminal") or attempt == 2:
                session["status"] = "failed"
            else:
                session["status"] = "repair_available"
                history = _repair(row, verification)
                attempt = 2
            if session["status"] in {"verified", "failed"}:
                cursor, attempt, history = cursor + 1, 1, None
        session["attempts"].append(row)
        calls.append(row)
    initiated = sum(row["sent"] for row in calls)
    if initiated > 48 or _cost(config, initiated * 16384, initiated * 32768) > Decimal(config["max_cost_usd"]):
        raise CorpusError("issued reservations exceed allowance")
    groups = {role: {arm: {"sessions": sum(s["task_id"] in tasks and s["arm"] == arm for s in sessions),
                  "first_attempt_verified": sum(s["task_id"] in tasks and s["arm"] == arm and
                      bool(s["attempts"]) and s["attempts"][0]["kind"] == "verified" for s in sessions),
                  "within_budget_verified": sum(s["task_id"] in tasks and s["arm"] == arm and
                      s["status"] == "verified" for s in sessions)} for arm in ("A", "B")}
              for role, tasks in plan["protocol"]["role_task_ids"].items()}
    return {"schema_version": 1, "status": "stopped" if halt else "completed" if cursor == 24 else "in_progress",
            "execution_mode": plan["execution_mode"],
            "halt_reason": halt, "source_commit": plan["source_commit"], "provider": "deepseek",
            "transport": deepseek.TRANSPORT, "model": config["model"], "exact_model_revision_verified": False,
            "actual_provider_calls": initiated if plan["execution_mode"] == "provider" else 0,
            "simulated_calls": initiated if plan["execution_mode"] == "offline_fixture" else 0,
            "initiated_slots": initiated, "call_count_scope": "Initiated slots; uncertain transport may not have reached the provider.",
            "sessions": sessions, "groups": groups,
            "generation_usage": totals if usage_known else None,
            "known_generation_usage": totals, "estimated_cost_usd": str(_cost(config, totals["input_tokens"], totals["output_tokens"])) if usage_known else None,
            "reserved_cost_usd": str(_cost(config, initiated * 16384, initiated * 32768)),
            "whole_round_reserved_cost_usd": plan["whole_round_reserved_cost_usd"],
            "next": None if halt or cursor == 24 else {"session": cursor, "attempt": attempt, "history": history},
            "preparation": {"offline_preflight_seconds": preflight_evidence["elapsed_seconds"],
                "author_preparation_seconds": None, "historical_preparation_cost": "unknown",
                "shared_research_infrastructure_source": measure_sources({name: (REPO / name).read_bytes() for name in TOOLS}),
                "scope": "Shared controller source counted once separately; installed Lean/Python are external shared prerequisites."},
            "compression": _compression(root, frozen, guide, verified_sources),
            "scope": {"author_designed_development_tasks": True, "guidance_only": True,
                      "new_theory_effect_established": False, "held_out_transfer_established": False,
                      "training_eligible": False}}


def _compression(root, frozen, guide, candidates):
    result = {}
    shared = dict(frozen["blobs"])
    for arm in ("A", "B"):
        selected = {}
        for task in [f"u0{i}" for i in range(1, 7)]:
            source = root / "preflight" / task / "Proof.lean"
            verification = read_object(source.parent / "verification.json")
            best_tokens = sum(s["source_tokens"] for s in verification["audit"]["sources"] if s["module"] == "Proof")
            for path, checked in candidates[arm].get(task, []):
                tokens = sum(s["source_tokens"] for s in checked["audit"]["sources"] if s["module"] == "Proof")
                if tokens < best_tokens:
                    source, best_tokens = path, tokens
            selected[f"proofs/{task}.lean"] = source.read_bytes()
        if arm == "B":
            selected["guide.txt"] = guide.encode()
        result[arm] = {"nonshared_payload": measure_sources(selected),
                       "joint_local_sources": measure_sources({**shared, **selected})}
    result["guide_utf8_bytes"] = len(guide.encode())
    result["scope"] = "Same six verified fallback goals; shared mathematics stored once; logs and common research infrastructure excluded."
    return result


def execute_next(output, key_file, *, transport=None):
    root = Path(output).resolve()
    with mig.session_lock(root):
        state = report(root)
        if state["status"] != "in_progress":
            raise CorpusError("no call available; incomplete events cannot be retried")
        _, plan, frozen, guide = _load(root)
        config = plan["protocol"]["config"]
        if (transport is None) != (plan["execution_mode"] == "provider"):
            raise CorpusError("fixture and paid-provider execution cannot be mixed")
        if transport is None and (plan["source_commit"] is None or config["pricing_checked_on"] !=
                datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()):
            raise CorpusError("live generation requires committed inputs and same-day checked prices")
        position = state["next"]
        session = plan["schedule"][position["session"]]
        request = mig.task_request(root / "math", session["task_id"])
        payload = payload_for(request, session["arm"], guide, config, position["history"])
        try:
            deepseek.input_allowance(payload, config["input_reservation"])
            sent = True
        except OSError:
            sent = False
        # Read only the user-selected credential after offline checks; never archive its path.
        key = read_private_key(key_file) if sent and transport is None else ""
        number = sum(len(s["attempts"]) for s in state["sessions"]) + 1
        folder = root / "events" / f"{number:03d}"
        folder.mkdir()
        mig.save_new(folder / "payload.json", payload)
        issued = {"event": number, "session": position["session"], "attempt": position["attempt"], "sent": sent,
                  "math_request_sha256": request["request_sha256"], "payload_sha256": digest(mig.canonical(payload)),
                  "input_reservation": 16384 if sent else 0, "output_reservation": 32768 if sent else 0}
        with (root / "issued.jsonl").open("ab") as journal:
            journal.write(mig.canonical(mig.seal(issued)) + b"\n")
            journal.flush()
            os.fsync(journal.fileno())
        if not sent:
            outcome = {"kind": "input_budget", "terminal": True}
        else:
            started = time.monotonic()
            receipt = {"reservation_sha256": digest(mig.canonical(issued)), "error": None,
                       "transport_kind": plan["execution_mode"],
                       "raw_sha256": None, "observation": None}
            try:
                status, request_id, raw = bounded_response(key, payload, config["call_deadline_seconds"],
                    transport=deepseek.response if transport is None else transport)
                if status != 200:
                    raise OSError("provider_request_failed")
                (folder / "response.bin").write_bytes(raw)
                receipt.update(http_status=status, provider_request_id=request_id,
                               raw_sha256=digest(raw), observation=observation(raw))
                outcome = _decision(raw, config)
            except OSError as exc:
                receipt["error"] = "provider_deadline_exceeded" if str(exc) == "provider_deadline_exceeded" else "provider_request_failed"
                message = str(exc)
                receipt["provider_error_code"] = message if re.fullmatch(r"provider_http_[0-9]{3}|credential_echo_blocked|credential_in_payload_blocked|provider_response_too_large", message) else None
                outcome = {"kind": receipt["error"], "halt": True}
            finally:
                key = None
            receipt["elapsed_seconds"] = time.monotonic() - started
            mig.save_new(folder / "receipt.json", mig.seal(receipt))
            if outcome["kind"] == "candidate":
                source = outcome.pop("source")
                (folder / "Proof.lean").write_text(source)
                with lean_sandbox() as lean:
                    verification = mig.verify_attempt(frozen, request, source, folder, lean=str(lean))
                mig.save_new(folder / "verification.json", verification)
                outcome = {"kind": verification["status"], "verification_sha256": digest(mig.canonical(verification))}
        mig.save_new(folder / "outcome.json", mig.seal(outcome))
        return report(root)
