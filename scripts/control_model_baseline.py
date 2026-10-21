#!/usr/bin/env python3
"""Two-goal DeepSeek shortening pilot over verified, unchanged old-tool contexts."""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from maam import CorpusError, baseline_search as search, deepseek
from maam.generation import check_lean, lean_environment, observation
from maam.live_calibration import read_private_key
from maam.migration import canonical, save_new, seal, session_lock, unseal
from maam.theory import digest, read_object
from maam.transfer import commit_for

MODEL = "deepseek-flash"
MAX_CALLS, INPUT_LIMIT, OUTPUT_LIMIT = 2, 16384, 32768
TIMEOUT = 180
SANDBOX = str(REPO / "scripts/lean_sandbox.py")
INPUT_PRICE, OUTPUT_PRICE, MARGIN = Decimal("0.30"), Decimal("1.20"), Decimal("1.25")
MAX_COST = Decimal("0.12")
POLICY = {"schema_version": 1, "evidence_mode": "supplied_local", "max_sweeps": 1,
          "stable_sweeps": 1, "methods": [{"name": "deepseek_existing_tool_shortening",
          "instructions": "Use all supplied existing tools to seek a strictly shorter full Proof module. "
                          "Keep definitions, goal and imports fixed; retain the incumbent if no shorter proof is found."}]}
INSTRUCTIONS = (
    "You are optimizing a Lean 4.24.0 proof using only the supplied task-local sources. "
    "Inspect the incumbent and existing lemmas. Return a shorter proof term beginning with by, "
    "or retain the incumbent. No new imports, axioms, definitions, external tools or other tasks. "
    "All helper text counts toward the full Proof module source cost; correctness and strict shortening "
    "are checked independently. Return JSON with action (candidate or retain), proof and reason. "
    "For retain, proof must be empty. For candidate, proof must be nonempty Lean source. "
    "The request's supplied_local provenance describes the inner verification interface; "
    "this outer call is independently metered DeepSeek generation."
)
FORMAT = {"type": "json_schema", "name": "baseline_shortening", "strict": True, "schema": {
    "type": "object", "properties": {"action": {"type": "string", "enum": ["candidate", "retain"]},
    "proof": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["action", "proof", "reason"], "additionalProperties": False}}
TOOLS = tuple(dict.fromkeys((*search.TOOLS, "maam/deepseek.py", "maam/generation.py",
    "maam/live_calibration.py", "maam/transfer.py", "scripts/control_model_baseline.py")))


def _tools():
    return {p: digest((REPO / p).read_bytes()) for p in TOOLS}


def _cost(inputs, outputs):
    return (inputs * INPUT_PRICE + outputs * OUTPUT_PRICE) * MARGIN / 1_000_000


def payload_for(request):
    return {"model": MODEL, "store": False, "instructions": INSTRUCTIONS,
            "input": canonical(request).decode(), "max_output_tokens": OUTPUT_LIMIT,
            "reasoning": {"effort": "low"}, "text": {"format": FORMAT}}


def prepare(inventory_path, output, *, verify_commit=True):
    inventory = read_object(Path(inventory_path))
    tasks = [row["task_id"] for row in inventory["tasks"]]
    if not 1 <= len(tasks) <= MAX_CALLS or len(set(tasks)) != len(tasks) or set(tasks) - {"d01", "d03"}:
        raise CorpusError("pilot accepts only one or two development goals d01/d03")
    if _cost(MAX_CALLS * INPUT_LIMIT, MAX_CALLS * OUTPUT_LIMIT) > MAX_COST:
        raise CorpusError("fixed reservations exceed the cost ceiling")
    commit = commit_for([REPO / p for p in TOOLS]) if verify_commit else None
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    search.prepare_search(inventory_path, POLICY, root / "search")
    plan = {"schema_version": 1, "task_ids": tasks, "tool_sha256": _tools(),
            "search_plan_sha256": digest((root / "search/plan.json").read_bytes()),
            "source_commit": commit, "model": MODEL, "max_calls": len(tasks),
            "input_reservation_per_call": INPUT_LIMIT, "max_output_tokens_per_call": OUTPUT_LIMIT,
            "max_cost_usd": str(MAX_COST), "pricing_checked_on": "2026-10-21",
            "pricing_source": "https://api-docs.deepseek.com/quick_start/pricing/",
            "input_usd_per_million": str(INPUT_PRICE), "output_usd_per_million": str(OUTPUT_PRICE),
            "cost_margin": str(MARGIN)}
    save_new(root / "plan.json", seal(plan))
    (root / "calls").mkdir()
    (root / "issued.jsonl").write_bytes(canonical(seal({"plan_sha256": digest(canonical(plan))})) + b"\n")
    return report(root)


def _decision(raw, request):
    observed = observation(raw)
    usage = observed["usage"]
    if usage is None:
        return None, "unknown_usage"
    if observed["reported_model"] != MODEL:
        return None, "model_mismatch"
    if usage["input_tokens"] > INPUT_LIMIT or usage["output_tokens"] > OUTPUT_LIMIT:
        return None, "usage_limit_exceeded"
    try:
        body = json.loads(raw)
        if body.get("status") != "completed":
            return None, "provider_response_incomplete"
        output = json.loads(observed["output"])
        if (not isinstance(output, dict) or set(output) != {"action", "proof", "reason"}
                or any(not isinstance(output[k], str) for k in output)
                or not output["reason"].strip()):
            return None, "invalid_model_output"
        if output["action"] == "retain" and output["proof"] == "":
            return {"action": "retain", "request_sha256": request["request_sha256"],
                    "reason": output["reason"]}, None
        if output["action"] == "candidate" and output["proof"].strip():
            return {"action": "candidate", "request_sha256": request["request_sha256"],
                    "proof": output["proof"], "bridge": output["reason"]}, None
    except (ValueError, AttributeError):
        pass
    return None, "invalid_model_output"


def report(output):
    root = Path(output).resolve()
    plan = unseal(root / "plan.json")
    if (plan["tool_sha256"] != _tools() or plan["model"] != MODEL
            or plan["search_plan_sha256"] != digest((root / "search/plan.json").read_bytes())):
        raise CorpusError("model pilot tools or search plan changed")
    child_plan = unseal(root / "search/plan.json")
    tasks = [row["task_id"] for row in child_plan["initial"]]
    if (tasks != plan["task_ids"] or not 1 <= len(tasks) <= MAX_CALLS
            or set(tasks) - {"d01", "d03"} or child_plan["policy"] != POLICY):
        raise CorpusError("pilot scope changed")
    state = search.report(root / "search")
    journal = [json.loads(line) for line in (root / "issued.jsonl").read_bytes().splitlines()]
    for row in journal:
        if row.pop("seal_sha256", None) != digest(canonical(row)):
            raise CorpusError("pilot call journal changed")
    if not journal or journal[0] != {"plan_sha256": digest(canonical(plan))} or len(journal) - 1 > len(tasks):
        raise CorpusError("pilot call journal differs from plan")
    issued = journal[1:]
    if {p.name for p in (root / "calls").iterdir()} != {f"{i:02d}" for i in range(1, len(issued) + 1)}:
        raise CorpusError("call artifacts differ from issued slots; interrupted setup cannot be retried")
    initial = {row["task_id"]: row for row in child_plan["initial"]}
    calls, stopped = [], False
    if len(state["attempts"]) > len(issued):
        raise CorpusError("inner attempt lacks a provider reservation")
    for number, pending in enumerate(issued, 1):
        if stopped:
            raise CorpusError("calls continued after a stopping condition")
        folder = root / "calls" / f"{number:02d}"
        # Each goal is visited once, so its incumbent is always the frozen initial certificate.
        request = search._request(root / "search", child_plan, child_plan["schedule"][number - 1], initial)
        payload = payload_for(request)
        expected = {"slot": number, "request_sha256": digest(canonical(request)),
                    "payload_sha256": digest(canonical(payload)),
                    "input_reservation": INPUT_LIMIT, "output_reservation": OUTPUT_LIMIT}
        if (pending != expected or read_object(folder / "request.json") != request
                or read_object(folder / "payload.json") != payload):
            raise CorpusError("issued call request or payload changed")
        row = {"slot": number, "task_id": request["task_id"], "status": "interrupted",
               "usage": None, "error": "incomplete_call_or_verification"}
        submission, error = None, None
        receipt_path = folder / "receipt.json"
        if receipt_path.exists():
            receipt = unseal(receipt_path)
            if receipt["reservation_sha256"] != digest(canonical(pending)):
                raise CorpusError("provider receipt differs from reservation")
            if receipt["error"] is None:
                raw = (folder / "response.bin").read_bytes()
                if receipt["raw_sha256"] != digest(raw) or receipt["observation"] != observation(raw):
                    raise CorpusError("provider response or usage receipt changed")
                row["usage"] = receipt["observation"]["usage"]
                submission, error = _decision(raw, request)
            else:
                if (receipt["error"] != "provider_request_failed" or receipt["raw_sha256"] is not None
                        or receipt["observation"] is not None or (folder / "response.bin").exists()):
                    raise CorpusError("invalid provider failure receipt")
                error = receipt["error"]
        inner = state["attempts"][number - 1] if len(state["attempts"]) >= number else None
        if inner:
            path = root / "search/attempts" / f"{number:04d}" / "response.json"
            if submission is None or read_object(path) != submission:
                raise CorpusError("Lean submission is not the metered model output")
        outcome = folder / "outcome.json"
        if outcome.exists():
            if not receipt_path.exists():
                raise CorpusError("outcome lacks a provider receipt")
            if error:
                expected_outcome = {"status": "stopped", "error": error}
                if inner:
                    raise CorpusError("invalid provider output unexpectedly reached Lean")
            else:
                if inner is None:
                    raise CorpusError("submitted output lacks inner evidence")
                result = root / "search/attempts" / f"{number:04d}" / "result.json"
                expected_outcome = {"status": "submitted", "search_result_sha256": digest(result.read_bytes())}
            if unseal(outcome) != expected_outcome:
                raise CorpusError("pilot outcome differs from provider or Lean evidence")
            row.update(status="stopped" if error else inner["status"], error=error)
        stopped = not outcome.exists() or error is not None or (inner is not None and inner["status"] == "incomplete")
        calls.append(row)
    stopped = stopped or state["status"] == "interrupted_or_inconclusive"
    usage = None if any(row["usage"] is None for row in calls) else {
        key: sum(row["usage"][key] for row in calls) for key in ("input_tokens", "output_tokens", "total_tokens")}
    status = "stopped" if stopped else "completed" if len(calls) == len(tasks) else "in_progress"
    return {"schema_version": 1, "status": status, "source_commit": plan["source_commit"],
            "provider": "deepseek", "transport": deepseek.TRANSPORT, "requested_model": MODEL,
            "exact_model_revision_verified": False, "actual_provider_calls": len(issued),
            "call_count_scope": "Initiated slots; an interrupted transport may or may not have reached the provider.",
            "calls": calls, "generation_usage": usage,
            "estimated_cost_usd": None if usage is None else str(_cost(usage["input_tokens"], usage["output_tokens"])),
            "reserved_cost_usd": str(_cost(len(issued) * INPUT_LIMIT, len(issued) * OUTPUT_LIMIT)),
            "max_cost_usd": str(MAX_COST), "initial_source_tokens": state["initial_source_tokens"],
            "selected_source_tokens": state["selected_source_tokens"], "search_report": state,
            "scope": "Development-only bounded model attempts; no sufficient-baseline, concept-attribution, "
                     "cognitive-difficulty, exact-revision or training claim. Child supplied_local metadata is "
                     "unchanged; actual provider provenance and metering live in this outer receipt ledger."}


def execute_next(output, key_file):
    root = Path(output).resolve()
    with session_lock(root):
        state = report(root)
        if state["status"] != "in_progress":
            raise CorpusError("no pilot call available; incomplete calls cannot be retried")
        check_lean(SANDBOX, "4.24.0")
        request = search.next_request(root / "search")
        payload = payload_for(request)
        deepseek.input_allowance(payload, INPUT_LIMIT)
        key = read_private_key(key_file)
        number = len(state["calls"]) + 1
        folder = root / "calls" / f"{number:02d}"
        folder.mkdir()
        save_new(folder / "request.json", request)
        save_new(folder / "payload.json", payload)
        pending = {"slot": number, "request_sha256": digest(canonical(request)),
                   "payload_sha256": digest(canonical(payload)),
                   "input_reservation": INPUT_LIMIT, "output_reservation": OUTPUT_LIMIT}
        with (root / "issued.jsonl").open("ab") as stream:
            stream.write(canonical(seal(pending)) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        receipt = {"reservation_sha256": digest(canonical(pending)), "error": None,
                   "raw_sha256": None, "observation": None}
        try:
            code, request_id, raw = deepseek.response(key, payload, TIMEOUT)
        except OSError:
            receipt["error"] = "provider_request_failed"
        else:
            if request_id and key[:20] in request_id:
                request_id = None
            with (folder / "response.bin").open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            receipt.update(raw_sha256=digest(raw), observation=observation(raw),
                           http_status=code, request_id=request_id)
        finally:
            del key
        save_new(folder / "receipt.json", seal(receipt))
        with (folder / "receipt.json").open("rb") as stream:
            os.fsync(stream.fileno())
        submission, error = (None, receipt["error"]) if receipt["error"] else _decision(raw, request)
        if error:
            outcome = {"status": "stopped", "error": error}
        else:
            with lean_environment():
                search.submit(root / "search", submission)
            path = root / "search/attempts" / f"{number:04d}" / "result.json"
            outcome = {"status": "submitted", "search_result_sha256": digest(path.read_bytes())}
        save_new(folder / "outcome.json", seal(outcome))
    return report(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "next", "status"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "prepare" and args.inventory is None:
        parser.error("prepare requires --inventory")
    if args.action == "next" and args.key_file is None:
        parser.error("next requires --key-file")
    try:
        value = (prepare(args.inventory, args.root) if args.action == "prepare" else
                 execute_next(args.root, args.key_file) if args.action == "next" else report(args.root))
        if args.output:
            save_new(args.output, value)
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (CorpusError, OSError, ValueError, KeyError) as exc:
        print("pilot stopped: " + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
