#!/usr/bin/env python3
"""Compile frozen task declarations and verify only development reference proofs.

This offline check never requests a model completion or submits a reserved goal.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam import CorpusError
from maam.generation import lean_environment
from maam.migration import load_suite, save_new, start_session, submit_attempt, task_request
from maam.theory import read_object

SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"
ORIGIN = ROOT / "experiments/hom_kernel_evolution"


def check_assets(suite=SUITE):
    frozen = load_suite(suite)
    folder = Path(suite).resolve().parent
    for target, original in (("Base.lean", "Base.lean"), ("Candidate.lean", "Candidate.lean"),
                             ("Extension.lean", "Extension.lean"),
                             ("package.json", "package-v2.json"),
                             ("lean-toolchain", "lean-toolchain")):
        if (folder / target).read_bytes() != (ORIGIN / original).read_bytes():
            raise CorpusError("transfer suite must retain byte-identical frozen v2 assets")
    tasks = frozen["manifest"]["tasks"]
    development = [t for t in tasks if t["split"] == "development"]
    reserved = [t for t in tasks if t["split"] == "reserved"]
    references = read_object(folder / "reference_proofs.json")["tasks"]
    if (len(development) != 4 or len(reserved) != 4
            or len({t["family"] for t in development}) != 2
            or len({t["family"] for t in reserved}) != 2
            or set(references) != {t["id"] for t in development}):
        raise CorpusError("expected four development references and four reserved declarations")
    for value in references.values():
        if set(value) != {"baseline", "treatment"}:
            raise CorpusError("each development task needs both reference conditions")
    for task in reserved:
        text = frozen["blobs"][task["module"]].decode()
        if (text.count("def ") != 1 or "theorem " in text or "lemma " in text
                or ":= by" in text or "sorry" in text or "axiom " in text):
            raise CorpusError("reserved modules must contain only one goal declaration")
    return frozen, references


def compile_declarations(frozen, lean):
    """Typecheck Prop definitions without constructing a term of any task goal."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="maam-attempt-") as name:
        work = Path(name)
        with lean_environment():
            env = os.environ.copy()
            env["LEAN_PATH"] = str(work)
            for module, blob in frozen["blobs"].items():
                relative = Path(*module.split("."))
                source = work / relative.with_suffix(".lean")
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(blob)
                result = subprocess.run(
                    [str(lean), "-DmaxHeartbeats=200000", "-o",
                     str(relative.with_suffix(".olean")), str(relative.with_suffix(".lean"))],
                    cwd=work, env=env, capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise CorpusError(f"declaration compilation failed for {module}: "
                                      + result.stdout + result.stderr)
                rows.append({"module": module, "status": "declaration_compiled"})
    return rows


def check(output, *, lean=ROOT / "scripts/lean_sandbox.py"):
    frozen, references = check_assets()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    declarations = compile_declarations(frozen, lean)
    results = []
    for condition in ("baseline", "treatment"):
        session = output / condition
        start_session(SUITE, session, condition=condition,
                      solver_id="author-development-reference-not-a-model", mode="supplied_reference")
        for task in frozen["manifest"]["tasks"]:
            if task["split"] != "development":
                continue
            request = task_request(session, task["id"])
            submission = {"task_id": task["id"], "request_sha256": request["request_sha256"],
                          **references[task["id"]][condition]}
            with lean_environment():
                result = submit_attempt(session, submission, lean=str(lean))
            results.append({"task_id": task["id"], "condition": condition,
                            "status": result["status"], "failure": result.get("failure")})
    summary = {"status": "passed" if all(r["status"] == "verified" for r in results) else "failed",
               "declarations": declarations, "development_reference_attempts": results,
               "reserved_solver_attempts": 0,
               "generation_usage": "not measured; author references, no provider calls",
               "scope": "declaration typechecks and development verifier smoke only",
               "fingerprints": frozen["fingerprints"]}
    save_new(output / "task-smoke-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lean", type=Path, default=ROOT / "scripts/lean_sandbox.py")
    args = parser.parse_args()
    result = check(args.output, lean=args.lean.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
