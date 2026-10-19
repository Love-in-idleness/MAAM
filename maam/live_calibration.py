"""Small, private-key calibration around the frozen generation controller.

This synchronous wrapper binds exact input-counted payloads and records its own
source fingerprint. It does not modify the earlier controller or its evidence.
"""
from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path
import re
import stat
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from . import generation
from .corpus import CorpusError
from .migration import canonical, save_new, seal, task_request
from .theory import digest

MODEL = "gpt-6-luna"
INPUT_LIMIT = 8192
OUTPUT_LIMIT = 2048
MAX_USD = Decimal("0.05")
INPUT_PRICE = Decimal("0.125")
OUTPUT_PRICE = Decimal("0.50")
PRICE_MARGIN = Decimal("10")
PRICE_SOURCE = "https://developers.openai.com/api/docs/models/gpt-6-luna"
COUNT_ENDPOINT = generation.ENDPOINT + "/input_tokens"


def read_private_key(path):
    """Read only an explicitly selected, owner-only regular file; never log it."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 4096):
            raise CorpusError("key source must be a private owner-only regular file")
        key = handle.read().strip()
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,}", key):
        raise CorpusError("key source must contain one API key without extra text")
    return key


def private_http(key, endpoint, payload, timeout):
    """No redirects/retries; provider error bodies never reach an archive/log."""
    if endpoint not in {generation.ENDPOINT, COUNT_ENDPOINT}:
        raise OSError("provider_endpoint_blocked")
    body = canonical(payload)
    if key.encode() in body or key[:20].encode() in body:
        raise OSError("credential_in_payload_blocked")
    request = Request(endpoint, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        response = build_opener(generation.NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        # Auth errors can echo key fragments. Do not read, print or save them.
        code = exc.code
        exc.close()
        raise OSError(f"provider_http_{code}") from None
    with response:
        if response.code != 200:
            raise OSError(f"provider_http_{response.code}")
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise OSError("provider_response_too_large")
        if key.encode() in raw or key[:20].encode() in raw:
            raise OSError("credential_echo_blocked")
        return response.code, response.headers.get("x-request-id"), raw


def upper_cost(inputs, outputs):
    return (Decimal(inputs) * INPUT_PRICE + Decimal(outputs) * OUTPUT_PRICE) / Decimal(1_000_000) * PRICE_MARGIN


def execute(root, key_file, lean, *, http=None):
    """One development goal, two conditions, one call each, no automatic retry."""
    root = Path(root).resolve()
    lean = Path(lean).resolve()
    if lean.name != "lean_sandbox.py" or not lean.is_file():
        raise CorpusError("this calibration requires the lean_sandbox.py wrapper")
    suite = Path(__file__).resolve().parents[1] / "experiments/hom_kernel_migration/suite.json"
    config = {"model": MODEL, "sampling": {"reasoning_effort": "low"}, "budget": {
        "max_calls_per_task": 1, "max_output_tokens_per_call": OUTPUT_LIMIT,
        "max_output_tokens_per_task": OUTPUT_LIMIT, "request_timeout_seconds": 120}}
    generation.check_lean(str(lean), "4.24.0")
    generation.prepare(suite, root, config, ["d01"])
    _, record = generation.load_run(root)
    (root / "guard-reservations").mkdir()
    plan = {"schema_version": 1, "model": MODEL, "max_generation_calls": 2,
            "max_input_tokens_per_call": INPUT_LIMIT, "max_output_tokens_per_call": OUTPUT_LIMIT,
            "max_usd": str(MAX_USD), "price_margin": str(PRICE_MARGIN),
            "price_source": PRICE_SOURCE, "price_checked_date": "2026-10-20",
            "input_usd_per_million_upper": str(INPUT_PRICE), "output_usd_per_million": str(OUTPUT_PRICE),
            "guard_sha256": digest(Path(__file__).read_bytes()),
            "sandbox_sha256": digest(lean.read_bytes()),
            "pricing_scope": "conservative local estimate; not an account-wide spend limit or invoice"}
    save_new(root / "guard-plan.json", seal(plan))
    # Only this process reads the key; the path and value are absent from records.
    key = read_private_key(key_file)
    http = private_http if http is None else http
    payloads, counts, reserved = [], [], Decimal(0)
    try:
        for index, item in enumerate(record["schedule"], 1):
            request = task_request(root / item["condition"], item["task_id"])
            payload = generation.payload_for(record, request, [], OUTPUT_LIMIT)
            counted_input = {k: payload[k] for k in ("model", "input", "instructions", "reasoning", "text")
                             if k in payload}
            status, request_id, raw = http(key, COUNT_ENDPOINT, counted_input, 60)
            value = json.loads(raw)
            count = value.get("input_tokens") if isinstance(value, dict) else None
            if status != 200 or type(count) is not int or not 0 < count <= INPUT_LIMIT:
                raise OSError("input_count_preflight_failed")
            allowance = upper_cost(count, OUTPUT_LIMIT)
            if reserved + allowance > MAX_USD:
                raise OSError("cost_preflight_exceeds_run_ceiling")
            reserved += allowance
            payloads.append(canonical(payload))
            counts.append(count)
            save_new(root / f"input-count-{index:02d}.json", seal({**item, "input_tokens": count,
                "request_id": request_id, "payload_sha256": digest(canonical(payload)),
                "guarded_cost_allowance_usd": str(allowance)}))
        save_new(root / "guard-preflight.json", seal({"status": "passed", "input_tokens": counts,
                  "guarded_total_allowance_usd": str(reserved), "generation_calls": 0}))
    except (OSError, ValueError) as exc:
        # Only errors produced by private_http itself are safe to retain.
        code = str(exc) if isinstance(exc, OSError) and re.fullmatch(r"[a-z_]+(?:_\d{3})?", str(exc)) else "preflight_failed"
        save_new(root / "guard-stop.json", seal({"reason": code, "generation_calls": 0,
                  "completed_input_counts": len(counts)}))
        return {"status": "preflight_stopped", "reason": code, "generation_calls": 0}

    calls = 0

    def guarded_transport(payload, timeout):
        nonlocal calls
        if calls >= 2 or canonical(payload) != payloads[calls]:
            raise OSError("uncounted_or_extra_payload_blocked")
        calls += 1
        save_new(root / "guard-reservations" / f"{calls:02d}.json", seal({
            "call": calls, "payload_sha256": digest(canonical(payload)),
            "input_tokens": counts[calls - 1], "max_output_tokens": OUTPUT_LIMIT,
            "guarded_cost_allowance_usd": str(upper_cost(counts[calls - 1], OUTPUT_LIMIT))}))
        status, request_id, raw = http(key, generation.ENDPOINT, payload, timeout)
        return status, request_id, raw

    original_transport = generation.openai_response
    original_key = os.environ.get("OPENAI_API_KEY")
    try:
        # Keep the frozen controller's real-provider label; no test-transport path.
        generation.openai_response = guarded_transport
        os.environ["OPENAI_API_KEY"] = key
        result = generation.run(root, lean=str(lean))
    finally:
        generation.openai_response = original_transport
        if original_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original_key
    verified = (result["provider_usage_observed"] and result["usage_complete"]
                and all(t["status"] == "verified" for t in result["tasks"]))
    summary = {"status": "verified" if verified else "stopped", "generation_calls": calls,
               "guarded_total_allowance_usd": str(reserved), "result": result}
    save_new(root / "live-summary.json", summary)
    return summary
