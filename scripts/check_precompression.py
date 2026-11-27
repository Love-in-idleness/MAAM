#!/usr/bin/env python3
"""Fresh Lean checks and complete source accounting for a supplied calibration."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam.corpus import CorpusError
from maam.migration import save_new
from maam.precompression import compare_study, load_study
from maam.theory import CHECKER, digest

STUDY = ROOT / "experiments/precompression_v1/study.json"


def check(workdir, lean):
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=False)
    executable = shutil.which(lean)
    if executable is None:
        raise CorpusError("Lean is unavailable")
    frozen = load_study(STUDY)
    env = os.environ.copy()
    env["LEAN_PATH"] = str(workdir)
    env["ELAN_TOOLCHAIN"] = "leanprover/lean4:v4.33.1"
    env["PATH"] = str(Path(executable).resolve().parent) + os.pathsep + env.get("PATH", "")
    trace = []

    def command(args, label):
        stdout = workdir / (label + ".stdout")
        stderr = workdir / (label + ".stderr")
        with stdout.open("xb") as out, stderr.open("xb") as err:
            proc = subprocess.run(args, cwd=workdir, env=env, stdout=out, stderr=err,
                                  timeout=120, check=False)
        trace.append({"stage": label, "returncode": proc.returncode,
                      "stdout_sha256": digest(stdout.read_bytes()),
                      "stderr_sha256": digest(stderr.read_bytes())})
        if proc.returncode:
            raise CorpusError(f"{label} failed; see retained logs in {workdir}")
        return stdout.read_text()

    version = command([executable, "--version"], "version")
    if not re.search(r"version 4\.33\.1\b", version):
        raise CorpusError("calibration requires Lean 4.33.1")
    (workdir / "PackageCheck.lean").write_bytes(CHECKER.read_bytes())
    for module, source in frozen["blobs"].items():
        (workdir / (module + ".lean")).write_bytes(source)
    for module in ("Base", "Candidate", "Historical", "Prepared", "Control", "Treatment"):
        command([executable, "-o", module + ".olean", module + ".lean"], "compile-" + module)
    audits = {}
    for module in ("Historical", "Prepared", "Control", "Treatment"):
        sources = ["Base", module]
        if module == "Treatment":
            sources.insert(1, "Candidate")
        cfg = {"moduleName": module, "allowedModules": ["Init", *sources],
               "auditedModules": sources, "allowedAxioms": [], "packageModules": sources,
               "requiredDeclarations": ["Calibration.one", "Calibration.two"],
               "targets": [{"name": "Calibration.one", "expected": "Calibration.GoalOne"},
                           {"name": "Calibration.two", "expected": "Calibration.GoalTwo"}],
               "sources": [{"moduleName": m, "path": m + ".lean"} for m in sources]}
        config = module + ".json"
        save_new(workdir / config, cfg)
        output = module + ".audit.json"
        command([executable, "--run", "PackageCheck.lean", config, output], "audit-" + module)
        audits[module] = json.loads((workdir / output).read_text())
    return {"schema_version": 1, "status": "verified_precompression_calibration",
            "lean_version": "4.33.1", "checker_sha256": digest(CHECKER.read_bytes()),
            "driver_sha256": digest(Path(__file__).read_bytes()),
            "supplied_calibration": True, "search_executed": False, "provider_calls": 0,
            "audits": audits, "measurement": compare_study(STUDY), "trace": trace,
            "scope": "Fresh supplied propositional proofs with fixed goals, no axioms and "
                "audited imports; no discovery experiment or search attribution."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lean", default="lean")
    args = parser.parse_args(argv)
    if args.output.exists():
        print(json.dumps({"status": "error", "error": "output already exists"}))
        return 1
    try:
        result = check(args.workdir, args.lean)
    except (CorpusError, OSError, subprocess.TimeoutExpired) as exc:
        result = {"status": "failed_calibration", "error": str(exc),
                  "workdir": str(args.workdir), "search_executed": False}
        save_new(args.output, result)
        print(json.dumps(result))
        return 2
    save_new(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
