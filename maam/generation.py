"""Metered provider calls around the unchanged, fingerprinted migration checker.

Controller hashes are integrity checks, not signed provider attestations. Lean
executes generated code; use a separate OS sandbox for untrusted experiments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .corpus import CorpusError
from .migration import (canonical, load_session, load_suite, save_new, seal,
                        session_lock, session_report, start_session, submit_attempt,
                        task_request, unseal)
from .theory import digest, nonempty_string, read_object

ENDPOINT = "https://api.openai.com/v1/responses"
INSTRUCTIONS = (
    "Solve the single frozen Lean task in the request using only its supplied sources. "
    "Return JSON with exactly two nonempty strings: proof and bridge. "
    "proof is the Lean term after :=, usually by followed by tactics, without imports, "
    "namespace or theorem declarations. bridge explains how this term proves the "
    "original goal. Do not change goals, sources, imports, axioms or budgets. "
    "Do not use sorry, admit or new axioms. You have no external tools. "
    "Any previous attempts and diagnostics belong only to this task and condition."
)
FORMAT = {"type": "json_schema", "name": "lean_proof", "strict": True,
          "schema": {"type": "object", "properties": {
              "proof": {"type": "string"}, "bridge": {"type": "string"}},
              "required": ["proof", "bridge"], "additionalProperties": False}}
SCOPE = {"held_out_evaluation": False, "fair_model_performance_claim": False,
         "training_eligible": False, "exact_model_revision_verified": False}


@contextmanager
def lean_environment():
    """Synchronous controller: generated Lean must not inherit provider secrets."""
    original = os.environ.copy()
    allowed = {k: v for k, v in original.items() if k in {
        "PATH", "HOME", "ELAN_HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL"}}
    os.environ.clear()
    os.environ.update(allowed)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_config(config):
    if not isinstance(config, dict) or set(config) != {"model", "sampling", "budget"}:
        raise CorpusError("generation config needs exactly model, sampling and budget")
    nonempty_string(config["model"], "model")
    sampling, budget = config["sampling"], config["budget"]
    if not isinstance(sampling, dict) or set(sampling) - {"temperature", "top_p", "reasoning_effort"}:
        raise CorpusError("unsupported sampling parameter")
    for key, maximum in (("temperature", 2), ("top_p", 1)):
        if key in sampling and (type(sampling[key]) not in (int, float)
                or not 0 <= sampling[key] <= maximum or not math.isfinite(sampling[key])):
            raise CorpusError("invalid sampling parameter: " + key)
    if "reasoning_effort" in sampling:
        nonempty_string(sampling["reasoning_effort"], "reasoning_effort")
        if sampling["reasoning_effort"] != "none" and set(sampling) & {"temperature", "top_p"}:
            raise CorpusError("omit temperature/top_p when reasoning is enabled")
    fields = {"max_calls_per_task", "max_output_tokens_per_call",
              "max_output_tokens_per_task", "request_timeout_seconds"}
    if not isinstance(budget, dict) or set(budget) != fields:
        raise CorpusError("generation budget fields differ from the protocol")
    if any(type(budget[k]) is not int or budget[k] <= 0 for k in fields):
        raise CorpusError("generation budgets must be positive integers")
    if min(budget["max_output_tokens_per_call"], budget["max_output_tokens_per_task"]) < 16:
        raise CorpusError("Responses output allowances must be at least 16 tokens")


def prepare(suite, root, config, task_ids):
    validate_config(config)
    frozen = load_suite(suite)
    tasks = {t["id"]: t for t in frozen["manifest"]["tasks"]}
    if (not isinstance(task_ids, list) or not task_ids
            or any(not isinstance(t, str) or t not in tasks for t in task_ids)
            or len(set(task_ids)) != len(task_ids)):
        raise CorpusError("choose a nonempty ordered list of distinct task ids")
    if any(tasks[t]["split"] != "development" for t in task_ids):
        raise CorpusError("this driver round supports development calibration only")
    if config["budget"]["max_calls_per_task"] > frozen["manifest"]["budget"]["max_attempts_per_task"]:
        raise CorpusError("generation calls cannot exceed the frozen proof-attempt limit")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    for condition in ("baseline", "treatment"):
        # Legacy evaluator enum; direct-provider provenance is recorded below.
        start_session(suite, root / condition, condition=condition,
                      solver_id="openai-responses:" + config["model"])
    for folder in ("reservations", "calls"):
        (root / folder).mkdir()
    schedule = [{"task_id": task, "condition": condition} for i, task in enumerate(task_ids)
                for condition in (("baseline", "treatment") if i % 2 == 0 else ("treatment", "baseline"))]
    record = {"schema_version": 1, "phase": "metered_generation_calibration",
              "provider": "openai_responses", "endpoint": ENDPOINT,
              "prepared_at": now(), "config": config, "schedule": schedule,
              "driver_sha256": digest(Path(__file__).read_bytes()),
              "fingerprints": frozen["fingerprints"],
              "instructions": INSTRUCTIONS, "scope": SCOPE,
              "provenance": "transport recorded per receipt; legacy session mode is interactive_agent"}
    save_new(root / "generation.json", seal(record))
    return {"status": "prepared", "root": str(root), "tasks_per_condition": len(task_ids), "scope": SCOPE}


def load_run(root):
    root = Path(root).resolve()
    record = unseal(root / "generation.json")
    if (record.get("schema_version") != 1 or record.get("phase") != "metered_generation_calibration"
            or record.get("driver_sha256") != digest(Path(__file__).read_bytes())
            or record.get("instructions") != INSTRUCTIONS or record.get("scope") != SCOPE
            or record.get("endpoint") != ENDPOINT):
        raise CorpusError("generation driver, prompt or protocol changed; prepare a new run")
    validate_config(record["config"])
    for condition in ("baseline", "treatment"):
        _, session, frozen = load_session(root / condition)
        if (session["condition"] != condition or frozen["fingerprints"] != record["fingerprints"]
                or session["solver"]["id"] != "openai-responses:" + record["config"]["model"]):
            raise CorpusError("generation session differs from its frozen protocol")
    return root, record


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def openai_response(payload, timeout):
    """One HTTP request, no retry, no redirects, no credential in archived data."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise CorpusError("set OPENAI_API_KEY in the process environment before running")
    request = Request(ENDPOINT, data=canonical(payload), method="POST",
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        response = build_opener(NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        raw = response.read(4 * 1024 * 1024 + 1)
        return response.code, response.headers.get("x-request-id"), raw


def usage_from(response):
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if (any(type(usage.get(k)) is not int or usage[k] < 0 for k in keys)
            or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]):
        return None
    for field, key, bound in (("input_tokens_details", "cached_tokens", "input_tokens"),
                              ("output_tokens_details", "reasoning_tokens", "output_tokens")):
        detail = usage.get(field)
        if detail is not None and (not isinstance(detail, dict)
                or type(detail.get(key)) is not int or not 0 <= detail[key] <= usage[bound]):
            return None
    # output_tokens already includes reasoning; do not add it again.
    return usage


def output_text(response):
    output = response.get("output", [])
    if not isinstance(output, list):
        return ""
    return "".join(part.get("text", "") for item in output if isinstance(item, dict)
                   and item.get("type") == "message" and isinstance(item.get("content"), list)
                   for part in item["content"] if isinstance(part, dict)
                   and part.get("type") == "output_text" and isinstance(part.get("text"), str))


def observation(raw):
    """Derive metering from preserved provider bytes, never from proof text."""
    try:
        response = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        response = {}
    if not isinstance(response, dict):
        response = {}
    model = response.get("model")
    return {"usage": usage_from(response),
            "reported_model": model if isinstance(model, str) and model else None,
            "response_id": response.get("id"), "output": output_text(response)}


def payload_for(record, request, history, allowance):
    sampling = record["config"]["sampling"]
    payload = {"model": record["config"]["model"], "store": False,
               "instructions": INSTRUCTIONS,
               "input": json.dumps({"request": request, "previous_attempts": history}, ensure_ascii=False),
               "max_output_tokens": allowance, "text": {"format": FORMAT}}
    payload.update({k: v for k, v in sampling.items() if k != "reasoning_effort"})
    if "reasoning_effort" in sampling:
        payload["reasoning"] = {"effort": sampling["reasoning_effort"]}
    return payload


def submission_for(pending, receipt):
    proof = json.loads(receipt["output"])
    if not isinstance(proof, dict) or set(proof) != {"proof", "bridge"}:
        raise ValueError("expected exactly proof and bridge")
    nonempty_string(proof["proof"], "proof")
    nonempty_string(proof["bridge"], "bridge")
    return {**proof, "task_id": pending["task_id"], "request_sha256": pending["request_sha256"],
            "generation": {"provider": "openai_responses", "call_id": pending["call_id"],
                           "response_sha256": receipt["response_sha256"]}}


def call_records(root, record):
    reservations = sorted((root / "reservations").glob("*.json"))
    if [p.stem for p in reservations] != [f"{i:04d}" for i in range(1, len(reservations) + 1)]:
        raise CorpusError("generation reservation sequence changed")
    if {p.name for p in (root / "calls").iterdir()} - {p.stem for p in reservations}:
        raise CorpusError("generation artifact has no reservation")
    rows = []
    for path in reservations:
        pending = unseal(path)
        budget = record["config"]["budget"]
        ready, expected_allowance = None, None
        if not any(r["result"] is None or r["receipt"] is None or r["receipt"]["usage"] is None
                   or r["result"]["status"] == "provider_exceeded_output_limit" for r in rows):
            for item in record["schedule"]:
                previous = [r for r in rows if all(r["pending"][k] == v for k, v in item.items())]
                spent = sum(r["receipt"]["usage"]["output_tokens"] for r in previous)
                remaining = budget["max_output_tokens_per_task"] - spent
                if (not any(r["result"]["status"] == "verified" for r in previous)
                        and len(previous) < budget["max_calls_per_task"] and remaining >= 16):
                    ready = item
                    expected_allowance = min(budget["max_output_tokens_per_call"], remaining)
                    break
        if ready is None or any(pending[k] != v for k, v in ready.items()) or pending["allowance"] != expected_allowance:
            raise CorpusError("generation launch order or reserved allowance changed")
        folder = root / "calls" / path.stem
        result_path = folder / "result.json"
        request = task_request(root / pending["condition"], pending["task_id"])
        prior = [r for r in rows if (r["pending"]["task_id"], r["pending"]["condition"])
                 == (pending["task_id"], pending["condition"])]
        history = [{"output": r["result"]["output"], "feedback": r["result"]["feedback"]}
                   for r in prior if r["result"] is not None]
        if (pending["call_id"] != path.stem
                or pending["request_sha256"] != request["request_sha256"]
                or {"condition": pending["condition"], "task_id": pending["task_id"]} not in record["schedule"]
                or pending["payload"] != payload_for(record, request, history, pending["allowance"])):
            raise CorpusError("generation reservation differs from its task-local request")
        result = unseal(result_path) if result_path.exists() else None
        receipt_path = folder / "receipt.json"
        receipt = unseal(receipt_path) if receipt_path.exists() else None
        if receipt is not None:
            raw = (folder / "response.bin").read_bytes()
            if (unseal(folder / "pending.json") != pending
                    or receipt["reservation_sha256"] != digest(canonical(pending))
                    or receipt["response_sha256"] != digest(raw)
                    or any(receipt[k] != v for k, v in observation(raw).items())):
                raise CorpusError("provider metering or response fingerprint changed")
        if result is not None:
            if (unseal(folder / "pending.json") != pending
                    or result["reservation_sha256"] != digest(canonical(pending))
                    or receipt is None
                    or any(result[k] != v for k, v in receipt.items())):
                raise CorpusError("generation response or reservation fingerprint changed")
            verification = result["verification"]
            if verification is not None:
                attempt = root / pending["condition"] / "attempts" / pending["task_id"] / f"{verification['attempt']:03d}"
                formal = unseal(attempt / "result.json")
                submission = read_object(attempt / "submission.json")
                if (verification["sha256"] != digest((attempt / "result.json").read_bytes())
                        or verification["submission_sha256"] != digest((attempt / "submission.json").read_bytes())
                        or formal["status"] != result["status"] or formal.get("failure") != result["feedback"]
                        or submission != submission_for(pending, receipt)):
                    raise CorpusError("generation verification artifacts changed")
            elif result["status"] in {"verified", "rejected", "inconclusive"}:
                raise CorpusError("formal generation result has no verification artifact")
        rows.append({"pending": pending, "result": result, "receipt": receipt})
    return rows


def report(root):
    root, record = load_run(root)
    rows = call_records(root, record)
    reports = {c: session_report(root / c) for c in ("baseline", "treatment")}
    tasks, uncertain, interrupted_any = [], False, False
    budget = record["config"]["budget"]
    for item in record["schedule"]:
        calls = [r for r in rows if all(r["pending"][k] == v for k, v in item.items())]
        observed = [r["receipt"]["usage"] if r["receipt"] else None for r in calls]
        known = sum(u["output_tokens"] for u in observed if u is not None)
        charged = sum(u["output_tokens"] if u is not None else r["pending"]["allowance"]
                      for r, u in zip(calls, observed))
        unknown = any(u is None for u in observed)
        interrupted = any(r["result"] is None for r in calls)
        uncertain |= unknown
        interrupted_any |= interrupted
        migration = next(t for t in reports[item["condition"]]["tasks"] if t["id"] == item["task_id"])
        linked = [r["result"]["verification"]["attempt"] for r in calls
                  if r["result"] and r["result"]["verification"] is not None]
        attempts = [a["attempt"] for a in migration["attempts"]]
        if (linked != attempts and not (interrupted and attempts[:len(linked)] == linked
                                       and len(attempts) == len(linked) + 1)):
            raise CorpusError("migration attempts are not completely bound to generation calls")
        if linked != attempts:
            pending_call = next(r for r in calls if r["result"] is None)
            reservation = unseal(root / item["condition"] / "reservations" /
                                 f"{item['task_id']}-{attempts[-1]:03d}.json")
            if (pending_call["receipt"] is None or reservation["submission_sha256"] != digest(canonical(
                    submission_for(pending_call["pending"], pending_call["receipt"])))):
                raise CorpusError("interrupted Lean attempt differs from its provider response")
        if len(calls) > budget["max_calls_per_task"]:
            raise CorpusError("recorded generation exceeds the frozen task budget")
        over_limit = charged > budget["max_output_tokens_per_task"] or any(
            u is not None and u["output_tokens"] > r["pending"]["allowance"]
            for r, u in zip(calls, observed))
        solved = migration["selected"] is not None
        reason = ("provider_exceeded_output_limit" if over_limit else
                  "unknown_usage_or_interrupted_call" if unknown or interrupted else
                  "verified" if solved else
                  "call_budget_exhausted" if len(calls) >= budget["max_calls_per_task"] else
                  "output_budget_exhausted" if budget["max_output_tokens_per_task"] - charged < 16 else None)
        tasks.append({**item, "calls": len(calls), "status": reason or "ready",
                      "observed_output_tokens": known if not unknown else None,
                      "known_output_tokens_lower_bound": known, "charged_output_allowance": charged,
                      "selected": migration["selected"]})
    stop = unseal(root / "stop.json") if (root / "stop.json").exists() else None
    if stop is not None and (stop["calls"] != len(rows) or stop["tasks"] != tasks):
        raise CorpusError("generation stop event differs from the recorded attempts")
    return {"status": "stopped" if stop else "prepared" if not rows else "in_progress",
            "scope": SCOPE, "tasks": tasks, "calls": len(rows),
            "usage_complete": bool(rows) and not uncertain,
            "provider_usage_observed": bool(rows) and all(r["receipt"] and r["receipt"]["usage"] is not None
                                                           and r["receipt"].get("transport")
                                                           == "openai_responses" for r in rows),
            "reported_models": sorted({r["receipt"]["reported_model"] for r in rows
                                       if r["receipt"] and r["receipt"]["reported_model"]}),
            "unknown_usage_or_interrupted_call": uncertain or interrupted_any, "stop": stop}


def check_lean(lean, version):
    executables = [shutil.which(lean), shutil.which("lean")]
    if None in executables:
        raise CorpusError("expose pinned Lean and its child lean command before generation")
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "ELAN_HOME", "TMPDIR", "LANG", "LC_ALL"}}
    env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v" + version
    for executable in dict.fromkeys(executables):
        try:
            result = subprocess.run([executable, "--version"], env=env, capture_output=True,
                                    text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CorpusError("warm the frozen Lean toolchain before generation: " + version) from exc
        match = re.search(r"version (\d+\.\d+\.\d+)", result.stdout)
        if result.returncode or match is None or match.group(1) != version:
            raise CorpusError("warm the frozen Lean toolchain before generation: " + version)


def generate_one(root, record, item, state, transport, lean, transport_kind):
    rows = call_records(root, record)
    request = task_request(root / item["condition"], item["task_id"])
    history = [{"output": r["result"]["output"], "feedback": r["result"]["feedback"]}
               for r in rows if r["result"] and all(r["pending"][k] == v for k, v in item.items())]
    budget = record["config"]["budget"]
    allowance = min(budget["max_output_tokens_per_call"],
                    budget["max_output_tokens_per_task"] - state["charged_output_allowance"])
    call_id = f"{len(rows) + 1:04d}"
    pending = {**item, "call_id": call_id, "started_at": now(), "allowance": allowance,
               "request_sha256": request["request_sha256"],
               "payload": payload_for(record, request, history, allowance)}
    # Independent reservation survives deleted artifacts and interrupted HTTP/Lean.
    save_new(root / "reservations" / (call_id + ".json"), seal(pending))
    folder = root / "calls" / call_id
    folder.mkdir()
    save_new(folder / "pending.json", seal(pending))
    started = time.monotonic()
    result = {"reservation_sha256": digest(canonical(pending)), "usage": None,
              "reported_model": None, "response_id": None, "request_id": None,
              "http_status": None, "status": "transport_error", "output": "",
              "feedback": None, "verification": None}
    try:
        status, request_id, raw = transport(pending["payload"], budget["request_timeout_seconds"])
        result.update(http_status=status, request_id=request_id)
    except (OSError, TimeoutError) as exc:
        raw = b""
        result["feedback"] = {"kind": "transport_error", "exception_type": type(exc).__name__}
    (folder / "response.bin").write_bytes(raw)
    result["response_sha256"] = digest(raw)
    result["seconds"] = time.monotonic() - started
    result.update(observation(raw))
    receipt = {k: result[k] for k in ("reservation_sha256", "response_sha256", "seconds", "http_status", "request_id",
                                     "usage", "reported_model", "response_id", "output")}
    receipt["transport"] = transport_kind
    result["transport"] = transport_kind
    # Save usage before Lean: an interrupted verification still has its receipt.
    save_new(folder / "receipt.json", seal(receipt))
    try:
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise ValueError("provider response must be an object")
        if result["usage"] and result["usage"]["output_tokens"] > allowance:
            result["status"] = "provider_exceeded_output_limit"
            result["feedback"] = {"kind": result["status"]}
        elif result["http_status"] != 200 or response.get("status") != "completed":
            result["status"] = "provider_incomplete_or_error"
            result["feedback"] = {"kind": result["status"], "provider_status": response.get("status"),
                                  "incomplete_details": response.get("incomplete_details")}
        else:
            submission = submission_for(pending, receipt)
            with lean_environment():
                formal = submit_attempt(root / item["condition"], submission, lean=lean)
            attempt = Path(formal["artifact"])
            result.update(status=formal["status"], feedback=formal.get("failure"),
                          verification={"attempt": formal["attempt"],
                                        "sha256": digest((attempt / "result.json").read_bytes()),
                                        "submission_sha256": digest((attempt / "submission.json").read_bytes())})
    except (ValueError, CorpusError) as exc:
        if result["feedback"] is None:
            result.update(status="invalid_response", feedback={"kind": "invalid_response", "message": str(exc)})
    save_new(folder / "result.json", seal(result))
    return result


def run(root, *, lean="lean", transport=None):
    root, record = load_run(root)
    with session_lock(root):
        if (root / "stop.json").exists():
            return report(root)
        # Local tests inject a transport; production always uses the fixed endpoint.
        transport_kind = "injected_test_transport" if transport is not None else "openai_responses"
        if transport is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise CorpusError("set OPENAI_API_KEY in the process environment before running")
            transport = openai_response
        if any(r["receipt"] and r["receipt"]["transport"] != transport_kind for r in call_records(root, record)):
            raise CorpusError("cannot mix test and provider transports within a frozen run")
        _, _, frozen = load_session(root / "baseline")
        check_lean(lean, frozen["manifest"]["lean_version"])
        while True:
            state = report(root)
            if state["stop"]:
                return state
            reason = None
            if state["unknown_usage_or_interrupted_call"]:
                reason = "unknown_usage_or_interrupted_call"
            elif any(r["result"] and r["result"]["status"] == "provider_exceeded_output_limit"
                     for r in call_records(root, record)):
                reason = "provider_exceeded_output_limit"
            ready = next((t for t in state["tasks"] if t["status"] == "ready"), None)
            if reason or ready is None:
                save_new(root / "stop.json", seal({"reason": reason or "schedule_exhausted",
                          "stopped_at": now(), "calls": state["calls"], "tasks": state["tasks"]}))
                return report(root)
            item = {k: ready[k] for k in ("task_id", "condition")}
            generate_one(root, record, item, ready, transport, lean, transport_kind)
