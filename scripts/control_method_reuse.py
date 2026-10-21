#!/usr/bin/env python3
"""Apply one explicit existing-tool method on two development goals, offline."""
import argparse
import json
from pathlib import Path
import platform
import sys
import zlib

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from maam import CorpusError, baseline_search as search, method_card
from maam.baseline import inventory_baseline
from maam.generation import lean_environment
from maam.migration import canonical, save_new, seal, session_lock, task_request, unseal
from maam.theory import digest, read_object
from scripts.measure_compressed_reference import measure_sources
from scripts.measure_model_portfolio import model_inventory
from scripts.measure_retained_portfolio import _witness

CARD = REPO / "experiments/left_inverse_method_v1/method.json"
TASKS = ["d02", "d04"]
POLICY = {"schema_version": 1, "evidence_mode": "supplied_local", "max_sweeps": 1,
          "stable_sweeps": 1, "methods": [{"name": "left_inverse_cancel_v1",
          "instructions": "Instantiate the declared left-inverse cancellation card; keep unsupported "
                          "right-sided goals and all non-shorter original proofs."}]}
TOOLS = ("scripts/control_method_reuse.py", "maam/method_card.py",
         "scripts/measure_model_portfolio.py", "scripts/measure_retained_portfolio.py",
         "scripts/measure_compressed_reference.py")


def _tools():
    return {**{p: digest((REPO / p).read_bytes()) for p in TOOLS}, "method.json": digest(CARD.read_bytes())}


def _inputs(model_root, card):
    observed, origin = model_inventory(model_root)
    source = next((row["selected"] for row in origin["tasks"] if row["task_id"] == card["origin"]["task_id"]), None)
    if (source is None or source["proof_sha256"] != card["origin"]["proof_sha256"]
            or digest((Path(source["artifact"]) / "Proof.lean").read_bytes()) != source["proof_sha256"]):
        raise CorpusError("method origin differs from its bound model certificate")
    inventory = inventory_baseline([row["root"] for row in origin["sessions"]], TASKS)
    if inventory["missing_tasks"]:
        raise CorpusError("method pilot requires a verified incumbent on both development goals")
    return observed, inventory


def prepare(model_root, output):
    card = method_card.load_card(CARD)
    observed, inventory = _inputs(model_root, card)
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    save_new(root / "inventory.json", inventory)
    (root / "method.json").write_bytes(CARD.read_bytes())
    search.prepare_search(root / "inventory.json", POLICY, root / "search")
    (root / "generated").mkdir()
    (root / "setup").mkdir()
    files = {"method.json": CARD.read_bytes(), "renderer.py": (REPO / "maam/method_card.py").read_bytes(),
             "controller.py": Path(__file__).read_bytes()}
    for name, content in files.items():
        (root / "setup" / name).write_bytes(content)
    plan = {"schema_version": 1, "model_root": str(Path(model_root).resolve()),
            "source_model_report_sha256": digest(canonical(observed)), "tool_sha256": _tools(),
            "inventory_sha256": digest(canonical(inventory)),
            "search_plan_sha256": digest((root / "search/plan.json").read_bytes()),
            "setup_files": {name: digest(content) for name, content in files.items()}}
    save_new(root / "plan.json", seal(plan))
    return report(root)


def _proofs(inventory):
    sources = {}
    for row in inventory["tasks"]:
        selected = row["selected"]
        source_session = inventory["sessions"][selected["session_index"]]["root"]
        _, source, _ = _witness(selected["artifact"], task_request(source_session, row["task_id"]), selected, {}, [])
        sources[row["task_id"] + "/Proof"] = source
    return sources


def report(output):
    root = Path(output).resolve()
    plan = unseal(root / "plan.json")
    card = method_card.load_card(root / "method.json")
    observed, initial_inventory = _inputs(plan["model_root"], card)
    if (plan["tool_sha256"] != _tools()
            or digest((root / "method.json").read_bytes()) != plan["tool_sha256"]["method.json"]
            or digest(canonical(observed)) != plan["source_model_report_sha256"]
            or digest(canonical(initial_inventory)) != plan["inventory_sha256"]
            or canonical(read_object(root / "inventory.json")) != canonical(initial_inventory)
            or digest((root / "search/plan.json").read_bytes()) != plan["search_plan_sha256"]):
        raise CorpusError("method code, origin, card or initial inventory changed")
    files = {name: (root / "setup" / name).read_bytes() for name in plan["setup_files"]}
    expected_files = {"method.json": CARD.read_bytes(), "renderer.py": (REPO / "maam/method_card.py").read_bytes(),
                      "controller.py": Path(__file__).read_bytes()}
    if (files != expected_files or {name: digest(content) for name, content in files.items()} != plan["setup_files"]
            or {p.name for p in (root / "setup").iterdir()} != set(files)):
        raise CorpusError("method setup artifacts changed")
    state = search.report(root / "search")
    child_plan = unseal(root / "search/plan.json")
    if (child_plan["policy"] != POLICY or [r["task_id"] for r in child_plan["initial"]] != TASKS
            or child_plan["inventory_sha256"] != digest((root / "inventory.json").read_bytes())):
        raise CorpusError("method search scope differs from its initial inventory")
    issued = search._issued(root / "search", child_plan)
    names = sorted(p.name for p in (root / "generated").iterdir())
    if (len(names) > len(TASKS) or names != [f"{i:04d}.json" for i in range(1, len(names) + 1)]
            or not len(issued) <= len(names) <= len(issued) + 1):
        raise CorpusError("method generation slots differ from search reservations")
    counts = dict(scans=len(names), candidates=0, retained=0, verified=0, rejected=0, incomplete=0)
    initial = {row["task_id"]: row for row in child_plan["initial"]}
    for index, name in enumerate(names):
        request = search._request(root / "search", child_plan, child_plan["schedule"][index], initial)
        response, evidence = method_card.generate(request, card)
        if unseal(root / "generated" / name) != {"request": request, "response": response, "evidence": evidence}:
            raise CorpusError("method instantiation differs from its deterministic replay")
        counts["candidates"] += response["action"] == "candidate"
        if index < len(issued):
            if (issued[index]["request_sha256"] != request["request_sha256"]
                    or issued[index]["response_sha256"] != digest(canonical(response))):
                raise CorpusError("search submission is not the generated method instance")
            status = state["attempts"][index]["status"]
            counts[status if status in ("retained", "verified", "rejected") else "incomplete"] += 1
        else:
            counts["incomplete"] += 1
    stopped = counts["incomplete"] > 0 or state["status"] == "interrupted_or_inconclusive"
    complete = len(issued) == len(TASKS) and not stopped
    sessions = [row["root"] for row in initial_inventory["sessions"]]
    sessions += [str(root / "search" / row["path"]) for row in child_plan["sessions"]]
    selected_inventory = inventory_baseline(sessions, TASKS)
    chosen = [(r["task_id"], r["selected"]["proof_sha256"], r["selected"]["proof_source_tokens"])
              for r in selected_inventory["tasks"]]
    if chosen != [(r["task_id"], r["proof_sha256"], r["proof_source_tokens"]) for r in state["tasks"]]:
        raise CorpusError("method search and retained portfolio select different certificates")
    before, after = _proofs(initial_inventory), _proofs(selected_inventory)
    setup = {"method/" + name: content for name, content in files.items()}
    applications = state["attempts"]
    return {"schema_version": 1, "status": "stopped" if stopped else "completed" if complete else "in_progress",
            "method_id": card["id"], "origin": card["origin"], "plan_sha256": digest(canonical(plan)),
            "runtime": {"python_version": platform.python_version(),
                        "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION},
            "source_model_usage": observed["generation_usage"], "new_model_calls": 0, "generation_usage": None,
            "counts": counts, "applications": applications,
            "initial_source_tokens": state["initial_source_tokens"],
            "selected_source_tokens": state["selected_source_tokens"], "new_lean_package_source_tokens": 0,
            "proof_documents": {"baseline": measure_sources(before), "selected": measure_sources(after)},
            "method_setup": {"card_only": measure_sources({"method/method.json": files["method.json"]}),
                             "executable": measure_sources(setup)},
            "combined_documents": {"selected_plus_card": measure_sources({**after, "method/method.json": files["method.json"]}),
                                   "selected_plus_executable": measure_sources({**after, **setup})},
            "selected_inventory_sha256": digest(canonical(selected_inventory)),
            "search_report": state,
            "evidence": {"extraction": "author_extracted_from_existing_model_certificate",
                         "ai_card_usability_measured": False, "automatic_method_discovery": False,
                         "fair_model_comparison": False, "broad_baseline_prepared": False,
                         "causal_theory_attribution": False, "held_out_evaluation": False,
                         "scope": "Two development goals, one explicit source template and author-supplied bindings. "
                                  "Local helpers are charged in Proof; the whole card, renderer and controller "
                                  "are measured separately once against shared repository infrastructure, "
                                  "not as a dependency-closed standalone archive. Earlier development checks "
                                  "are outside these two fixed application slots. No weighted cognitive score. "
                                  "No new Lean theory module; inherited generation usage remains unknown."}}


def execute_next(output):
    root = Path(output).resolve()
    with session_lock(root):
        if report(root)["status"] != "in_progress":
            raise CorpusError("no method slot available; incomplete work cannot be retried")
        request = search.next_request(root / "search")
        response, evidence = method_card.generate(request, method_card.load_card(root / "method.json"))
        save_new(root / "generated" / f"{request['slot']:04d}.json", seal({
            "request": request, "response": response, "evidence": evidence}))
        with lean_environment():
            search.submit(root / "search", response)
    return report(root)


def check_report(path, root):
    if canonical(read_object(Path(path))) != canonical(report(root)):
        raise CorpusError("method report differs from current evidence or measurements")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "next", "status"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--model-root", type=Path)
    outputs = parser.add_mutually_exclusive_group()
    outputs.add_argument("--output", type=Path)
    outputs.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    if args.action == "prepare" and args.model_root is None:
        parser.error("prepare requires --model-root")
    if args.check and args.action != "status":
        parser.error("--check requires status")
    try:
        value = (prepare(args.model_root, args.root) if args.action == "prepare" else
                 execute_next(args.root) if args.action == "next" else report(args.root))
        if args.check:
            check_report(args.check, args.root)
        if args.output:
            save_new(args.output, value)
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (CorpusError, OSError, ValueError, KeyError) as exc:
        print("method pilot stopped: " + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
