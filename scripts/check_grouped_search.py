#!/usr/bin/env python3
"""Replay a complete grouped preparation/control/treatment calibration in Lean."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam import CorpusError
from maam import grouped_search as gs
from maam import grouped_methods
from maam.migration import save_new, session_report
from maam.theory import digest

PLAN = ROOT / "experiments/grouped_search_v1/plan.json"


def check(workdir, lean):
    executable = shutil.which(lean)
    if executable is None:
        raise CorpusError("Lean is unavailable")
    # The frozen migration verifier launches Lean subprocesses when loading modules.
    os.environ["PATH"] = str(Path(executable).resolve().parent) + os.pathsep + os.environ.get("PATH", "")
    parent = Path(workdir).resolve()
    parent.mkdir(parents=True, exist_ok=False)
    workdir = parent / "supplied"
    gs.start(PLAN, workdir, solver_id="supplied-grouped-calibration", lean=executable)
    checks = []
    try:
        gs.request(workdir, "treatment")
    except CorpusError:
        checks.append("treatment request blocked before preparation freeze")
    else:
        raise AssertionError("candidate exposed before preparation freeze")

    def candidate(phase, helpers, one, two):
        request = gs.request(workdir, phase)
        response = {"action": "candidate", "request_sha256": request["request_sha256"],
                    "helpers": helpers, "proofs": {"one": one, "two": two},
                    "bridge": "Supplied grouped proof and shared helper calibration."}
        result = gs.submit(workdir, phase, response, lean=executable)
        return result

    helper = "have project (P Q : Prop) (h : P ∧ Q) : P := h.left"
    first = candidate("preparation", helper,
        "by\n  intro P Q hp hq\n  exact project P Q (And.intro hp hq)",
        "by\n  intro P Q R hp hq hr\n  exact project P (Q ∧ R) (And.intro hp (And.intro hq hr))")
    if first["status"] != "verified":
        raise CorpusError("shared-helper group was not verified")
    second = candidate("preparation", "",
        "by\n  intro P Q hp hq\n  exact hp",
        "by\n  intro P Q R hp hq hr\n  exact hp")
    if second["status"] != "verified":
        raise CorpusError("direct group was not verified")
    gs.freeze(workdir)
    control = gs.request(workdir, "control")
    treatment = gs.request(workdir, "treatment")
    if (control["prepared_sha256"] != treatment["prepared_sha256"]
            or any(s["module"] == "Candidate" for s in control["inner_request"]["sources"])):
        raise AssertionError("condition-specific request contract failed")
    checks.append("both arms inherit identical prepared proofs; candidate source is treatment-only")
    rejected = candidate("control", "",
        "by\n  intro P Q hp hq\n  exact hq",
        "by\n  intro P Q R hp hq hr\n  exact hp")
    if rejected["status"] != "rejected":
        raise AssertionError("wrong component was accepted")
    checks.append("a wrong original component rejects the entire group")
    repaired = candidate("control", "",
        "by\n  intro P Q hp hq\n  exact hp -- trailing comment",
        "by\n  intro P Q R hp hq hr\n  exact hp")
    if repaired["status"] != "verified":
        raise CorpusError("control repair was not verified")
    migrated = candidate("treatment", "",
        "by\n  intro P Q hp hq\n  exact Calibration.keep P Q hp hq",
        "by\n  intro P Q R hp hq hr\n  exact Calibration.keep P (Q ∧ R) hp (And.intro hq hr)")
    if migrated["status"] != "verified":
        raise CorpusError("candidate group was not verified")
    current = gs.request(workdir, "treatment")
    gs.submit(workdir, "treatment", {"action": "retain", "request_sha256": current["request_sha256"],
                                    "reason": "Retain the complete prepared proof pool."})
    report = gs.report(workdir)
    if report["status"] != "grouped_schedule_complete" or report["verified_complete_routes"] != 5:
        raise AssertionError("grouped schedule or verified pool mismatch")
    for phase in gs.SESSIONS:
        for task in session_report(Path(workdir) / phase)["tasks"]:
            if task["selected"] and task["selected"]["target"]["expected"] != "GroupGoal.goal":
                raise AssertionError("original conjunction changed")
    local = parent / "local"
    gs.start(PLAN, local, solver_id="deterministic-core-v1", lean=executable)
    preparation = grouped_methods.run(local, "preparation", lean=executable)
    gs.freeze(local)
    control = grouped_methods.run(local, "control", lean=executable)
    treatment = grouped_methods.run(local, "treatment", lean=executable)
    for stage in (preparation, control, treatment):
        if [d["status"] for d in stage["decisions"]] != ["verified", "verified"]:
            raise CorpusError("a generated core-tactic group was not verified")
    checks.append("two deterministic methods generate verified groups in all three search phases")
    return {"schema_version": 1, "status": "verified_grouped_search_calibration",
            "provider_calls": 0, "supplied_reference": True, "checks": checks,
            "driver_sha256": digest(Path(__file__).read_bytes()),
            "verified_group_attempts_including_preflight": 14,
            "verified_attempts_by_run": {"supplied": 6, "local_methods": 8},
            "rejected_group_attempts": 1, "retained_decisions": 1,
            "report": report, "local_methods": {"method_sha256": preparation["method_sha256"],
                "methods": preparation["methods"], "report": treatment["report"]},
            "scope": "Supplied full-group witnesses, shared local helper, one failed component "
                "and repair, plus two deterministic core-tactic methods. No model API or isolated model search."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args(argv)
    if args.output.exists():
        print(json.dumps({"status": "error", "error": "output already exists"}))
        return 1
    try:
        result = check(args.workdir, args.lean)
    except (CorpusError, OSError, AssertionError) as exc:
        result = {"status": "failed_grouped_calibration", "error": str(exc),
                  "workdir": str(args.workdir)}
        save_new(args.output, result)
        print(json.dumps(result))
        return 2
    save_new(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
