"""Offline preparation of one constructive closure-transport method."""
from pathlib import Path
import platform
import shutil
import zlib

from . import migration as mig
from .corpus import CorpusError
from .lean_sandbox import lean_sandbox, probe
from .theory import digest, read_object
from .transfer import commit_for
from scripts.measure_compressed_reference import measure_sources

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "experiments/closure_transport_v1"
TASKS = [f"c0{i}" for i in range(1, 7)]
TOOLS = ("maam/closure_transport.py", "scripts/check_closure_transport.py", "maam/migration.py",
         "maam/theory.py", "maam/corpus.py", "maam/PackageCheck.lean", "maam/lean_sandbox.py",
         "maam/transfer.py", "scripts/measure_compressed_reference.py", "scripts/check_theory_package.py")


def _tools():
    return {name: digest((REPO / name).read_bytes()) for name in TOOLS}


def _references(path):
    data = read_object(path)
    refs = data.get("tasks")
    if not isinstance(refs, dict) or set(refs) != set(TASKS):
        raise CorpusError("references must match all six tasks exactly")
    for item in refs.values():
        if (not isinstance(item, dict) or set(item) != {"proof", "bridge"}
                or any(not isinstance(value, str) or not value.strip() for value in item.values())):
            raise CorpusError("each author reference requires proof and bridge strings")
    return refs


def prepare(output, *, fixture=FIXTURE, verify_commit=True):
    fixture = Path(fixture).resolve()
    frozen = mig.load_suite(fixture / "suite.json")
    if (frozen["manifest"]["suite_id"] != "closure-transport-v1"
            or [task["id"] for task in frozen["manifest"]["tasks"]] != TASKS
            or any(task["split"] != "development" for task in frozen["manifest"]["tasks"])
            or frozen["manifest"]["budget"]["max_attempts_per_task"] != 1):
        raise CorpusError("expected the fixed six-task offline closure development suite")
    _references(fixture / "reference_proofs.json")
    guide = (fixture / "guide.txt").read_text()
    if not guide.strip() or len(guide.split()) > 400 or "/home/" in guide:
        raise CorpusError("guide must be at most 400 words without private paths")
    for name in ("Base.lean", "Candidate.lean"):
        if (fixture / name).read_bytes() != (REPO / "experiments/hom_kernel" / name).read_bytes():
            raise CorpusError("existing group/Hom source must be reused byte-identically")
    files = [p for p in fixture.rglob("*") if p.is_file() and p.suffix not in {".olean", ".ilean"}]
    commit = commit_for(files + [REPO / name for name in TOOLS]) if verify_commit else None
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "inputs").mkdir()
    for name in ("guide.txt", "reference_proofs.json"):
        shutil.copyfile(fixture / name, root / "inputs" / name)
    mig.start_session(fixture / "suite.json", root / "math", condition="treatment",
                      solver_id="closure-author-reference", mode="supplied_reference")
    plan = {"schema_version": 1, "source_commit": commit, "tool_sha256": _tools(),
            "math_fingerprints": frozen["fingerprints"],
            "input_sha256": {p.name: digest(p.read_bytes()) for p in (root / "inputs").iterdir()}}
    mig.save_new(root / "plan.json", mig.seal(plan))
    return report(root)


def _load(output):
    root = Path(output).resolve()
    plan = mig.unseal(root / "plan.json")
    if plan["tool_sha256"] != _tools():
        raise CorpusError("offline closure controller changed")
    for name, sha in plan["input_sha256"].items():
        if digest((root / "inputs" / name).read_bytes()) != sha:
            raise CorpusError("offline reference or guide changed")
    _, session, frozen = mig.load_session(root / "math")
    if (frozen["fingerprints"] != plan["math_fingerprints"] or session["condition"] != "treatment"
            or session["solver"] != {"id": "closure-author-reference", "mode": "supplied_reference"}):
        raise CorpusError("offline mathematical context changed")
    return root, plan, frozen, _references(root / "inputs/reference_proofs.json")


def task_input(output, task_id, *, include_guide=False):
    """Preview a future solver input; author references and labels stay outside."""
    root, _, _, _ = _load(output)
    if task_id not in TASKS:
        raise CorpusError("unknown closure task")
    request = mig.task_request(root / "math", task_id)
    result = {"lean_version": request["lean_version"],
              "sources": [{"module": row["module"], "content": row["content"]} for row in request["sources"]],
              "target": {"declaration": "Submission.solve", "type": request["task"]["goal"]},
              "output_contract": {"proof": "complete Proof.lean source"}}
    if include_guide:
        result["guide"] = (root / "inputs/guide.txt").read_text()
    return result


def report(output):
    root, plan, frozen, refs = _load(output)
    state = mig.session_report(root / "math")
    proofs, rows = {}, []
    for task in state["tasks"]:
        task_id = task["id"]
        request = mig.task_request(root / "math", task_id)
        expected = {"task_id": task_id, "request_sha256": request["request_sha256"], **refs[task_id]}
        for attempt in task["attempts"]:
            folder = root / "math" / attempt["artifact"]
            if (folder / "submission.json").exists() and read_object(folder / "submission.json") != expected:
                raise CorpusError("submitted proof differs from the author reference")
            if (folder / "Proof.lean").exists() and (folder / "Proof.lean").read_text() != mig.proof_source(request, refs[task_id]["proof"]):
                raise CorpusError("complete proof source differs from the author reference")
        selected = task["selected"]
        row = {"task_id": task_id, "status": task["status"], "attempts": task["attempts"],
               "source_tokens": selected["proof_source_tokens"] if selected else None,
               "named_transport_dependency": None}
        if selected:
            folder = root / "math/attempts" / task_id / f"{selected['attempt']:03d}"
            proofs[f"proofs/{task_id}.lean"] = (folder / "Proof.lean").read_bytes()
            row["proof_sha256"] = digest(proofs[f"proofs/{task_id}.lean"])
            row["named_transport_dependency"] = "Theory.preimage_mul_closed" in selected["target"]["direct_proof_dependencies"]
            row["map_contract_verified"] = task_id in TASKS[:4]
        rows.append(row)
    attempts = [attempt for task in rows for attempt in task["attempts"]]
    interrupted = any(attempt["status"] == "incomplete" for attempt in attempts)
    failed = any(attempt["status"] != "verified" for attempt in attempts)
    complete = len(proofs) == 6
    status = "interrupted" if interrupted else "stopped" if failed else "completed" if complete else "in_progress"
    compression = None
    if complete:
        guide = (root / "inputs/guide.txt").read_bytes()
        package = {name + ".lean": frozen["blobs"][name] for name in frozen["package"]["modules"]}
        all_sources = {name + ".lean": source for name, source in frozen["blobs"].items()}
        compression = {"proofs_only": measure_sources(proofs),
                       "package_guide_and_proofs": measure_sources({**package, **proofs, "guide.txt": guide}),
                       "joint_local_sources": measure_sources({**all_sources, **proofs, "guide.txt": guide}),
                       "comparison": "none; no old-tool baseline or matched model search was run"}
    sandbox = mig.unseal(root / "sandbox.json") if (root / "sandbox.json").exists() else None
    return {"schema_version": 1, "status": status, "source_commit": plan["source_commit"],
            "new_model_calls": 0, "generation_usage": None, "generation_mode": "author_supplied_reference",
            "counts": {"tasks": 6, "verified": len(proofs), "attempts": len(attempts)},
            "tasks": rows, "sandbox": sandbox, "math_fingerprints": plan["math_fingerprints"],
            "tool_sha256": plan["tool_sha256"], "input_sha256": plan["input_sha256"],
            "runtime": {"python": platform.python_version(), "zlib": zlib.ZLIB_RUNTIME_VERSION},
            "compression": compression,
            "preparation_cost": {"author_time_seconds": None,
                "common_checker_source": measure_sources({name: (REPO / name).read_bytes() for name in TOOLS})},
            "evidence": {"author_map_choices": True, "ai_constructed_maps": False,
                "automatic_extraction": False, "guide_effect_measured": False,
                "new_theory_effect_established": False, "held_out_transfer": False,
                "training_eligible": False,
                "scope": "Group specialization, explicit existential map/compatibility/preservation obligations; source references supply the constructions. No executable witness extraction or mathematical novelty claim."}}


def run(output):
    root = Path(output).resolve()
    with mig.session_lock(root):
        state = report(root)
        if state["status"] != "in_progress":
            raise CorpusError("no offline reference slot available; interrupted attempts are preserved")
        _, _, frozen, refs = _load(root)
        if not (root / "sandbox.json").exists():
            mig.save_new(root / "sandbox.json", mig.seal(probe()))
        with lean_sandbox(check=False) as lean:
            for task in state["tasks"]:
                if task["attempts"]:
                    continue
                task_id = task["task_id"]
                request = mig.task_request(root / "math", task_id)
                source = mig.proof_source(request, refs[task_id]["proof"])
                if len(source.encode()) > frozen["manifest"]["budget"]["max_proof_bytes"]:
                    raise CorpusError("complete author proof exceeds the source-size budget")
                result = mig.submit_attempt(root / "math", {"task_id": task_id,
                    "request_sha256": request["request_sha256"], **refs[task_id]}, lean=str(lean))
                if result["status"] != "verified":
                    break
    return report(root)
