"""Controlled, freshly checked comparisons of supplied Lean theory packages.

Version 1 runs reference witnesses. It does not generate proofs, call an LLM,
or infer the mathematical value of candidates with no observed applications.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .corpus import CorpusError

VERSION = 1
CORE_AXIOMS = ["propext", "Quot.sound", "Classical.choice"]
CHECKER = Path(__file__).with_name("PackageCheck.lean")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CorpusError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CorpusError(f"expected a JSON object: {path}")
    return data


def nonempty_string(value, label):
    if not isinstance(value, str) or not value:
        raise CorpusError(f"{label} must be a nonempty string")
    return value


def names(value, label):
    if not isinstance(value, list) or not value:
        raise CorpusError(f"{label} must be a nonempty list of distinct names")
    for name in value:
        if not isinstance(name, str) or not all(p.isidentifier() for p in name.split(".")):
            raise CorpusError(f"invalid name in {label}")
    if len(set(value)) != len(value):
        raise CorpusError(f"duplicate name in {label}")
    return value


def inside(root: Path, relative, label):
    nonempty_string(relative, label)
    if Path(relative).is_absolute():
        raise CorpusError(f"{label} must be relative to the experiment directory")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise CorpusError(f"{label} leaves the experiment directory")
    return path


def load_experiment(path: str | Path) -> dict:
    path = Path(path).resolve()
    data = read_object(path)
    if type(data.get("schema_version")) is not int or data["schema_version"] != VERSION:
        raise CorpusError("unsupported experiment schema_version")
    if data.get("phase") != "reference_migration":
        raise CorpusError("version 1 supports reference_migration only; no held-out search claim")
    nonempty_string(data.get("experiment_id"), "experiment_id")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data.get("lean_version", "")):
        raise CorpusError("lean_version must pin an exact version")
    base = data.get("base")
    if not isinstance(base, dict):
        raise CorpusError("base must be an object")
    nonempty_string(base.get("id"), "base.id")
    base_modules = names(base.get("modules"), "base.modules")
    # Core modules are fixed by the protocol, not expanded by candidate metadata.
    if base.get("allowed_core_prefixes") != ["Init"]:
        raise CorpusError("reference protocol permits only Init core modules")
    allowed_axioms = base.get("allowed_axioms")
    if allowed_axioms != CORE_AXIOMS:
        raise CorpusError("reference protocol pins Lean's standard core axioms; no additional axioms")
    root = path.parent
    package_path = inside(root, data.get("package"), "package")
    package = read_object(package_path)
    if type(package.get("schema_version")) is not int or package["schema_version"] != VERSION:
        raise CorpusError("unsupported package schema_version")
    nonempty_string(package.get("package_id"), "package_id")
    nonempty_string(package.get("idea"), "package.idea")
    if package.get("base_id") != base["id"]:
        raise CorpusError("candidate package belongs to a different base")
    if package.get("status") != "proved_extension" or package.get("conjectures") != []:
        raise CorpusError("reference package must be a proved extension with no usable conjectures")
    package_modules = names(package.get("modules"), "package.modules")
    names(package.get("declarations"), "package.declarations")
    conditions = data.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != {"baseline", "treatment"}:
        raise CorpusError("conditions must define baseline and treatment")
    groups = [base_modules, package_modules]
    for condition in ("baseline", "treatment"):
        cfg = conditions[condition]
        if not isinstance(cfg, dict):
            raise CorpusError(f"{condition} must be an object")
        modules = names(cfg.get("modules"), f"{condition}.modules")
        if cfg.get("entry_module") != modules[-1]:
            raise CorpusError(f"{condition} entry_module must be its last compilation module")
        groups.append(modules)
    combined = sum(groups, [])
    if len(set(combined)) != len(combined):
        raise CorpusError("base, package and proof modules must be disjoint")
    if any(n.split(".")[0] in {"Init", "Lean", "Std"} for n in combined):
        raise CorpusError("experiment modules must not shadow core modules")
    sources = data.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(combined):
        raise CorpusError("sources must list every experiment module exactly once")
    blobs = {}
    hashes = {}
    for module, descriptor in sources.items():
        if not isinstance(descriptor, dict):
            raise CorpusError(f"invalid source descriptor: {module}")
        source_path = inside(root, descriptor.get("path"), f"source {module}")
        if source_path.suffix != ".lean":
            raise CorpusError("experiment sources must be .lean files")
        content = source_path.read_bytes()
        expected = descriptor.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
            raise CorpusError(f"missing frozen SHA-256 for {module}")
        if digest(content) != expected:
            raise CorpusError(f"frozen source fingerprint mismatch: {module}")
        blobs[module] = content
        hashes[module] = expected
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise CorpusError("tasks must be nonempty")
    task_ids = []
    for task in tasks:
        if not isinstance(task, dict):
            raise CorpusError("tasks must contain objects")
        task_ids.append(nonempty_string(task.get("id"), "task.id"))
        if task.get("split") != "development":
            raise CorpusError("reference migrations are development evidence, not held-out evaluation")
        for field in ("goal", "baseline", "treatment"):
            names([task.get(field)], f"task.{field}")
    if len(set(task_ids)) != len(task_ids):
        raise CorpusError("duplicate task id")
    resources = data.get("resources")
    if not isinstance(resources, dict):
        raise CorpusError("resources must be an object")
    for field in ("per_command_timeout_seconds", "total_timeout_seconds", "max_heartbeats"):
        if type(resources.get(field)) is not int or resources[field] <= 0:
            raise CorpusError(f"{field} must be a positive integer")
    frozen = {
        "experiment_sha256": digest(path.read_bytes()),
        "package_sha256": digest(package_path.read_bytes()),
        "source_sha256": dict(sorted(hashes.items())),
        "checker_sha256": digest(CHECKER.read_bytes()),
        "evaluator_sha256": digest(Path(__file__).read_bytes()),
    }
    return {"manifest": data, "package": package, "blobs": blobs, "fingerprints": frozen}


class _RunFailure(Exception):
    def __init__(self, kind, stage, message):
        self.kind, self.stage, self.message = kind, stage, message


def _command(command, cwd, env, resources, deadline, stage, trace):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _RunFailure("budget_exhausted", stage, "total verification budget exhausted")
    timeout = min(resources["per_command_timeout_seconds"], remaining)
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise _RunFailure("budget_exhausted", stage, "verification command timed out") from exc
    trace.append({"stage": stage, "seconds": time.monotonic() - started,
                  "returncode": result.returncode})
    if result.returncode:
        raise _RunFailure("verification_failed", stage, (result.stdout + result.stderr)[-8000:])
    return result


def compare_audits(manifest: dict, audits: dict) -> dict:
    """Compare measured source costs; local proof savings are descriptive only."""
    rows = []
    for task in manifest["tasks"]:
        evidence = {}
        for condition in ("baseline", "treatment"):
            matches = [r for r in audits[condition]["targets"] if r["name"] == task[condition]]
            if len(matches) != 1 or matches[0].get("expected") != task["goal"]:
                raise CorpusError(f"audit target mismatch: {task['id']}")
            row = matches[0]
            if row.get("goal_preserved") is not True:
                raise CorpusError(f"goal was not preserved: {task['id']}")
            source = row["source"]
            if source["declaration_tokens"] != source["signature_tokens"] + source["body_tokens"] + 1:
                raise CorpusError("source split is inconsistent")
            evidence[condition] = row
        before, after = evidence["baseline"], evidence["treatment"]
        rows.append({
            "id": task["id"], "split": task["split"], "goal": task["goal"],
            **evidence,
            "local_proof_body_tokens_saved": before["source"]["body_tokens"] - after["source"]["body_tokens"],
            "local_proof_expr_nodes_saved": before["proof_expr_nodes"] - after["proof_expr_nodes"],
        })
    costs = {condition: sum(f["source_tokens"] for f in audits[condition]["sources"])
             for condition in ("baseline", "treatment")}
    saved = costs["baseline"] - costs["treatment"]
    return {
        "tasks": rows,
        "source_ledger": {
            "baseline_nonshared_tokens": costs["baseline"],
            "treatment_including_package_tokens": costs["treatment"],
            "net_tokens_saved": saved,
            "outcome": "improved" if saved > 0 else "tied" if saved == 0 else "higher_cost",
            "convention": "all parsed tokens in nonshared source modules, including package definitions and proofs once",
            "shared_base_charged": False,
        },
        "judgement": "reference_evidence_only",
        "search_performed": False,
        "held_out_evaluation": False,
        "general_value": "not determined by one supplied migration",
        "training_eligibility": "reference demonstration; not an independently measured preference",
    }


def run_experiment(path: str | Path, *, lean="lean") -> dict:
    frozen = load_experiment(path)
    manifest, package = frozen["manifest"], frozen["package"]
    executable = shutil.which(lean)
    if executable is None:
        raise CorpusError(f"{lean} is not installed; install Lean {manifest['lean_version']} first")
    tool_env = os.environ.copy()
    tool_env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v" + manifest["lean_version"]
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                 timeout=15, check=False, env=tool_env)
    except subprocess.TimeoutExpired as exc:
        raise CorpusError("Lean version check timed out") from exc
    match = re.search(r"version (\d+\.\d+\.\d+)", version.stdout)
    if version.returncode or match is None or match.group(1) != manifest["lean_version"]:
        raise CorpusError(f"experiment requires Lean {manifest['lean_version']}: {version.stdout.strip()}")
    report = {
        "schema_version": VERSION, "experiment_id": manifest["experiment_id"],
        "package_id": package["package_id"], "phase": manifest["phase"],
        "status": "pending", "fingerprints": frozen["fingerprints"],
        "lean_version": manifest["lean_version"],
        "provenance": {"code_commit": os.environ.get("GITHUB_SHA"),
                       "workflow_run_id": os.environ.get("GITHUB_RUN_ID")},
        "verification_resources": manifest["resources"],
        "protocol": {
            "proof_mode": "supplied_reference_witnesses",
            "fresh_compilation": True,
            "isolated_conditions": True,
            "allowed_core_prefixes": ["Init"],
            "allowed_axioms": CORE_AXIOMS,
            "source_signature_convention": "includes declaration keyword, name and binders; excludes := separator",
            "expr_convention": "constructor occurrences, including binder types; metadata wrappers excluded",
            "scope": "one controlled migration; not a human-interest or proof-search performance benchmark",
        },
        "trace": [], "audits": {}, "comparison": None,
    }
    resources = manifest["resources"]
    deadline = time.monotonic() + resources["total_timeout_seconds"]
    try:
        for condition in ("baseline", "treatment"):
            proof = manifest["conditions"][condition]
            modules = list(manifest["base"]["modules"])
            charged = []
            if condition == "treatment":
                modules += package["modules"]
                charged += package["modules"]
            modules += proof["modules"]
            charged += proof["modules"]
            with tempfile.TemporaryDirectory(prefix=f"maam-{condition}-") as temp:
                work = Path(temp)
                for module in modules:
                    dest = work.joinpath(*module.split(".")).with_suffix(".lean")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(frozen["blobs"][module])
                env = tool_env.copy()
                env["LEAN_PATH"] = str(work)
                for module in modules:
                    relative = Path(*module.split("."))
                    _command([executable, f"-DmaxHeartbeats={resources['max_heartbeats']}",
                              "-o", str(relative.with_suffix(".olean")), str(relative.with_suffix(".lean"))],
                             work, env, resources, deadline, f"{condition}:compile:{module}", report["trace"])
                config = {
                    "moduleName": proof["entry_module"],
                    "allowedModules": ["Init"] + modules,
                    "auditedModules": modules,
                    "allowedAxioms": CORE_AXIOMS,
                    "packageModules": package["modules"] if condition == "treatment" else [],
                    "requiredDeclarations": package["declarations"] if condition == "treatment" else [],
                    "targets": [{"name": t[condition], "expected": t["goal"]} for t in manifest["tasks"]],
                    "sources": [{"moduleName": m, "path": str(work.joinpath(*m.split(".")).with_suffix(".lean"))}
                                for m in charged],
                }
                config_path, audit_path = work / "audit-input.json", work / "audit-output.json"
                config_path.write_text(json.dumps(config), encoding="utf-8")
                _command([executable, "--run", str(CHECKER), str(config_path), str(audit_path)],
                         work, env, resources, deadline, f"{condition}:audit", report["trace"])
                audit = read_object(audit_path)
                if audit.get("lean_version") != manifest["lean_version"]:
                    raise CorpusError("auditor toolchain version mismatch")
                measured = [s.get("module") for s in audit.get("sources", [])]
                if len(measured) != len(charged) or set(measured) != set(charged):
                    raise CorpusError("auditor omitted a charged source module")
                if audit.get("package_declarations") != config["requiredDeclarations"]:
                    raise CorpusError("auditor package declarations mismatch")
                if audit.get("module") != proof["entry_module"]:
                    raise CorpusError("auditor entry module mismatch")
                if not set(audit.get("axioms_used", [])) <= set(CORE_AXIOMS):
                    raise CorpusError("unexpected axioms in audit")
                report["audits"][condition] = audit
        report["comparison"] = compare_audits(manifest, report["audits"])
        report["status"] = "verified_reference_comparison"
    except _RunFailure as exc:
        report["status"] = "inconclusive" if exc.kind == "budget_exhausted" else "rejected"
        report["failure"] = {"kind": exc.kind, "stage": exc.stage, "message": exc.message}
    return report
