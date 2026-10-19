"""Pre-registered paired transfer runs around the unchanged generation checker.

Legacy records retain their calibration scope. This controller adds phase gates
and whole-run reservations bound to each repair payload; it never infers efficacy.
"""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import subprocess

from . import generation as gen
from . import deepseek
from .corpus import CorpusError
from .live_calibration import read_private_key
from .migration import (canonical, compare_sessions, save_new, seal,
                        session_lock, start_session, task_request, unseal)
from .theory import digest, inside
from .transfer_protocol import cost_for, load_protocol, schedule

REPO = Path(__file__).resolve().parents[1]
SANDBOX = REPO / "scripts/lean_sandbox.py"
CONTROLLERS = [Path(__file__), Path(__file__).with_name("transfer_protocol.py"),
               Path(deepseek.__file__),
               Path(gen.__file__), Path(__file__).with_name("live_calibration.py"),
               Path(__file__).with_name("migration.py"), Path(__file__).with_name("theory.py"),
               Path(__file__).with_name("PackageCheck.lean"), SANDBOX,
               REPO / "scripts/control_transfer.py"]
PHASES = ("development", "reserved")


def controller_hashes():
    return {str(p.relative_to(REPO)): digest(p.read_bytes()) for p in CONTROLLERS}


def commit_for(paths):
    """A live run must start from committed, byte-identical experiment inputs."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                         stderr=subprocess.DEVNULL).decode().strip()
        for path in paths:
            relative = str(path.resolve().relative_to(REPO))
            blob = subprocess.check_output(["git", "show", f"{commit}:{relative}"],
                                           cwd=REPO, stderr=subprocess.DEVNULL)
            if blob != path.read_bytes():
                raise CorpusError("commit the frozen protocol and controller before preparing a live run")
        return commit
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise CorpusError("all live-run inputs must exist in the frozen repository commit") from exc


def prepare(protocol, root, *, verify_commit=True):
    protocol = Path(protocol).resolve()
    loaded = load_protocol(protocol)
    spec, frozen = loaded["manifest"], loaded["frozen"]
    suite = inside(protocol.parent, spec["suite"]["path"], "suite")
    files = [protocol, suite, inside(suite.parent, frozen["manifest"]["package"], "package")]
    files += [inside(suite.parent, s["path"], "source") for s in frozen["manifest"]["sources"].values()]
    commit = commit_for(files + CONTROLLERS) if verify_commit else None
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    snapshot = root / "snapshot"
    snapshot.mkdir()
    for path in files:
        dest = inside(snapshot, str(path.relative_to(protocol.parent)), "snapshot")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    for name in ("budget-reservations", "input-counts", "stages"):
        (root / name).mkdir()
    for phase in PHASES:
        stage = root / "stages" / phase
        stage.mkdir()
        for condition in ("baseline", "treatment"):
            start_session(suite, stage / condition, condition=condition,
                          solver_id="openai-responses:" + spec["config"]["model"])
        for name in ("reservations", "calls"):
            (stage / name).mkdir()
        # Additive adapter: do not rewrite original reserved labels or scope flags.
        record = {"schema_version": 1, "phase": "metered_generation_calibration",
                  "provider": "openai_responses", "endpoint": gen.ENDPOINT,
                  "prepared_at": gen.now(), "config": spec["config"],
                  "schedule": schedule(loaded, phase), "driver_sha256": digest(Path(gen.__file__).read_bytes()),
                  "fingerprints": frozen["fingerprints"], "instructions": gen.INSTRUCTIONS,
                  "scope": gen.SCOPE,
                  "provenance": "legacy format only; actual provider is DeepSeek at https://api.deepseek.com/responses; original splits retained"}
        save_new(stage / "generation.json", seal(record))
    plan = {"schema_version": 1, "protocol_file": str(protocol.relative_to(protocol.parent)),
            "fingerprints": loaded["fingerprints"], "controllers": controller_hashes(),
            "freeze_commit": commit, "endpoint": deepseek.ENDPOINT, "provider": "deepseek",
            "input_policy": "reserve full input cap; local byte screen, not provider token count",
            "prepared_at": gen.now()}
    save_new(root / "plan.json", seal(plan))
    return report(root)


def load(root):
    root = Path(root).resolve()
    plan = unseal(root / "plan.json")
    loaded = load_protocol(inside(root / "snapshot", plan["protocol_file"], "protocol"))
    if (plan["fingerprints"] != loaded["fingerprints"] or plan["controllers"] != controller_hashes()
            or plan["endpoint"] != deepseek.ENDPOINT or plan["provider"] != "deepseek"):
        raise CorpusError("frozen protocol, controller or isolation wrapper changed")
    for phase in PHASES:
        _, record = gen.load_run(root / "stages" / phase)
        if (record["schedule"] != schedule(loaded, phase) or record["config"] != loaded["manifest"]["config"]
                or record["fingerprints"] != loaded["frozen"]["fingerprints"]):
            raise CorpusError("stage differs from the frozen transfer protocol")
    return root, plan, loaded


def next_payload(stage, record, state):
    item = {k: state[k] for k in ("task_id", "condition")}
    prior = [r for r in gen.call_records(stage, record)
             if all(r["pending"][k] == v for k, v in item.items())]
    history = [{"output": r["result"]["output"], "feedback": r["result"]["feedback"]}
               for r in prior if r["result"]]
    budget = record["config"]["budget"]
    allowance = min(budget["max_output_tokens_per_call"],
                    budget["max_output_tokens_per_task"] - state["charged_output_allowance"])
    request = task_request(stage / item["condition"], item["task_id"])
    return item, gen.payload_for(record, request, history, allowance)


def phase_complete(state):
    complete = bool(state["stop"] and state["stop"]["reason"] == "schedule_exhausted")
    if complete and any(t["status"] not in {"verified", "call_budget_exhausted", "output_budget_exhausted"}
                        for t in state["tasks"]):
        raise CorpusError("stage claimed completion before exhausting its frozen schedule")
    return complete


def budget_ledger(root, loaded):
    """Replay authoritative reservations against raw metering, including crashes."""
    budget = loaded["manifest"]["experiment_budget"]
    paths = sorted((root / "budget-reservations").glob("*.json"))
    if [p.stem for p in paths] != [f"{n:04d}" for n in range(1, len(paths) + 1)]:
        raise CorpusError("whole-run reservation sequence changed")
    all_rows = {}
    for phase in PHASES:
        stage, record = gen.load_run(root / "stages" / phase)
        all_rows[phase] = gen.call_records(stage, record)
    seen, inputs, outputs, known_inputs, known_outputs = set(), 0, 0, 0, 0
    charged_cost, known_cost = Decimal(0), Decimal(0)
    unknown, interrupted, violations, provider = False, False, [], bool(paths)
    last_phase = "development"
    local_counts = {phase: 0 for phase in PHASES}
    for index, path in enumerate(paths, 1):
        guard = unseal(path)
        phase, call_id = guard["split"], guard["local_call_id"]
        if (phase not in PHASES or (last_phase == "reserved" and phase != "reserved")
                or guard["index"] != index or (phase, call_id) in seen
                or call_id != f"{local_counts[phase] + 1:04d}"):
            raise CorpusError("whole-run call order changed")
        last_phase = phase
        local_counts[phase] += 1
        seen.add((phase, call_id))
        folder = root / "input-counts" / path.stem
        counted = unseal(folder / "count.json")
        pending = unseal(folder / "pending.json")
        raw = (folder / "response.bin").read_bytes()
        value = json.loads(raw)
        if (not isinstance(value, dict)
                or guard["count_sha256"] != digest((folder / "count.json").read_bytes())
                or counted["raw_sha256"] != digest(raw)
                or counted["input_tokens"] != value.get("input_tokens")
                or type(counted["input_tokens"]) is not int or counted["input_tokens"] <= 0
                or counted["input_tokens"] > budget["max_input_tokens_per_call"]
                or pending["split"] != phase or pending["local_call_id"] != call_id
                or guard["payload_sha256"] != digest(canonical(pending["payload"]))
                or counted["payload_sha256"] != guard["payload_sha256"]
                or guard["input_tokens"] != counted["input_tokens"]
                or guard["output_allowance"] != pending["payload"]["max_output_tokens"]
                or Decimal(guard["cost_allowance_usd"]) != cost_for(budget, guard["input_tokens"], guard["output_allowance"])):
            raise CorpusError("input count or whole-run cost reservation changed")
        if (index > budget["max_generation_calls"]
                or inputs + guard["input_tokens"] > budget["max_total_input_tokens"]
                or outputs + guard["output_allowance"] > budget["max_total_output_tokens"]
                or charged_cost + Decimal(guard["cost_allowance_usd"]) > Decimal(budget["max_cost_usd"])):
            raise CorpusError("whole-run reservation exceeded its frozen preflight budget")
        rows = all_rows[phase]
        number = int(call_id)
        row = rows[number - 1] if 0 < number <= len(rows) else None
        if row is None:
            if index != len(paths) or number != len(rows) + 1:
                raise CorpusError("missing generation reservation before a later call")
            stage, record = gen.load_run(root / "stages" / phase)
            state = next((t for t in gen.report(stage)["tasks"] if t["status"] == "ready"), None)
            if state is None or next_payload(stage, record, state)[1] != pending["payload"]:
                raise CorpusError("unstarted reservation differs from the next frozen payload")
        elif (row["pending"]["call_id"] != call_id
              or row["pending"]["payload"] != pending["payload"]):
            raise CorpusError("guard reservation differs from the actual generation payload")
        usage = row["receipt"]["usage"] if row and row["receipt"] else None
        interrupted |= row is None or row["result"] is None
        unknown |= usage is None
        provider &= bool(row and row["receipt"] and row["receipt"]["transport"] == deepseek.TRANSPORT)
        if row and row["receipt"] and row["receipt"]["transport"] == deepseek.TRANSPORT:
            if value != json.loads(deepseek.input_allowance(pending["payload"], budget["max_input_tokens_per_call"])[2]):
                raise CorpusError("DeepSeek input allowance differs from the frozen local policy")
        if usage is None:
            inputs += guard["input_tokens"]
            outputs += guard["output_allowance"]
            charged_cost += Decimal(guard["cost_allowance_usd"])
        else:
            known_inputs += usage["input_tokens"]
            known_outputs += usage["output_tokens"]
            inputs += usage["input_tokens"]
            outputs += usage["output_tokens"]
            amount = cost_for(budget, usage["input_tokens"], usage["output_tokens"])
            known_cost += amount
            charged_cost += amount
            if usage["input_tokens"] > guard["input_tokens"]:
                violations.append("provider_input_exceeded_count")
            if usage["output_tokens"] > guard["output_allowance"]:
                violations.append("provider_output_exceeded_allowance")
            if row["receipt"]["reported_model"] != loaded["manifest"]["config"]["model"]:
                violations.append("reported_model_mismatch")
        if phase == "reserved" and not phase_complete(gen.report(root / "stages/development")):
            raise CorpusError("reserved calls preceded development completion")
        if (len(seen) > budget["max_generation_calls"] or inputs > budget["max_total_input_tokens"]
                or outputs > budget["max_total_output_tokens"] or charged_cost > Decimal(budget["max_cost_usd"])):
            violations.append("run_budget_exceeded")
        if index < len(paths) and (unknown or interrupted or violations):
            raise CorpusError("generation continued after an unknown, interrupted or violating call")
    actual = {(phase, r["pending"]["call_id"]) for phase, rows in all_rows.items() for r in rows}
    if actual - seen:
        raise CorpusError("generation call has no whole-run budget reservation")
    return {"generation_calls": len(paths), "usage_complete": bool(paths) and not unknown,
            "interrupted": interrupted, "provider_evidence": provider and not unknown,
            "input_tokens": known_inputs if not unknown else None,
            "output_tokens": known_outputs if not unknown else None,
            "known_input_tokens_lower_bound": known_inputs, "known_output_tokens_lower_bound": known_outputs,
            "charged_input_tokens": inputs, "charged_output_tokens": outputs,
            "guarded_cost_usd": str(charged_cost), "known_guarded_cost_lower_bound_usd": str(known_cost),
            "violations": sorted(set(violations))}


def report(root):
    root, plan, loaded = load(root)
    ledger = budget_ledger(root, loaded)
    stages = {}
    for phase in PHASES:
        stage = root / "stages" / phase
        state = gen.report(stage)
        comparison = compare_sessions(stage / "baseline", stage / "treatment")
        comparison["tasks"] = [t for t in comparison["tasks"] if t["split"] == phase]
        complete = phase_complete(state)
        stages[phase] = {"complete": complete, "generation": state, "comparison": comparison}
    stop = unseal(root / "stop.json") if (root / "stop.json").exists() else None
    if stop and stop["ledger"] != ledger:
        raise CorpusError("transfer stop event differs from the replayed budget ledger")
    finished = all(s["complete"] for s in stages.values())
    return {"status": "stopped" if stop else "completed" if finished else "prepared" if not ledger["generation_calls"] else "in_progress",
            "study_id": loaded["manifest"]["study_id"], "freeze_commit": plan["freeze_commit"],
            "provider": "deepseek", "endpoint": deepseek.ENDPOINT,
            "ledger": ledger, "stages": stages, "stop": stop,
            "matched_allocations_complete": finished and ledger["usage_complete"] and not ledger["violations"] and not ledger["interrupted"],
            "exact_model_revision_verified": False, "held_out_effectiveness_claim": False,
            "training_eligible": False,
            "pricing_scope": "conservative local estimate with frozen rates/margin; not an account cap or invoice",
            "legacy_scope": "underlying generation records remain calibration; phase comes from the outer protocol"}


def stop(root, reason):
    _, _, loaded = load(root)
    save_new(root / "stop.json", seal({"reason": reason, "stopped_at": gen.now(),
                                      "ledger": budget_ledger(root, loaded)}))
    return report(root)


def run(root, phase, *, key_file=None, transport=None, count_input=None):
    """No automatic retries. Injected counting/transport are strictly offline evidence."""
    root, plan, loaded = load(root)
    if phase not in PHASES:
        raise CorpusError("choose development or reserved")
    offline = transport is not None or count_input is not None
    if offline and (transport is None or count_input is None):
        raise CorpusError("offline runs require both synthetic counting and transport")
    with session_lock(root):
        state = report(root)
        if state["stop"]:
            return state
        if state["ledger"]["interrupted"] or (state["ledger"]["generation_calls"] and not state["ledger"]["usage_complete"]):
            return stop(root, "unknown_usage_or_interrupted_call")
        if state["ledger"]["violations"]:
            return stop(root, "provider_limit_or_model_mismatch")
        if phase == "reserved" and not state["stages"]["development"]["complete"]:
            raise CorpusError("finish the frozen development stage before reserved evaluation")
        stage, record = gen.load_run(root / "stages" / phase)
        kind = "injected_test_transport" if offline else deepseek.TRANSPORT
        for previous_phase in PHASES:
            p, r = gen.load_run(root / "stages" / previous_phase)
            if any(row["receipt"] and row["receipt"]["transport"] != kind for row in gen.call_records(p, r)):
                raise CorpusError("cannot mix fixture and provider evidence")
        if state["stages"][phase]["complete"]:
            return state
        gen.check_lean(str(SANDBOX), loaded["frozen"]["manifest"]["lean_version"])
        if not offline:
            if plan["freeze_commit"] is None:
                raise CorpusError("fixture preparation cannot be used for paid generation")
            key = read_private_key(key_file)
            transport = lambda payload, timeout: deepseek.response(key, payload, timeout)
            count_input = lambda payload, timeout: deepseek.input_allowance(payload, loaded["manifest"]["experiment_budget"]["max_input_tokens_per_call"])
        budget = loaded["manifest"]["experiment_budget"]
        while True:
            state = report(root)
            ledger = state["ledger"]
            if ledger["interrupted"] or (ledger["generation_calls"] and not ledger["usage_complete"]):
                return stop(root, "unknown_usage_or_interrupted_call")
            if ledger["violations"]:
                return stop(root, "provider_limit_or_model_mismatch")
            ready = next((t for t in state["stages"][phase]["generation"]["tasks"] if t["status"] == "ready"), None)
            if ready is None:
                gstate = gen.report(stage)
                save_new(stage / "stop.json", seal({"reason": "schedule_exhausted", "stopped_at": gen.now(),
                          "calls": gstate["calls"], "tasks": gstate["tasks"]}))
                return report(root)
            if ledger["generation_calls"] >= budget["max_generation_calls"]:
                return stop(root, "run_call_input_output_or_cost_limit")
            item, payload = next_payload(stage, record, ready)
            index = f"{ledger['generation_calls'] + 1:04d}"
            local_id = f"{state['stages'][phase]['generation']['calls'] + 1:04d}"
            folder = root / "input-counts" / index
            if folder.exists():
                return stop(root, "interrupted_input_count")
            folder.mkdir()
            save_new(folder / "pending.json", seal({"split": phase, "local_call_id": local_id,
                                                    "payload": payload, "started_at": gen.now()}))
            count_payload = ({k: payload[k] for k in ("model", "input", "instructions", "reasoning", "text") if k in payload}
                             if offline else payload)
            try:
                status, request_id, raw = count_input(count_payload, 60)
                (folder / "response.bin").write_bytes(raw)
                value = json.loads(raw)
                count = value.get("input_tokens") if isinstance(value, dict) else None
                if status != 200 or type(count) is not int or not 0 < count <= budget["max_input_tokens_per_call"]:
                    return stop(root, "input_count_failed_or_over_limit")
                save_new(folder / "count.json", seal({"payload_sha256": digest(canonical(payload)),
                          "input_tokens": count, "request_id": request_id, "raw_sha256": digest(raw)}))
            except (OSError, ValueError):
                return stop(root, "input_count_failed_or_over_limit")
            allowance = payload["max_output_tokens"]
            amount = cost_for(budget, count, allowance)
            if (ledger["charged_input_tokens"] + count > budget["max_total_input_tokens"]
                    or ledger["charged_output_tokens"] + allowance > budget["max_total_output_tokens"]
                    or Decimal(ledger["guarded_cost_usd"]) + amount > Decimal(budget["max_cost_usd"])):
                return stop(root, "run_call_input_output_or_cost_limit")
            guard = {"index": int(index), "split": phase, "local_call_id": local_id,
                     "payload_sha256": digest(canonical(payload)), "input_tokens": count,
                     "output_allowance": allowance, "cost_allowance_usd": str(amount),
                     "count_sha256": digest((folder / "count.json").read_bytes())}
            save_new(root / "budget-reservations" / (index + ".json"), seal(guard))
            used = False

            def bound_transport(actual, timeout):
                nonlocal used
                if used or canonical(actual) != canonical(payload):
                    raise OSError("uncounted_or_extra_payload_blocked")
                used = True
                return transport(actual, timeout)

            gen.generate_one(stage, record, item, ready, bound_transport, str(SANDBOX), kind)
