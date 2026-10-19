"""Frozen task order and conservative budgets for a metered transfer study."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
import re

from .corpus import CorpusError
from .generation import validate_config
from .migration import load_suite
from .theory import digest, inside, nonempty_string, read_object


STOPPING = ["first_verified", "task_call_or_output_limit",
            "run_call_input_output_or_cost_limit", "unknown_usage",
            "interrupted_call_or_verification", "provider_limit_or_model_mismatch"]
SCOPE = {"author_constructed_tasks": True, "candidate_fixed": True,
         "representative_population_claim": False, "exact_model_revision_verified": False,
         "training_eligible": False}
PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
INTEGER_LIMITS = {"max_generation_calls", "max_input_tokens_per_call",
                  "max_total_input_tokens", "max_total_output_tokens"}
DECIMAL_LIMITS = {"max_cost_usd", "input_usd_per_million", "output_usd_per_million", "cost_margin"}


def _positive_decimal(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise CorpusError(label + " must be a positive decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise CorpusError(label + " must be a positive decimal string") from exc
    if not number.is_finite() or number <= 0:
        raise CorpusError(label + " must be a finite positive decimal string")
    return number


def cost_for(budget, input_tokens, output_tokens):
    """Return a conservative Decimal dollar estimate, including the frozen margin."""
    if any(type(tokens) is not int or tokens < 0 for tokens in (input_tokens, output_tokens)):
        raise CorpusError("cost token counts must be nonnegative integers")
    rates = [_positive_decimal(budget[key], key) for key in
             ("input_usd_per_million", "output_usd_per_million", "cost_margin")]
    # Size precision to the inputs so integer-token arithmetic does not round money.
    with localcontext() as context:
        context.prec = (len(str(input_tokens)) + len(str(output_tokens))
                        + sum(len(value.as_tuple().digits) for value in rates) + 8)
        return ((Decimal(input_tokens) * rates[0] + Decimal(output_tokens) * rates[1])
                * rates[2] / Decimal(1_000_000))


def _validate_budget(budget, config, task_count):
    fields = INTEGER_LIMITS | DECIMAL_LIMITS | {"pricing_checked_on", "pricing_source"}
    if not isinstance(budget, dict) or set(budget) != fields:
        raise CorpusError("experiment budget fields differ from the transfer protocol")
    if any(type(budget[key]) is not int or budget[key] <= 0 for key in INTEGER_LIMITS):
        raise CorpusError("experiment token and call limits must be positive integers")
    values = {key: _positive_decimal(budget[key], key) for key in DECIMAL_LIMITS}
    if (values["input_usd_per_million"] < Decimal("0.30")
            or values["output_usd_per_million"] < Decimal("1.20")
            or values["cost_margin"] < Decimal(1)):
        raise CorpusError("transfer pricing must cover the pinned DeepSeek Flash rates with margin at least one")
    checked = budget["pricing_checked_on"]
    if not isinstance(checked, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked):
        raise CorpusError("pricing_checked_on must be a valid YYYY-MM-DD date")
    try:
        date.fromisoformat(checked)
    except ValueError as exc:
        raise CorpusError("pricing_checked_on must be a valid YYYY-MM-DD date") from exc
    if budget["pricing_source"] != PRICING_SOURCE:
        raise CorpusError("transfer pricing source must be the official DeepSeek Flash model page")
    per_task = config["budget"]
    calls = budget["max_generation_calls"]
    capacity = task_count * 2
    if calls > capacity * per_task["max_calls_per_task"]:
        raise CorpusError("global generation call limit exceeds the frozen schedule capacity")
    if budget["max_total_input_tokens"] > calls * budget["max_input_tokens_per_call"]:
        raise CorpusError("global input token limit exceeds the frozen call capacity")
    output_capacity = min(calls * per_task["max_output_tokens_per_call"],
                          capacity * per_task["max_output_tokens_per_task"])
    if budget["max_total_output_tokens"] > output_capacity:
        raise CorpusError("global output token limit exceeds the frozen schedule capacity")


def load_protocol(path):
    path = Path(path).resolve()
    data = read_object(path)
    fields = {"schema_version", "study_id", "phase", "suite", "config",
              "experiment_budget", "task_order", "stopping", "scope"}
    if set(data) != fields or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise CorpusError("expected transfer protocol schema 1 with the fixed fields")
    if data["phase"] != "pre_registered_transfer_comparison":
        raise CorpusError("expected pre_registered_transfer_comparison phase")
    nonempty_string(data["study_id"], "study_id")
    descriptor = data["suite"]
    if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256"}:
        raise CorpusError("suite descriptor needs exactly path and sha256")
    suite = inside(path.parent, descriptor["path"], "suite")
    try:
        suite_hash = digest(suite.read_bytes())
    except OSError as exc:
        raise CorpusError("cannot read the transfer suite") from exc
    if descriptor["sha256"] != suite_hash:
        raise CorpusError("transfer protocol suite fingerprint changed")
    frozen = load_suite(suite)
    validate_config(data["config"])
    if (data["config"]["model"] != "deepseek-flash"
            or data["config"]["sampling"] != {"reasoning_effort": "low"}):
        raise CorpusError("this transfer protocol pins deepseek-flash with low reasoning")
    if (data["config"]["budget"]["max_calls_per_task"]
            > frozen["manifest"]["budget"]["max_attempts_per_task"]):
        raise CorpusError("generation calls cannot exceed the frozen proof-attempt limit")
    order = data["task_order"]
    if not isinstance(order, dict) or set(order) != {"development", "reserved"}:
        raise CorpusError("task order must define development and reserved splits")
    tasks = {task["id"]: task for task in frozen["manifest"]["tasks"]}
    seen = set()
    for split, ids in order.items():
        if (not isinstance(ids, list) or not ids
                or any(not isinstance(task, str) or task not in tasks for task in ids)
                or len(set(ids)) != len(ids)):
            raise CorpusError("each split needs a nonempty ordered list of distinct suite task ids")
        if seen.intersection(ids) or any(tasks[task]["split"] != split for task in ids):
            raise CorpusError("protocol task splits differ from the frozen suite")
        seen.update(ids)
    if seen != set(tasks):
        raise CorpusError("task order must cover every suite task exactly once")
    _validate_budget(data["experiment_budget"], data["config"], len(tasks))
    if data["stopping"] != STOPPING:
        raise CorpusError("transfer stopping rules differ from the fixed protocol")
    scope = data["scope"]
    if (not isinstance(scope, dict) or set(scope) != set(SCOPE)
            or any(type(scope[key]) is not bool or scope[key] is not value for key, value in SCOPE.items())):
        raise CorpusError("transfer scope must retain the declared evidence limitations")
    return {"manifest": data, "frozen": frozen, "fingerprints": {
        "protocol_sha256": digest(path.read_bytes()),
        "source_fingerprints": frozen["fingerprints"],
        "protocol_validator_sha256": digest(Path(__file__).read_bytes())}}


def schedule(protocol, split):
    if split not in {"development", "reserved"}:
        raise CorpusError("choose the development or reserved split")
    return [{"task_id": task, "condition": condition}
            for index, task in enumerate(protocol["manifest"]["task_order"][split])
            for condition in (("baseline", "treatment") if index % 2 == 0
                              else ("treatment", "baseline"))]
