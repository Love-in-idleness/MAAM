"""Offline author controls for an explicit, complete-source theorem contract."""
from pathlib import Path
import json
import re
import shutil

from . import migration as mig
from .corpus import CorpusError
from .lean_sandbox import lean_sandbox, probe
from .theory import digest, read_object
from .transfer import CONTROLLERS, commit_for

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "experiments/theorem_contract_v2"
TASKS = [f"c0{i}" for i in range(1, 7)]
CASE_IDS = TASKS + ["c01_" + name for name in (
    "fully_qualified_theorem", "def", "wrong_goal", "new_axiom", "extra_import", "proof_term")]
MAX_SOURCE_BYTES = 32768
TOOLS = tuple(dict.fromkeys(("maam/theorem_contract.py", "scripts/check_theorem_contract.py",
    "maam/lean_sandbox.py", "maam/corpus.py", *(str(p.relative_to(REPO)) for p in CONTROLLERS))))
INSTRUCTIONS = (
    "Solve the single Lean 4.24.0 goal using the supplied sources. Return only a JSON object "
    "with exactly one string field, proof, containing the complete Proof.lean source. "
    "Import precisely the listed modules. Declare Submission.solve using Lean's theorem "
    "command with precisely the supplied target type. A namespace Submission block containing "
    "theorem solve is accepted, as is theorem Submission.solve. A def declaration is rejected "
    "by this project's declaration contract even when it is a valid Lean proof. Replace the "
    "<proof> placeholder in the declaration template with a complete proof. Do not return only "
    "a proof term. Do not change frozen sources, imports, goals or axioms. No sorry, admit, "
    "new axioms, external tools, file access or networking. Any compliant proof is accepted."
)
JSON_SCHEMA = {"type": "object", "properties": {"proof": {"type": "string"}},
               "required": ["proof"], "additionalProperties": False}
NEGATIVES = {
    "c01_def": ("audit", "target is not a theorem"),
    "c01_wrong_goal": ("audit", "target proposition changed"),
    "c01_new_axiom": ("audit", "forbidden axiom"),
    "c01_extra_import": ("audit", "forbidden imported module"),
    "c01_proof_term": ("compile:Proof", ""),
}


def _hashes():
    return {name: digest((REPO / name).read_bytes()) for name in TOOLS}


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _protocol(path):
    data = read_object(path)
    if (set(data) != {"schema_version", "experiment_id", "fixture", "suite_sha256",
                     "references_sha256", "guide_sha256", "task_ids", "case_ids"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["experiment_id"] != "theorem-contract-v2"
            or data["fixture"] != "../closure_transport_v1"
            or data["task_ids"] != TASKS or data["case_ids"] != CASE_IDS
            or any(not isinstance(data[k], str) or not re.fullmatch(r"[0-9a-f]{64}", data[k])
                   for k in ("suite_sha256", "references_sha256", "guide_sha256"))):
        raise CorpusError("expected the fixed offline theorem-contract-v2 protocol")
    return data


def prepare(output, *, verify_commit=True):
    protocol = _protocol(FIXTURE / "protocol.json")
    fixture = (FIXTURE / protocol["fixture"]).resolve()
    for name, field in (("suite.json", "suite_sha256"),
                        ("reference_proofs.json", "references_sha256"), ("guide.txt", "guide_sha256")):
        if digest((fixture / name).read_bytes()) != protocol[field]:
            raise CorpusError("frozen author material changed")
    refs = read_object(fixture / "reference_proofs.json")["tasks"]
    if (set(refs) != set(TASKS) or any(set(row) != {"proof", "bridge"} or
            any(not isinstance(v, str) or not v.strip() for v in row.values()) for row in refs.values())):
        raise CorpusError("expected six complete author references")
    frozen = mig.load_suite(fixture / "suite.json")
    if [t["id"] for t in frozen["manifest"]["tasks"]] != TASKS:
        raise CorpusError("author suite differs from the contract protocol")
    files = [p for folder in (FIXTURE, fixture) for p in folder.rglob("*")
             if p.is_file() and p.suffix not in {".olean", ".ilean"}]
    commit = commit_for(files + [REPO / name for name in TOOLS]) if verify_commit else None
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "inputs").mkdir()
    shutil.copyfile(FIXTURE / "protocol.json", root / "inputs/protocol.json")
    for name in ("guide.txt", "reference_proofs.json"):
        shutil.copyfile(fixture / name, root / "inputs" / name)
    mig.start_session(fixture / "suite.json", root / "math", condition="treatment",
                      solver_id="theorem-contract-author-controls", mode="supplied_reference")
    plan = {"schema_version": 1, "protocol": protocol, "source_commit": commit,
            "provenance": "offline_author_controls", "tool_sha256": _hashes(),
            "math_fingerprints": frozen["fingerprints"],
            "input_sha256": {p.name: digest(p.read_bytes()) for p in (root / "inputs").iterdir()}}
    mig.save_new(root / "plan.json", mig.seal(plan))
    (root / "reservations").mkdir()
    (root / "attempts").mkdir()
    return report(root)


def _load(output):
    root = Path(output).resolve()
    plan = mig.unseal(root / "plan.json")
    if plan["tool_sha256"] != _hashes():
        raise CorpusError("contract tools changed")
    if (set(plan["input_sha256"]) != {"protocol.json", "reference_proofs.json", "guide.txt"}
            or any(digest((root / "inputs" / name).read_bytes()) != sha
                   for name, sha in plan["input_sha256"].items())
            or _protocol(root / "inputs/protocol.json") != plan["protocol"]):
        raise CorpusError("contract input snapshot changed")
    _, session, frozen = mig.load_session(root / "math")
    if (plan["provenance"] != "offline_author_controls" or session["condition"] != "treatment"
            or session["solver"] != {"id": "theorem-contract-author-controls", "mode": "supplied_reference"}
            or frozen["fingerprints"] != plan["math_fingerprints"]):
        raise CorpusError("contract mathematical context changed")
    for path, field in ((root / "math/snapshot/suite.json", "suite_sha256"),
                       (root / "inputs/reference_proofs.json", "references_sha256"),
                       (root / "inputs/guide.txt", "guide_sha256")):
        if digest(path.read_bytes()) != plan["protocol"][field]:
            raise CorpusError("contract material differs from the frozen protocol")
    return root, plan, frozen


def task_input(output, task_id, *, include_guide=False):
    root, _, _ = _load(output)
    if task_id not in TASKS:
        raise CorpusError("unknown contract task")
    request = mig.task_request(root / "math", task_id)
    imports = [s["module"] for s in request["sources"]]
    template = ("\n".join("import " + m for m in imports) + "\n\nnamespace Submission\n"
                + f"theorem solve : {request['task']['goal']} := <proof>\nend Submission\n")
    result = {"instructions": INSTRUCTIONS, "lean_version": request["lean_version"],
              "sources": [{"module": s["module"], "content": s["content"]} for s in request["sources"]],
              "target": {"declaration": "Submission.solve", "kind": "theorem", "type": request["task"]["goal"]},
              "output_contract": {"proof": "complete Proof.lean source", "imports": imports,
                                  "json_schema": json.loads(_json_bytes(JSON_SCHEMA)), "declaration_template": template}}
    if include_guide:
        result["guide"] = (root / "inputs/guide.txt").read_text()
    return result


def _source(root, case_id):
    task = case_id if case_id in TASKS else "c01"
    request = mig.task_request(root / "math", task)
    term = read_object(root / "inputs/reference_proofs.json")["tasks"][task]["proof"]
    source = mig.proof_source(request, term)
    if case_id == "c01_fully_qualified_theorem":
        source = (source.split("namespace Submission\n", 1)[0]
                  + f"theorem Submission.solve : {request['task']['goal']} :=\n" + term + "\n")
    elif case_id == "c01_def":
        source = source.replace("theorem solve :", "def solve :", 1)
    elif case_id == "c01_wrong_goal":
        source = source.split("namespace Submission\n", 1)[0] + (
            "namespace Submission\ntheorem solve : True := by exact True.intro\nend Submission\n")
    elif case_id == "c01_new_axiom":
        source += "\naxiom contract_extra : False\n"
    elif case_id == "c01_extra_import":
        source = "import Lean\n" + source
    elif case_id == "c01_proof_term":
        source = term
    return task, request, source


def _pending(root, case_id):
    task, request, source = _source(root, case_id)
    payload, response = task_input(root, task), {"proof": source}
    pending = {"case_id": case_id, "task_id": task, "request_sha256": request["request_sha256"],
               "payload_sha256": digest(_json_bytes(payload)),
               "response_sha256": digest(_json_bytes(response)), "source_sha256": digest(source.encode()),
               "sandbox_sha256": digest((root / "sandbox.json").read_bytes())}
    return pending, payload, response, request


def report(output):
    root, plan, _ = _load(output)
    files = {p.name for p in (root / "reservations").iterdir()}
    names = set(CASE_IDS[:len(files)])
    if files != {name + ".json" for name in names} or {p.name for p in (root / "attempts").iterdir()} - names:
        raise CorpusError("contract reservation sequence or artifacts changed")
    if names and not (root / "sandbox.json").exists():
        raise CorpusError("reserved contract controls require sandbox evidence")
    cases, stopped = [], False
    for case_id in CASE_IDS:
        row = {"case_id": case_id, "task_id": case_id if case_id in TASKS else "c01",
               "expected": "rejected" if case_id in NEGATIVES else "verified",
               "status": "pending", "matched": None, "verification_failure": None,
               "artifact": "attempts/" + case_id}
        if case_id in names:
            if stopped:
                raise CorpusError("contract controls continued after a stopping condition")
            pending, payload, response, _ = _pending(root, case_id)
            if mig.unseal(root / "reservations" / (case_id + ".json")) != pending:
                raise CorpusError("contract reservation changed")
            folder = root / "attempts" / case_id
            if not (folder / "result.json").exists():
                row["status"], stopped = "incomplete", True
            else:
                if (digest((folder / "payload.json").read_bytes()) != pending["payload_sha256"]
                        or digest((folder / "response.json").read_bytes()) != pending["response_sha256"]
                        or read_object(folder / "payload.json") != payload or read_object(folder / "response.json") != response
                        or (folder / "Proof.lean").read_bytes() != response["proof"].encode()):
                    raise CorpusError("contract payload, response or source changed")
                verification = read_object(folder / "verification.json")
                result = mig.unseal(folder / "result.json")
                if result != {"reservation_sha256": digest(mig.canonical(pending)),
                              "verification_sha256": digest((folder / "verification.json").read_bytes())}:
                    raise CorpusError("contract verification binding changed")
                for command in verification["trace"]:
                    for log in command["logs"].values():
                        if Path(log["path"]).name != log["path"] or digest((folder / log["path"]).read_bytes()) != log["sha256"]:
                            raise CorpusError("contract verification log changed")
                failure = verification.get("failure") or {}
                matched = verification["status"] == row["expected"]
                if case_id in NEGATIVES:
                    stage, diagnostic = NEGATIVES[case_id]
                    matched = matched and failure.get("stage") == stage and diagnostic in failure.get("message", "")
                row.update(status=verification["status"], matched=matched, verification_failure=verification.get("failure"),
                           proof_compiled=any(c["stage"] == "compile:Proof" and c["returncode"] == 0
                                              for c in verification["trace"]))
                stopped = not matched
        cases.append(row)
    completed = sum(c["matched"] is not None for c in cases)
    status = ("interrupted" if any(c["status"] == "incomplete" for c in cases) else
              "failed" if any(c["matched"] is False for c in cases) else
              "completed" if completed == len(CASE_IDS) else "in_progress" if names else "prepared")
    return {"schema_version": 1, "status": status, "source_commit": plan["source_commit"],
            "provenance": "offline_author_controls", "new_model_calls": 0, "generation_usage": None,
            "counts": {"slots": len(CASE_IDS), "completed": completed,
                       "verified": sum(c["status"] == "verified" for c in cases),
                       "rejected": sum(c["status"] == "rejected" for c in cases)}, "cases": cases,
            "sandbox": mig.unseal(root / "sandbox.json") if (root / "sandbox.json").exists() else None,
            "scope": "Offline declaration-contract controls; no model search, guide-effect measurement or new live allowance."}


def run(output):
    root = Path(output).resolve()
    with mig.session_lock(root):
        state = report(root)
        if state["status"] not in {"prepared", "in_progress"}:
            raise CorpusError("no contract slot available; interrupted controls cannot retry")
        _, _, frozen = _load(root)
        limit = min(MAX_SOURCE_BYTES, frozen["manifest"]["budget"]["max_proof_bytes"])
        if any(len(_source(root, case_id)[2].encode()) > limit for case_id in CASE_IDS):
            raise CorpusError("complete source exceeds the source-byte budget")
        if not (root / "sandbox.json").exists():
            mig.save_new(root / "sandbox.json", mig.seal(probe()))
        with lean_sandbox(check=False) as lean:
            for row in state["cases"]:
                if row["status"] != "pending":
                    continue
                case_id = row["case_id"]
                pending, payload, response, request = _pending(root, case_id)
                mig.save_new(root / "reservations" / (case_id + ".json"), mig.seal(pending))
                folder = root / "attempts" / case_id
                folder.mkdir()
                mig.save_new(folder / "payload.json", payload)
                mig.save_new(folder / "response.json", response)
                candidate = read_object(folder / "response.json")
                if (set(candidate) != {"proof"} or not isinstance(candidate["proof"], str)
                        or not candidate["proof"].strip() or candidate != response
                        or digest((folder / "response.json").read_bytes()) != pending["response_sha256"]):
                    raise CorpusError("expected one complete-source proof string")
                source = candidate["proof"]
                if len(source.encode()) > limit:
                    raise CorpusError("complete source exceeds the source-byte budget")
                (folder / "Proof.lean").write_bytes(source.encode())
                verification = mig.verify_attempt(frozen, request, source, folder, lean=str(lean))
                mig.save_new(folder / "verification.json", verification)
                mig.save_new(folder / "result.json", mig.seal({"reservation_sha256": digest(mig.canonical(pending)),
                    "verification_sha256": digest((folder / "verification.json").read_bytes())}))
                if report(root)["status"] == "failed":
                    break
    return report(root)
