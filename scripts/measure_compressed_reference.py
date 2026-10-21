#!/usr/bin/env python3
"""Measure complete source packages from the frozen M1 reference, offline."""

import argparse
import bz2
import json
from pathlib import Path
import platform
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam import CorpusError
from maam import migration
from maam.theory import compare_audits, digest, load_experiment, read_object
from scripts.check_theory_package import check_reference

# Pin trusted archive bytes; a self-consistent replacement audit is not evidence.
ARCHIVED_REFERENCE_SHA256 = "bb21755c52a4353097bcb0db40e4a5dd97624de3ca835b8893fae33e7f9de860"
ARCHIVED_RECEIPT_SHA256 = "98485684ec5404af589e21b86bdcb766ebd52055b8e51b3f2f58355ea803e5ef"


def measure_sources(sources):
    payload = migration.canonical({name: source.decode("utf-8") for name, source in sources.items()})
    compressed = {}
    for name, compress, decompress in (
        ("zlib-9", lambda value: zlib.compress(value, level=9, wbits=15), zlib.decompress),
        ("bzip2-9", lambda value: bz2.compress(value, compresslevel=9), bz2.decompress),
    ):
        encoded = compress(payload)
        if decompress(encoded) != payload:
            raise CorpusError(f"{name} failed the byte-exact round trip")
        compressed[name] = {"bytes": len(encoded), "sha256": digest(encoded)}
    return {
        "modules": sorted(sources),
        "source_utf8_bytes": sum(len(source) for source in sources.values()),
        "serialized_utf8_bytes": len(payload),
        "payload_sha256": digest(payload),
        "compressed": compressed,
        "roundtrip_verified": True,
    }


def build_report(root=ROOT):
    root = Path(root)
    reference_path = root / "results/theory-package-reference.json"
    receipt_path = root / "results/theory-package-validation.json"
    archives = []
    for path, expected in (
        (reference_path, ARCHIVED_REFERENCE_SHA256),
        (receipt_path, ARCHIVED_RECEIPT_SHA256),
    ):
        content = path.read_bytes()
        if digest(content) != expected:
            raise CorpusError(f"archived evidence fingerprint mismatch: {path.name}")
        archives.append(json.loads(content.decode("utf-8")))

    frozen = load_experiment(root / "experiments/hom_kernel/experiment.json")
    reference, receipt = archives
    check_reference(reference)
    if reference["fingerprints"] != frozen["fingerprints"]:
        raise CorpusError("archived reference fingerprints differ from the frozen experiment")
    if reference["comparison"] != compare_audits(frozen["manifest"], reference["audits"]):
        raise CorpusError("archived reference accounting is inconsistent")
    if (receipt["status"] != "verified" or receipt["workflow_conclusion"] != "success"
            or receipt["implementation_commit"] != reference["provenance"]["code_commit"]
            or str(receipt["workflow_run_id"]) != reference["provenance"]["workflow_run_id"]):
        raise CorpusError("archived reference provenance differs from its receipt")

    manifest, package, blobs = frozen["manifest"], frozen["package"], frozen["blobs"]
    charged = {}
    for condition in ("baseline", "treatment"):
        modules = list(manifest["conditions"][condition]["modules"])
        if condition == "treatment":
            modules += package["modules"]
        recorded = reference["audits"][condition]["sources"]
        if len(recorded) != len(modules) or {row["module"] for row in recorded} != set(modules):
            raise CorpusError(f"archived charged modules differ: {condition}")
        if any(row["source_utf8_bytes"] != len(blobs[row["module"]]) for row in recorded):
            raise CorpusError(f"archived source byte counts differ: {condition}")
        charged[condition] = modules

    scopes = {}
    for scope, common in (("nonshared_payload", []), ("standalone_sources", manifest["base"]["modules"])):
        conditions = {
            condition: measure_sources({module: blobs[module] for module in common + charged[condition]})
            for condition in ("baseline", "treatment")
        }
        saved = (conditions["baseline"]["compressed"]["zlib-9"]["bytes"]
                 - conditions["treatment"]["compressed"]["zlib-9"]["bytes"])
        scopes[scope] = {
            "conditions": conditions,
            "net_zlib_bytes_saved": saved,
            "outcome": "improved" if saved > 0 else "tied" if saved == 0 else "higher_cost",
        }

    return {
        "schema_version": 1,
        "status": "measured_archived_reference",
        "experiment_id": manifest["experiment_id"],
        "package_id": package["package_id"],
        "protocol": {
            "id": "reference-compression-v1",
            "serialization": "UTF-8 canonical JSON object: sorted module name to exact source text",
            "source_normalization": "none; preserve names, imports, comments and whitespace",
            "primary_metric": "absolute zlib level-9, wbits-15 bytes of the jointly serialized sources",
            "diagnostic_metric": "absolute bzip2 level-9 bytes of the same payload",
            "package_charged": "every candidate module and proof module exactly once",
            "shared_base_modules": manifest["base"]["modules"],
            "nonshared_payload": "shared base excluded before serialization; not C(K+X)-C(K)",
            "standalone_sources": "shared base and charged sources serialized jointly; Init/toolchain external",
            "excluded": "reports, logs, history, method documentation and toolchain binaries",
        },
        "inputs": {
            "frozen_fingerprints": frozen["fingerprints"],
            "archived_reference_sha256": ARCHIVED_REFERENCE_SHA256,
            "archived_receipt_sha256": ARCHIVED_RECEIPT_SHA256,
            "measurement_script_sha256": digest(Path(__file__).read_bytes()),
            "serializer_module_sha256": digest(Path(migration.__file__).read_bytes()),
        },
        "runtime": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "zlib_compile_version": zlib.ZLIB_VERSION,
            "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
            "bzip2_runtime_version": None,
        },
        "evidence": {
            "kind": "offline measurement bound to trusted committed Lean evidence",
            "fresh_lean_verification": False,
            "new_model_calls": 0,
            "historical_generation_usage": "unknown",
            "baseline_prepared": False,
            "held_out_evaluation": False,
            "method_transfer_evaluation": False,
            "general_mathematical_value": "unknown",
        },
        "scopes": scopes,
    }


def check_report(path, root=ROOT):
    if migration.canonical(read_object(Path(path))) != migration.canonical(build_report(root)):
        raise CorpusError("compression report differs from current inputs, runtime or measurements")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path, help="create a new report without overwriting files")
    action.add_argument("--check", type=Path, help="strict replay, including runtime and compressed bytes")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_report(args.check)
            print(json.dumps({"status": "reproduced", "report": str(args.check)}))
        else:
            report = build_report()
            migration.save_new(args.output, report)
            print(json.dumps({"status": report["status"], "output": str(args.output),
                              "net_zlib_bytes_saved": {
                                  scope: row["net_zlib_bytes_saved"] for scope, row in report["scopes"].items()
                              }}))
    except (OSError, ValueError, CorpusError, AssertionError) as exc:
        print(json.dumps({"status": "local_error", "kind": type(exc).__name__, "message": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
