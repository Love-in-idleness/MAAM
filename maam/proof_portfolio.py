"""Fresh verification and stable cost accounting for separate proof modules."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from .ablation import INVENTORY, validate_module
from .migration import save_new, seal
from .precompression import measure_sources
from .theory import CHECKER, CORE_AXIOMS, CorpusError, digest, read_object

ENTRY = "RefactorEntry"
SHARED = "RefactorShared"
SITES = Path(__file__).with_name("RefactorSites.lean")
METRICS = ("source_tokens", "source_utf8_bytes", "zlib_9_bytes", "bzip2_9_bytes", "expr_nodes")


def proof_module(task_id):
    return "RefactorProofs." + task_id


def theorem_name(task_id):
    return "Submission.solve_" + task_id


def module_path(root, name):
    return root.joinpath(*name.split(".")).with_suffix(".lean")


def imports(modules):
    return "".join(f"import {module}\n" for module in modules)


def compile_route(frozen, tasks, terms, artifact, *, lean, shared=None, uses_shared=(),
                  uses_candidate=(), install_candidate=False, inspect=False):
    """Build a route from controlled headers, retaining the rejected versions as well."""
    artifact = Path(artifact).resolve()
    artifact.mkdir(parents=True, exist_ok=False)
    manifest, package = frozen["manifest"], frozen["package"]
    budget = manifest["budget"]
    base = manifest["base"]["modules"]
    ids = {t["id"] for t in tasks}
    if (set(terms) != ids or not set(uses_shared) <= ids or not set(uses_candidate) <= ids
            or (uses_shared and shared is None)):
        raise CorpusError("route does not cover its fixed task and helper set")
    if not tasks:
        raise CorpusError("a route needs at least one task")
    tools = {ENTRY, SHARED, *(proof_module(i) for i in ids)}
    if tools & frozen["blobs"].keys():
        raise CorpusError("suite modules collide with generated proof or helper modules")
    selected = list(package["modules"]) if uses_candidate or install_candidate else []
    sources = {m: frozen["blobs"][m] for m in dict.fromkeys(base + [t["module"] for t in tasks] + selected)}
    if shared is not None:
        sources[SHARED] = shared.encode()
    task_modules, site_inputs = {}, []
    for task in tasks:
        tid = task["id"]
        module = proof_module(tid)
        task_modules[tid] = module
        used = list(dict.fromkeys(base + [task["module"]]))
        if tid in uses_candidate:
            used += selected
        if tid in uses_shared:
            used.append(SHARED)
        term = terms[tid]
        if len(term.encode()) > budget["max_proof_bytes"]:
            raise CorpusError("proof term exceeds the frozen byte limit")
        sources[module] = (imports(used) + "\nnamespace Submission\n"
                           + f"theorem solve_{tid} : {task['goal']} :=\n{term}\nend Submission\n").encode()
        if inspect:
            term_path = artifact / f"{tid}.term"
            term_path.write_text(term, encoding="utf-8")
            site_inputs.append({"theoremName": theorem_name(tid), "termPath": term_path.name})
    charged = selected + ([SHARED] if shared is not None else []) + list(task_modules.values())
    sources[ENTRY] = imports(sources).encode()
    for name, content in sources.items():
        path = module_path(artifact, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    identity = {"sources": {name: digest(value) for name, value in sources.items()},
                "charged": charged, "goals": {t["id"]: t["goal"] for t in tasks}}
    save_new(artifact / "pending.json", seal(identity))
    result = {"status": "incomplete", "identity": identity, "commands": []}
    executable = shutil.which(lean)
    env = dict(os.environ, ELAN_TOOLCHAIN="leanprover/lean4:v" + manifest["lean_version"],
               LEAN_PATH=str(artifact))
    deadline = time.monotonic() + budget["per_attempt_timeout_seconds"]

    def command(args, stage):
        remaining = min(deadline - time.monotonic(), budget["per_command_timeout_seconds"])
        if remaining <= 0:
            raise TimeoutError("route verification budget exhausted")
        started = time.monotonic()
        try:
            proc = subprocess.run([executable, *args], cwd=artifact, env=env, capture_output=True,
                                  timeout=remaining, check=False)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
        log_paths = {}
        for stream, value in (("stdout", stdout), ("stderr", stderr)):
            path = f"command-{len(result['commands']):02d}.{stream}"
            (artifact / path).write_bytes(value)
            log_paths[stream] = {"path": path, "sha256": digest(value)}
        result["commands"].append({"stage": stage, "returncode": code,
                                   "seconds": time.monotonic() - started, "logs": log_paths})
        if code is None:
            raise TimeoutError("Lean timed out at " + stage)
        if code != 0:
            raise CorpusError((stdout + stderr).decode(errors="replace")[-4000:])
        return stdout.decode(errors="replace")

    try:
        if executable is None:
            raise OSError(f"Lean executable unavailable: {lean}")
        version = command(["--version"], "toolchain")
        if not re.search(r"version " + re.escape(manifest["lean_version"]) + r"\b", version):
            raise OSError("Lean toolchain does not match frozen suite")
        for module in sources:
            path = module_path(artifact, module).relative_to(artifact)
            command([f"-DmaxHeartbeats={budget['max_heartbeats']}", "-o",
                     str(path.with_suffix(".olean")), str(path)], "compile:" + module)
        common = {"moduleName": ENTRY, "allowedModules": ["Init", *sources]}
        targets = [{"name": theorem_name(t["id"]), "expected": t["goal"]} for t in tasks]
        required = package["declarations"] if selected else []
        save_new(artifact / "audit-input.json", {**common, "auditedModules": list(sources),
            "allowedAxioms": CORE_AXIOMS, "packageModules": selected, "requiredDeclarations": required,
            "targets": targets, "sources": [{"moduleName": m,
                "path": str(module_path(artifact, m).relative_to(artifact))} for m in charged]})
        command(["--run", str(CHECKER), "audit-input.json", "audit.json"], "audit")
        audit = read_object(artifact / "audit.json")
        if (audit["lean_version"] != manifest["lean_version"] or audit["module"] != ENTRY
                or [{k: row[k] for k in ("name", "expected")} for row in audit["targets"]] != targets
                or not all(row["goal_preserved"] for row in audit["targets"])
                or [m["module"] for m in audit["sources"]] != charged
                or audit["package_declarations"] != required
                or not set(audit["axioms_used"]) <= set(CORE_AXIOMS)):
            raise CorpusError("formal audit differs from compiled route")
        save_new(artifact / "inventory-input.json", {**common, "chargedModules": charged})
        command(["--run", str(INVENTORY), "inventory-input.json", "inventory.json"], "inventory")
        inventory = read_object(artifact / "inventory.json")
        if (inventory["lean_version"] != manifest["lean_version"] or inventory["module"] != ENTRY
                or [m["module"] for m in inventory["modules"]] != charged):
            raise CorpusError("expression inventory differs from compiled route")
        for module in inventory["modules"]:
            validate_module(module)
        result.update(status="verified", tokens={m["module"]: m["source_tokens"] for m in audit["sources"]},
                      nodes={m["module"]: m["expr_nodes"] for m in inventory["modules"]},
                      audit_sha256=digest((artifact / "audit.json").read_bytes()),
                      inventory_sha256=digest((artifact / "inventory.json").read_bytes()))
        if inspect:
            save_new(artifact / "sites-input.json", {"entry": ENTRY, "proofs": site_inputs})
            command(["--run", str(SITES), "sites-input.json", "sites.json"], "inspect")
    except (CorpusError, OSError, TimeoutError) as exc:
        status = "rejected" if isinstance(exc, CorpusError) else "inconclusive"
        result.update(status=status, failure=str(exc))
    finally:
        save_new(artifact / "result.json", seal(result))
    if result["status"] != "verified":
        return result
    return {**result, "sources": {m: sources[m] for m in charged},
            "proof_modules": task_modules, "candidate_modules": selected,
            "uses_candidate": sorted(uses_candidate), "uses_shared": sorted(uses_shared),
            "sites": dict(zip(task_modules, json.loads((artifact / "sites.json").read_text()), strict=True))
                     if inspect else {}}


def project(route, tasks, mode="complete"):
    """Select the requested goals and charge the union of their supporting modules."""
    if route["status"] != "verified" or mode not in {"complete", "mandatory", "installed"}:
        raise CorpusError("costs require a verified route and known package mode")
    if mode == "mandatory" and not route["candidate_modules"]:
        raise CorpusError("mandatory delivery requires verification with the full candidate")
    ids = set(tasks)
    charged = {route["proof_modules"][tid] for tid in ids}
    if ids & set(route["uses_shared"]):
        charged.add(SHARED)
    if mode == "mandatory" or (mode == "complete" and ids & set(route["uses_candidate"])):
        charged.update(route["candidate_modules"])
    # Module names come from the fixed goals and actual dependencies. Route IDs are metadata.
    costs = measure_sources({m: route["sources"][m] for m in charged})
    return {**costs, "charged_modules": sorted(charged),
            "source_tokens": sum(route["tokens"][m] for m in charged),
            "expr_nodes": sum(route["nodes"][m] for m in charged)}
