"""A fixed executable method card, guarded by exact development-source identity."""
from pathlib import Path
import re
from string import Formatter

from .corpus import CorpusError
from .migration import canonical, proof_source
from .theory import digest, read_object

PARAMETERS = {"group", "element", "equality", "result"}
LAWS = ["mul_assoc", "inv_mul", "one_mul", "mul_one"]
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_']*"
KEYWORDS = {"by", "sorry", "admit", "axiom", "theorem", "def", "unsafe", "import",
            "set_option", "run_tac", "fun", "let", "in", "match", "where", "_"}


def _strings(value, keys):
    return (isinstance(value, dict) and set(value) == set(keys)
            and all(isinstance(v, str) and v.strip() for v in value.values()))


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _template(value, fields):
    if not isinstance(value, str) or not value.strip() or "{{" in value or "}}" in value:
        raise CorpusError("invalid method template")
    try:
        parsed = list(Formatter().parse(value))
    except ValueError as exc:
        raise CorpusError("invalid method template") from exc
    names = []
    for _, name, spec, conversion in parsed:
        if name is not None:
            if name not in fields or spec or conversion:
                raise CorpusError("method template accepts only declared plain placeholders")
            names.append(name)
    if set(names) != fields:
        raise CorpusError("method template must use every declared parameter")


def validate_card(card):
    fields = {"schema_version", "id", "origin", "entry", "parameters", "required_laws",
              "proof_template", "knowledge", "obligations", "applications", "limits"}
    if (not isinstance(card, dict) or set(card) != fields
            or type(card["schema_version"]) is not int or card["schema_version"] != 1
            or card["id"] != "left_inverse_cancel_v1"
            or not _strings(card["origin"], {"kind", "task_id", "proof_sha256"})
            or card["origin"]["task_id"] != "d03"
            or card["origin"]["kind"] != "author_extraction_from_verified_model_proof"
            or not _sha(card["origin"]["proof_sha256"])
            or not _strings(card["entry"], {"hypothesis", "conclusion", "direction"})
            or card["entry"]["direction"] != "left_inverse_cancel"
            or not _strings(card["parameters"], PARAMETERS) or card["required_laws"] != LAWS):
        raise CorpusError("invalid left-inverse method card")
    knowledge = card["knowledge"]
    if (not isinstance(knowledge, dict) or set(knowledge) != {
            "suite_id", "lean_version", "condition", "base"}
            or knowledge["suite_id"] != "metered-transfer-v1"
            or knowledge["lean_version"] != "4.24.0" or knowledge["condition"] != "baseline"
            or not _strings(knowledge["base"], {"module", "sha256"})
            or knowledge["base"]["module"] != "Base" or not _sha(knowledge["base"]["sha256"])):
        raise CorpusError("invalid method knowledge boundary")
    for field in ("obligations", "limits"):
        if (not isinstance(card[field], list) or not card[field]
                or any(not isinstance(v, str) or not v.strip() for v in card[field])):
            raise CorpusError("method obligations and limits must be explicit")
    _template(card["proof_template"], PARAMETERS)
    applications = card["applications"]
    if not isinstance(applications, dict) or set(applications) != {"d02", "d04"}:
        raise CorpusError("method v1 declares only two development applications")
    for task, action in (("d02", "retain"), ("d04", "candidate")):
        app = applications[task]
        common = {"module", "goal", "source_sha256", "action", "reason"}
        if (not isinstance(app, dict) or set(app) != (common if action == "retain" else
                common | {"bindings", "proof_wrapper"})
                or not _strings({k: app[k] for k in common}, common)
                or app["module"] != "Tasks." + task.upper() or app["goal"] != "Tasks." + task
                or app["action"] != action or not _sha(app["source_sha256"])):
            raise CorpusError("invalid declared method application")
        if action == "candidate":
            _template(app["proof_wrapper"], {"core"})
            if app["proof_wrapper"].count("    {core}") != 1:
                raise CorpusError("method wrapper requires one indented core")
            _bindings(app["bindings"])
    return card


def load_card(path):
    return validate_card(read_object(Path(path)))


def _bindings(bindings):
    if not _strings(bindings, PARAMETERS):
        raise CorpusError("method requires exactly four string bindings")
    for name in ("group", "equality", "result"):
        if not re.fullmatch(IDENTIFIER, bindings[name]) or bindings[name] in KEYWORDS:
            raise CorpusError("method bindings require safe local identifiers")
    # shortcut: one variable or one unary application; widen only for an observed application.
    element = bindings["element"]
    if (not re.fullmatch(rf"(?:{IDENTIFIER}|\({IDENTIFIER} {IDENTIFIER}\))", element)
            or any(word in KEYWORDS for word in re.findall(IDENTIFIER, element))):
        raise CorpusError("method element requires a single-line variable or unary application")
    if bindings["result"] in {bindings["group"], bindings["equality"],
                              *re.findall(IDENTIFIER, element)}:
        raise CorpusError("method result must be a distinct local identifier")


def render(card, bindings):
    validate_card(card)
    _bindings(bindings)
    return card["proof_template"].format_map(bindings)


def _fingerprint(value):
    return (isinstance(value, dict) and _sha(value.get("request_sha256"))
            and value["request_sha256"] == digest(canonical({
                k: v for k, v in value.items() if k != "request_sha256"})))


def generate(request, card):
    """Retain on any applicability mismatch; the host still performs Lean checking."""
    validate_card(card)
    if not isinstance(request, dict) or not _sha(request.get("request_sha256")):
        raise CorpusError("method request needs a search request fingerprint")
    task_id = request.get("task_id")
    evidence = {"schema_version": 1, "method_id": card["id"],
        "card_sha256": digest(canonical(card)), "source_proof_sha256": card["origin"]["proof_sha256"],
        "task_id": task_id, "matched": False, "reason": None, "bindings": None,
        "template_sha256": digest(card["proof_template"].encode()), "proof_sha256": None}

    def retain(reason):
        evidence["reason"] = reason
        return {"action": "retain", "request_sha256": request["request_sha256"],
                "reason": reason}, evidence

    inner = request.get("inner_request")
    if not _fingerprint(request) or not _fingerprint(inner):
        return retain("request_fingerprint_mismatch")
    task = inner.get("task")
    if not isinstance(task_id, str) or not isinstance(task, dict) or task.get("id") != task_id:
        return retain("task_identity_mismatch")
    if task_id not in card["applications"]:
        return retain("task_not_declared")
    app, knowledge = card["applications"][task_id], card["knowledge"]
    if any(inner.get(k) != knowledge[k] for k in ("condition", "suite_id", "lean_version")):
        return retain("knowledge_boundary_mismatch")
    contract = inner.get("contract")
    if (task.get("module") != app["module"] or task.get("goal") != app["goal"]
            or task.get("split") != "development" or not isinstance(contract, dict)
            or contract.get("expected_goal") != app["goal"]
            or contract.get("target") != "Submission.solve"):
        return retain("goal_identity_mismatch")
    expected = [(knowledge["base"]["module"], knowledge["base"]["sha256"]),
                (app["module"], app["source_sha256"])]
    sources = inner.get("sources")
    if not isinstance(sources, list) or len(sources) != len(expected):
        return retain("source_identity_mismatch")
    for source, (module, fingerprint) in zip(sources, expected):
        if (not _strings(source, {"module", "sha256", "content"}) or source["module"] != module
                or source["sha256"] != fingerprint or digest(source["content"].encode()) != fingerprint):
            return retain("source_identity_mismatch")
    if app["action"] == "retain":
        return retain(app["reason"])
    core = render(card, app["bindings"])
    proof = app["proof_wrapper"].format_map({"core": core.replace("\n", "\n    ")})
    evidence.update(matched=True, reason=app["reason"], bindings=dict(app["bindings"]),
                    proof_sha256=digest(proof_source(inner, proof).encode()))
    return {"action": "candidate", "request_sha256": request["request_sha256"],
            "proof": proof, "bridge": app["reason"]}, evidence
