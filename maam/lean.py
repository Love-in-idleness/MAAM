"""Run the bundled exporter in an existing, trusted Lean project."""

import json
import os
from pathlib import Path
import shutil
import subprocess

from .corpus import Corpus, CorpusError


def export(project: str, module: str, output: str, *, targets: list[str],
           expand_prefixes: list[str], runner="lake", timeout=600) -> dict:
    project_path = Path(project).resolve()
    output_path = Path(output).resolve()
    script = Path(__file__).with_name("Export.lean")
    if not project_path.is_dir():
        raise CorpusError(f"Lean project directory does not exist: {project_path}")
    if shutil.which(runner) is None:
        raise CorpusError(f"{runner} is not installed; install the project's Lean toolchain first")
    if not module or any(not p.isidentifier() for p in module.split(".")):
        raise CorpusError("module must be a dotted Lean module name")
    prefixes = expand_prefixes or [module.split(".")[0]]
    if any(not p or any(not x.isidentifier() for x in p.split(".")) for p in prefixes):
        raise CorpusError("expand prefixes must be dotted module names")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise CorpusError(f"output already exists: {output_path}; choose a new path")
    command = [runner] + (["env", "lean"] if runner == "lake" else [])
    command += ["--run", str(script), "--module", module, "--output", str(output_path)]
    for prefix in prefixes:
        command += ["--expand-prefix", prefix]
    for target in targets:
        command += ["--target", target]
    env = os.environ.copy()
    if runner == "lean":
        env["LEAN_PATH"] = str(project_path) + (os.pathsep + env["LEAN_PATH"] if env.get("LEAN_PATH") else "")
    try:
        result = subprocess.run(command, cwd=project_path, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise CorpusError(f"Lean export timed out after {timeout}s") from exc
    if result.returncode or not output_path.exists():
        raise CorpusError("Lean export failed:\n" + (result.stderr + result.stdout)[-6000:])
    with output_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_path,
                         capture_output=True, text=True, check=False)
    data["provenance"]["project_commit"] = git.stdout.strip() if git.returncode == 0 else None
    data["provenance"]["exporter_status"] = "export_completed_and_corpus_validated"
    Corpus(data)  # Never label malformed or cyclic export data as a successful corpus.
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return {"status": "exported", "output": str(output_path), "nodes": len(data["nodes"]),
            "scope": data["provenance"]["scope"], "length_basis": data["length_basis"]}
