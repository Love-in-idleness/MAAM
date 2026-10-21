"""Measure complete frozen source payloads without new Lean or provider runs."""
from contextlib import redirect_stderr, redirect_stdout
import bz2
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zlib

from maam import CorpusError
from maam.migration import canonical
from maam.theory import compare_audits, digest, load_experiment
from scripts import measure_compressed_reference as measurement


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = Path("experiments/hom_kernel/experiment.json")
REFERENCE = Path("results/theory-package-reference.json")
RECEIPT = Path("results/theory-package-validation.json")


class CompressedReferenceTests(unittest.TestCase):
    def temporary_root(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        shutil.copytree(ROOT / EXPERIMENT.parent, root / EXPERIMENT.parent)
        (root / "results").mkdir()
        for path in (REFERENCE, RECEIPT):
            shutil.copyfile(ROOT / path, root / path)
        return root

    def test_unicode_sources_and_insertion_order_have_one_payload(self):
        sources = {"Zeta": "-- 定义 α\n".encode(), "Alpha": b"theorem x : True := by trivial\n"}
        first = measurement.measure_sources(sources)
        second = measurement.measure_sources(dict(reversed(list(sources.items()))))
        payload = canonical({name: source.decode("utf-8") for name, source in sources.items()})
        self.assertEqual(first, second)
        self.assertEqual(first["modules"], ["Alpha", "Zeta"])
        self.assertEqual(first["source_utf8_bytes"], sum(map(len, sources.values())))
        self.assertEqual(first["serialized_utf8_bytes"], len(payload))
        self.assertEqual(first["payload_sha256"], digest(payload))
        self.assertIs(first["roundtrip_verified"], True)
        self.assertEqual(set(first["compressed"]), {"zlib-9", "bzip2-9"})
        for name, compressed in (("zlib-9", zlib.compress(payload, level=9)),
                                 ("bzip2-9", bz2.compress(payload, compresslevel=9))):
            self.assertEqual(first["compressed"][name],
                             {"bytes": len(compressed), "sha256": digest(compressed)})

    def test_roundtrip_flag_requires_both_actual_decompressions(self):
        for module in ("zlib", "bz2"):
            with self.subTest(codec=module), patch.object(
                    getattr(measurement, module), "decompress", return_value=b"wrong payload"):
                with self.assertRaises(CorpusError):
                    measurement.measure_sources({"Proof": b"example : True := by trivial\n"})

    def test_package_is_charged_once_and_base_only_in_standalone_scope(self):
        frozen = load_experiment(ROOT / EXPERIMENT)
        report = measurement.build_report(root=ROOT)
        for scope, with_base in (("nonshared_payload", False), ("standalone_sources", True)):
            comparison = report["scopes"][scope]
            for condition in ("baseline", "treatment"):
                modules = frozen["manifest"]["conditions"][condition]["modules"][:]
                if condition == "treatment":
                    modules += frozen["package"]["modules"]
                if with_base:
                    modules += frozen["manifest"]["base"]["modules"]
                sources = {name: frozen["blobs"][name] for name in modules}
                measured = comparison["conditions"][condition]
                self.assertEqual(measured["modules"], sorted(modules))
                self.assertEqual(measured["source_utf8_bytes"], sum(map(len, sources.values())))
                self.assertEqual(measured["payload_sha256"], digest(canonical(
                    {name: source.decode("utf-8") for name, source in sources.items()})))
            conditions = comparison["conditions"]
            saved = (conditions["baseline"]["compressed"]["zlib-9"]["bytes"]
                     - conditions["treatment"]["compressed"]["zlib-9"]["bytes"])
            self.assertEqual(comparison["net_zlib_bytes_saved"], saved)
            self.assertEqual(comparison["outcome"],
                             "improved" if saved > 0 else "tied" if saved == 0 else "higher_cost")

    def test_modified_frozen_source_is_rejected(self):
        root = self.temporary_root()
        source = root / EXPERIMENT.parent / "Candidate.lean"
        source.write_bytes(source.read_bytes() + b"\n-- changed source\n")
        with self.assertRaises(CorpusError):
            measurement.build_report(root=root)

    def test_recomputed_ledger_does_not_authenticate_replacement_reference(self):
        root = self.temporary_root()
        path = root / REFERENCE
        report = json.loads(path.read_text())
        report["audits"]["baseline"]["sources"][0]["source_tokens"] += 1
        manifest = load_experiment(root / EXPERIMENT)["manifest"]
        report["comparison"] = compare_audits(manifest, report["audits"])
        path.write_text(json.dumps(report))
        with self.assertRaises(CorpusError):
            measurement.build_report(root=root)

    def test_replacement_validation_receipt_is_rejected(self):
        root = self.temporary_root()
        path = root / RECEIPT
        receipt = json.loads(path.read_text())
        receipt["workflow_run_id"] += 1
        path.write_text(json.dumps(receipt))
        with self.assertRaises(CorpusError):
            measurement.build_report(root=root)

    def test_saved_report_must_equal_recomputed_measurements(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "measurement.json"
            report = measurement.build_report(root=ROOT)
            path.write_text(json.dumps(report))
            measurement.check_report(path, root=ROOT)
            report["scopes"]["nonshared_payload"]["conditions"]["treatment"][
                "compressed"]["zlib-9"]["bytes"] -= 1
            path.write_text(json.dumps(report))
            with self.assertRaises(CorpusError):
                measurement.check_report(path, root=ROOT)

    def test_cli_creates_checks_and_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            path = Path(temporary) / "measurement.json"
            self.assertEqual(measurement.main(["--output", str(path)]), 0)
            original = path.read_bytes()
            self.assertEqual(measurement.main(["--check", str(path)]), 0)
            self.assertEqual(measurement.main(["--output", str(path)]), 2)
            self.assertEqual(path.read_bytes(), original)
            report = json.loads(original)
            report["scopes"]["standalone_sources"]["net_zlib_bytes_saved"] += 1
            path.write_text(json.dumps(report))
            self.assertEqual(measurement.main(["--check", str(path)]), 2)

    def test_strict_replay_rejects_boolean_and_float_for_integer_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "measurement.json"
            for wrong_type in (True, 1.0):
                report = measurement.build_report(root=ROOT)
                report["schema_version"] = wrong_type
                path.write_text(json.dumps(report))
                with self.subTest(value=wrong_type), self.assertRaises(CorpusError):
                    measurement.check_report(path, root=ROOT)


if __name__ == "__main__":
    unittest.main()
