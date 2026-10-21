#!/usr/bin/env python3
"""Bind a confirmed baseline to archived optional proofs and measure the portfolio."""

import argparse
import json
from pathlib import Path
import platform
import sys
import zlib

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from maam import CorpusError
from maam.migration import canonical, load_session, proof_source, save_new, session_report, task_request, unseal
from maam.reuse import retained_portfolio
from maam.theory import CORE_AXIOMS, digest, read_object
from scripts import control_baseline_stability as stability
from scripts.measure_compressed_reference import measure_sources


def _witness(artifact, request, selected, package_sources, declarations):
    artifact = Path(artifact)
    source = (artifact / "Proof.lean").read_bytes()
    submission = read_object(artifact / "submission.json")
    result = unseal(artifact / "result.json")
    if (result["status"] != "verified" or result["request_sha256"] != request["request_sha256"]
            or result["proof_sha256"] != digest(source)
            or proof_source(request, submission["proof"]).encode("utf-8") != source):
        raise CorpusError("witness does not match its original request and source")
    audit = result["audit"]
    target = selected["target"]
    if (target.get("name") != "Submission.solve" or target.get("expected") != request["task"]["goal"]
            or target.get("goal_preserved") is not True or audit["targets"] != [target]
            or audit["lean_version"] != request["lean_version"] or audit["module"] != "Proof"
            or audit["package_declarations"] != declarations
            or not set(audit["axioms_used"]) <= set(CORE_AXIOMS)):
        raise CorpusError("witness audit differs from the original goal, package or axiom policy")
    charged = {**package_sources, "Proof": source}
    rows = audit["sources"]
    if len(rows) != len(charged) or {row["module"] for row in rows} != set(charged):
        raise CorpusError("witness audit must charge the complete package and proof exactly once")
    for row in rows:
        if (row["source_utf8_bytes"] != len(charged[row["module"]])
                or type(row["source_tokens"]) is not int or row["source_tokens"] < 0):
            raise CorpusError("witness source byte or token counts are inconsistent")
    tokens = {row["module"]: row["source_tokens"] for row in rows}
    package_tokens = sum(value for module, value in tokens.items() if module != "Proof")
    if (tokens["Proof"] != selected["proof_source_tokens"]
            or package_tokens != selected.get("package_source_tokens", 0)):
        raise CorpusError("witness source ledger differs from its selected certificate")
    return {
        "proof_source_tokens": tokens["Proof"], "proof_sha256": digest(source),
        "result_sha256": digest((artifact / "result.json").read_bytes()),
        "artifact": str(artifact), "request_sha256": request["request_sha256"],
        "import_context": [{"module": row["module"], "sha256": row["sha256"]} for row in request["sources"]],
        "direct_proof_dependencies": target.get("direct_proof_dependencies", []),
    }, source, package_tokens


def build_report(baseline_root, treatment_root):
    baseline_root, treatment_root = Path(baseline_root).resolve(), Path(treatment_root).resolve()
    confirmed, inventory = stability._replay(baseline_root)
    if (confirmed["status"] != "declared_method_preparation_complete"
            or confirmed["declared_method_preparation_complete"] is not True):
        raise CorpusError("baseline must complete its declared method confirmation first")
    tasks = [row["task_id"] for row in inventory["tasks"]]
    root, session, frozen = load_session(treatment_root)
    if session["condition"] != "treatment":
        raise CorpusError("alternative proofs must come from a treatment session")
    manifest, package, blobs = frozen["manifest"], frozen["package"], frozen["blobs"]
    by_id = {task["id"]: task for task in manifest["tasks"]}
    if not 1 <= len(tasks) <= 2 or any(t not in by_id or by_id[t]["split"] != "development" for t in tasks):
        raise CorpusError("portfolio requires one or two matching development goals")
    common = list(dict.fromkeys(manifest["base"]["modules"] + [by_id[t]["module"] for t in tasks]))
    knowledge = {"lean_version": manifest["lean_version"], "base": manifest["base"],
                 "tasks": [by_id[t] for t in tasks],
                 "source_sha256": {module: digest(blobs[module]) for module in common}}
    if canonical(knowledge) != canonical(inventory["knowledge"]):
        raise CorpusError("baseline and treatment goals, shared knowledge or toolchain differ")
    observed = session_report(root)
    choices = {row["id"]: row["selected"] for row in observed["tasks"]}
    package_sources = {module: blobs[module] for module in package["modules"]}
    originals, alternatives, original_sources, alternative_sources, package_costs = {}, {}, {}, {}, set()
    for row in inventory["tasks"]:
        task, selected = row["task_id"], row["selected"]
        if selected is None:
            raise CorpusError("baseline is missing a verified original certificate")
        source_session = inventory["sessions"][selected["session_index"]]["root"]
        request = task_request(source_session, task)
        original, source, _ = _witness(selected["artifact"], request, selected, {}, [])
        if original["proof_sha256"] != selected["proof_sha256"]:
            raise CorpusError("original witness differs from the confirmed certificate")
        originals[task], original_sources[task] = original, source
        alternative = choices[task]
        if alternative is None:
            alternatives[task] = None
            continue
        request = task_request(root, task)
        artifact = root / "attempts" / task / f"{alternative['attempt']:03d}"
        witness, source, cost = _witness(artifact, request, alternative, package_sources, package["declarations"])
        alternatives[task], alternative_sources[task] = witness, source
        package_costs.add(cost)
    if len(package_costs) != 1:
        raise CorpusError("at least one verified alternative with a consistent complete package cost is required")
    portfolio = retained_portfolio(originals, alternatives, package_costs.pop())
    selected_sources = {
        row["task_id"]: (alternative_sources if row["selected_origin"] == "alternative" else original_sources)[row["task_id"]]
        for row in portfolio["tasks"]
    }
    scopes = {}
    for scope, shared in (("nonshared_payload", {}), ("standalone_sources", {m: blobs[m] for m in common})):
        before = {**shared, **{task + "/Proof": source for task, source in original_sources.items()}}
        after = {**shared, **package_sources, **{task + "/Proof": source for task, source in selected_sources.items()}}
        conditions = {"baseline": measure_sources(before), "retained_treatment": measure_sources(after)}
        saved = conditions["baseline"]["compressed"]["zlib-9"]["bytes"] - conditions["retained_treatment"]["compressed"]["zlib-9"]["bytes"]
        scopes[scope] = {"conditions": conditions, "net_zlib_bytes_saved": saved,
                         "outcome": "improved" if saved > 0 else "tied" if saved == 0 else "higher_cost"}
    return {
        "schema_version": 1, "status": "measured_retained_reference_portfolio",
        "inputs": {"baseline_root": str(baseline_root), "treatment_session": str(root),
                   "baseline_confirmation_sha256": digest(canonical(confirmed)),
                   "baseline_inventory_sha256": digest(canonical(inventory)),
                   "treatment_report_sha256": digest(canonical(observed)),
                   "treatment_fingerprints": frozen["fingerprints"],
                   "tool_sha256": {name: digest((REPO / name).read_bytes()) for name in (
                       "scripts/measure_retained_portfolio.py", "scripts/control_baseline_stability.py",
                       "scripts/measure_compressed_reference.py", "maam/reuse.py", "maam/migration.py")}},
        "protocol": {"selection": "verified and strictly shorter full-module source tokens; preserve original imports",
                     "encoding": "reuse reference-compression-v1 canonical JSON and codecs; exact source bytes",
                     "proof_labels": "task_id/Proof labels independent documents, not jointly importable Lean modules",
                     "package_modules_charged_once": package["modules"], "shared_modules": common,
                     "nonshared_payload": "shared base and task declarations excluded before encoding; not C(K+X)-C(K)",
                     "standalone_sources": "joint local source documents; external Init/toolchain unchanged",
                     "excluded": "reports, logs, historical failures, method documentation and toolchain binaries"},
        "historical_treatment": {"solver": session["solver"], "budget": manifest["budget"],
                                 "missing_alternatives": [task for task in tasks if alternatives[task] is None]},
        "runtime": {"python_version": platform.python_version(), "zlib_compile_version": zlib.ZLIB_VERSION,
                    "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION, "bzip2_runtime_version": None},
        "retained_portfolio": portfolio, "scopes": scopes,
        "evidence": {"baseline_declared_method_scope_complete": True, "broad_baseline_prepared": False,
                     "fresh_lean_verification": False, "new_model_calls": 0, "historical_generation_usage": "unknown",
                     "fair_model_comparison": False, "held_out_evaluation": False,
                     "method_card_usability_measured": False, "causal_theory_attribution": False,
                     "scope": "Offline composition of archived same-goal certificates, not new discovery or matched-budget search."},
    }


def check_report(path, baseline_root, treatment_root):
    if canonical(read_object(Path(path))) != canonical(build_report(baseline_root, treatment_root)):
        raise CorpusError("retained portfolio report differs from current evidence, runtime or measurements")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--treatment-session", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_report(args.check, args.baseline_root, args.treatment_session)
            result = {"status": "reproduced", "report": str(args.check)}
        else:
            report = build_report(args.baseline_root, args.treatment_session)
            save_new(args.output, report)
            result = {"status": report["status"], "output": str(args.output),
                      "source_ledger": report["retained_portfolio"]["original_goal_source_ledger"]}
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__, "message": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
