"""Measure conditional replacement of fixed, already proved Lean goals."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .corpus import CorpusError
from .theory import CHECKER, CORE_AXIOMS, _RunFailure, _command, digest, inside, names, read_object


def _suite(path):
    path = Path(path).resolve()
    suite = read_object(path)
    if type(suite.get("schema_version")) is not int or suite["schema_version"] != 1:
        raise CorpusError("expected conjecture compression suite schema_version 1")
    if not re.fullmatch(r"[0-9a-f]{40}", suite.get("mathlib_revision", "")):
        raise CorpusError("suite must pin a Mathlib revision")
    if not re.fullmatch(r"\d+\.\d+\.\d+", suite.get("lean_version", "")):
        raise CorpusError("suite must pin a Lean version")
    names([suite.get("suite_id")], "suite_id")
    names(suite.get("allowed_library_prefixes"), "allowed_library_prefixes")

    def entries(field):
        values = suite.get(field)
        if not isinstance(values, dict) or not values:
            raise CorpusError(f"{field} must be a nonempty object")
        names(list(values), field)
        if any(not isinstance(v, dict) for v in values.values()):
            raise CorpusError(f"{field} entries must be objects")
        return values

    targets, candidates = entries("targets"), entries("candidates")
    names([task.get("goal") for task in targets.values()], "target goals")
    sources = {"common": suite.get("common")}
    for key, task in targets.items():
        sources[f"original/{key}"] = task.get("original")
        names(task.get("withheld_declarations"), f"{key}.withheld_declarations")
    for key, candidate in candidates.items():
        sources[f"assumption/{key}"] = candidate.get("assumption")
        alternatives = candidate.get("alternatives")
        if not isinstance(alternatives, dict) or not alternatives.keys() <= targets.keys():
            raise CorpusError(f"{key}: alternatives must reference fixed targets")
        for task, filename in alternatives.items():
            sources[f"alternative/{key}/{task}"] = filename

    contents = {}
    for key, filename in sources.items():
        source = inside(path.parent, filename, key)
        if source.suffix != ".lean":
            raise CorpusError(f"{key}: expected a Lean source file")
        contents[key] = source.read_bytes()
    hashes = {key: digest(value) for key, value in contents.items()}
    if hashes != suite.get("source_sha256"):
        raise CorpusError("frozen source fingerprints do not match suite")
    return suite, contents, {"suite_sha256": digest(path.read_bytes()), "source_sha256": hashes,
                             "auditor_sha256": digest(CHECKER.read_bytes()),
                             "evaluator_sha256": digest(Path(__file__).read_bytes())}


def _toolchain(suite, mathlib, lean, lake):
    lean, lake = shutil.which(lean), shutil.which(lake)
    if lean is None or lake is None:
        raise CorpusError("Lean and Lake must be installed")
    mathlib = Path(mathlib).resolve()
    env = os.environ.copy()
    for key in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT"):
        env.pop(key, None)
    env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v" + suite["lean_version"]

    def checked(command):
        result = subprocess.run(command, cwd=mathlib, env=env, text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise CorpusError((result.stderr or result.stdout).strip())
        return result.stdout.strip()

    revision = checked(["git", "rev-parse", "HEAD"])
    if revision != suite["mathlib_revision"]:
        raise CorpusError(f"expected Mathlib revision {suite['mathlib_revision']}, got {revision}")
    if checked(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise CorpusError("Mathlib has modified tracked sources")
    version = checked([lean, "--version"])
    if not re.search(r"\bversion " + re.escape(suite["lean_version"]) + r"\b", version):
        raise CorpusError(f"unexpected Lean toolchain: {version}")
    libpath = checked([lake, "env", "printenv", "LEAN_PATH"])
    paths = [str((mathlib / part).resolve()) for part in libpath.split(os.pathsep) if part]
    if not paths:
        raise CorpusError("Lake did not supply a Mathlib library path")
    return lean, env, paths, version


def _audit(suite, context, sources, task, *, conditional, trace, stage, deadline):
    lean, base_env, libraries, _ = context
    with tempfile.TemporaryDirectory(prefix="maam-conjecture-") as temp:
        root = Path(temp)
        env = {**base_env, "LEAN_PATH": os.pathsep.join([temp, *libraries])}
        expected = ("Bench.A → " if conditional else "") + task["goal"]
        probe = ["import Lean", "import Proof", f"def Bench.Expected : Prop := {expected}",
                 "open Lean Elab Command in", "run_cmd do", "  let env ← getEnv"]
        for name in task["withheld_declarations"]:
            probe.extend([f"  if (env.find? `{name}).isSome then",
                          f'    throwError "withheld declaration present: {name}"'])
        if conditional:
            probe.extend([
                "  let some assumptionModule := env.getModuleIdxFor? `Bench.A",
                '    | throwError "missing conjecture statement"',
                "  let declarations := env.constants.toList.filterMap fun (name, _) =>",
                "    if env.getModuleIdxFor? name == some assumptionModule then some name else none",
                "  unless declarations == [`Bench.A] do",
                '    throwError "assumption module must contain only the conjecture statement"',
                "  let some (.thmInfo info) := env.find? `Bench.proof",
                '    | throwError "missing conditional theorem"',
                "  let .lam _ _ body _ := info.value.consumeMData",
                '    | throwError "the conditional witness must introduce the assumption at its outer binder"',
                "  unless (body.consumeMData).hasLooseBVar 0 do",
                '    throwError "conditional witness does not use the conjecture hypothesis"',
            ])
        modules = {**sources, "Audit": ("\n".join(probe) + "\n").encode()}
        resources = {"per_command_timeout_seconds": 30}
        for module, content in modules.items():
            (root / f"{module}.lean").write_bytes(content)
            _command([lean, "-DmaxHeartbeats=1000000", "-o", f"{module}.olean", f"{module}.lean"],
                     root, env, resources, deadline, f"{stage}:compile:{module}", trace)
        charged = [name for name in ("Assumption", "Proof") if name in sources]
        (root / "audit-input.json").write_text(json.dumps({
            "moduleName": "Audit",
            "allowedModules": [*suite["allowed_library_prefixes"], *modules],
            "auditedModules": list(sources),
            "allowedAxioms": CORE_AXIOMS,
            "packageModules": ["Assumption"] if conditional else [],
            "requiredDeclarations": ["Bench.A"] if conditional else [],
            "targets": [{"name": "Bench.proof", "expected": "Bench.Expected"}],
            "sources": [{"moduleName": m, "path": f"{m}.lean"} for m in charged],
        }), encoding="utf-8")
        _command([lean, "--run", str(CHECKER), "audit-input.json", "audit-output.json"],
                 root, env, resources, deadline, f"{stage}:audit", trace)
        audit = read_object(root / "audit-output.json")
        target, = audit["targets"]
        if target["goal_preserved"] is not True or target["name"] != "Bench.proof":
            raise CorpusError("Lean audit did not confirm the fixed goal")
        costs = {r["module"]: r["source_tokens"] for r in audit["sources"]}
        if costs.keys() != set(charged) or any(type(v) is not int or v <= 0 for v in costs.values()):
            raise CorpusError("Lean audit omitted valid costs")
        library_imports = sorted(set(audit["imported_modules"]) - modules.keys())
        return {"proof_module_tokens": costs["Proof"], "assumption_module_tokens": costs.get("Assumption"),
                "signature_tokens": target["source"]["signature_tokens"],
                "proof_body_tokens": target["source"]["body_tokens"], "proof_expr_nodes": target["proof_expr_nodes"],
                "proof_dependencies": target["direct_proof_dependencies"], "axioms_used": audit["axioms_used"],
                "library_imports_count": len(library_imports),
                "library_imports_sha256": digest("\n".join(library_imports).encode())}


def _check_upstream(mathlib, task, original):
    upstream = task.get("upstream")
    if not isinstance(upstream, dict):
        raise CorpusError("baseline requires a pinned upstream source range")
    path = inside(Path(mathlib).resolve(), upstream.get("path"), "upstream.path")
    first, last = upstream.get("first_line"), upstream.get("last_line")
    name, = names([upstream.get("declaration")], "upstream.declaration")
    lines = path.read_bytes().splitlines(keepends=True)
    if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(lines):
        raise CorpusError("invalid upstream theorem source range")
    declaration = b"".join(lines[first - 1:last])
    prefix = f"theorem {name.rsplit('.', 1)[-1]} ".encode()
    if not declaration.startswith(prefix) or declaration.replace(prefix, b"theorem _root_.Bench.proof ", 1) not in original:
        raise CorpusError(f"baseline does not reproduce upstream declaration: {name}")
    return {"declaration": name, "path": upstream["path"], "lines": [first, last],
            "upstream_declaration_sha256": digest(declaration)}


def _portfolio(before, alternatives, declaration_cost):
    tasks = {}
    for key, original in before.items():
        replacement = alternatives[key]
        if replacement["status"] != "verified":
            tasks[key] = {**replacement, "original": original}
            continue
        proof = replacement["proof"]
        savings = original["proof_module_tokens"] - proof["proof_module_tokens"]
        tasks[key] = {**replacement, "original": original, "observed_module_tokens_saved": savings,
                      "observed_proof_body_tokens_saved": original["proof_body_tokens"] - proof["proof_body_tokens"],
                      "retain": "alternative" if savings > 0 else "original"}
    complete = all(row["status"] == "verified" for row in tasks.values())
    observed = sum(max(0, row["observed_module_tokens_saved"]) for row in tasks.values()
                   if row["status"] == "verified")
    return {
        "status": "measured" if complete else "unmeasured",
        "tasks": tasks,
        "observed_verified_retained_module_tokens_saved": observed,
        "assumption_statement_module_tokens": declaration_cost,
        "conditional_net_tokens_saved": (observed - declaration_cost) if complete else None,
        "proof_cost_of_conjecture": None,
        "net_tokens_saved_after_proving_conjecture": None,
    }


def measure_compression(path, mathlib, *, lean="lean", lake="lake"):
    suite, blobs, fingerprints = _suite(path)
    trace = []
    report = {"schema_version": 1, "suite_id": suite["suite_id"], "mathlib_revision": suite["mathlib_revision"],
              "fingerprints": fingerprints, "trace": trace, "candidates": {}, "ranking": [],
              "status": "unmeasured",
              "score_kind": "fixed_target_panel_conditional_net_parsed_source_tokens",
              "proof_body_cost": "Lean source syntax leaves after :=; whole source modules determine ranking"}
    try:
        context = _toolchain(suite, mathlib, lean, lake)
        report["lean_version"] = context[-1]
        deadline = time.monotonic() + 180
        baseline = {}
        for key, task in suite["targets"].items():
            original = blobs[f"original/{key}"]
            upstream = _check_upstream(mathlib, task, original)
            baseline[key] = _audit(suite, context, {"Goal": blobs["common"], "Proof": original},
                                   task, conditional=False, trace=trace, stage=f"original:{key}", deadline=deadline)
            baseline[key]["upstream"] = upstream
    except (_RunFailure, subprocess.TimeoutExpired) as exc:
        report["failure"] = _failure(exc)
        return report

    for key in suite["candidates"]:
        alternatives, costs = {}, set()
        for task_key, task in suite["targets"].items():
            source = blobs.get(f"alternative/{key}/{task_key}")
            if source is None:
                alternatives[task_key] = {"status": "missing_witness"}
                continue
            try:
                proof = _audit(suite, context, {"Goal": blobs["common"], "Assumption": blobs[f"assumption/{key}"],
                                               "Proof": source}, task, conditional=True, trace=trace,
                               stage=f"alternative:{key}:{task_key}", deadline=deadline)
                if proof["library_imports_sha256"] != baseline[task_key]["library_imports_sha256"]:
                    raise CorpusError("replacement changed the imported library")
                costs.add(proof["assumption_module_tokens"])
                alternatives[task_key] = {"status": "verified", "proof": proof}
            except (_RunFailure, CorpusError) as exc:
                status = "inconclusive" if isinstance(exc, _RunFailure) and exc.kind == "budget_exhausted" else "rejected_witness"
                alternatives[task_key] = {"status": status, "failure": _failure(exc)}
        if len(costs) > 1:
            raise CorpusError("assumption module has inconsistent measured costs")
        report["candidates"][key] = _portfolio(baseline, alternatives, next(iter(costs), None))
    if all(row["status"] == "measured" for row in report["candidates"].values()):
        rows = sorted(((-r["conditional_net_tokens_saved"], k) for k, r in report["candidates"].items()))
        previous_score = None
        for i, (inverse_score, key) in enumerate(rows, 1):
            if inverse_score != previous_score:
                rank = i
            report["ranking"].append({"rank": rank, "candidate": key, "conditional_net_tokens_saved": -inverse_score})
            previous_score = inverse_score
        report["status"] = "measured"
    return report


def _failure(exc):
    if isinstance(exc, _RunFailure):
        return {"kind": exc.kind, "stage": exc.stage, "message": exc.message}
    return {"message": str(exc)}
