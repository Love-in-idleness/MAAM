"""Regression controls for whole portfolios, nonadditive costs and attribution."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from maam import CorpusError
from maam.attribution import portfolio_attribution
from maam.cli import main
from maam.precompression import compare_study, measure_sources
from maam.theory import digest
from scripts.measure_compressed_reference import measure_sources as archived_measure

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "experiments/precompression_v1"


class PortfolioAttributionTests(unittest.TestCase):
    def test_theory_example_and_adoption_modes(self):
        costs = dict(historical=180, prepared=110, control=92, treatment=78, unit="synthetic_units")
        report = portfolio_attribution(**costs)
        self.assertEqual(report["historical_net_saving"], 102)
        self.assertEqual(report["old_tool_preparation_saving"], 70)
        self.assertEqual(report["continued_old_tool_search_saving"], 18)
        self.assertEqual(report["candidate_provision_observed_difference"], 14)
        self.assertTrue(report["identity_verified"])
        self.assertFalse(report["global_minimum_established"])
        costs["treatment"] = 150
        with self.assertRaises(CorpusError):
            portfolio_attribution(**costs)
        report = portfolio_attribution(**costs, retain_prepared=False)
        self.assertEqual(report["candidate_provision_observed_difference"], -58)
        self.assertTrue(report["identity_verified"])

    def test_unknown_values_and_invalid_inputs(self):
        costs = dict(historical=180, prepared=110, control=None, treatment=78, unit="bytes")
        report = portfolio_attribution(**costs)
        self.assertEqual(report["historical_net_saving"], 102)
        self.assertIsNone(report["identity_verified"])
        self.assertIsNone(report["candidate_provision_observed_difference"])
        for change in ({"control": True}, {"treatment": -1}, {"prepared": 1.5}, {"unit": ""},
                       {"unit": 4}, {"retain_prepared": 1}, {"prepared": 181}):
            with self.subTest(change=change), self.assertRaises(CorpusError):
                portfolio_attribution(**{**costs, **change})


class PrecompressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for source in EXAMPLE.glob("*.lean"):
            shutil.copy(source, self.root / source.name)
        self.study = self.root / "study.json"
        self.data = json.loads((EXAMPLE / "study.json").read_text())
        self.write()

    def write(self):
        self.study.write_text(json.dumps(self.data))

    def replace_source(self, module, content):
        path = self.root / self.data["sources"][module]["path"]
        path.write_bytes(content)
        self.data["sources"][module]["sha256"] = digest(content)

    def test_joint_encoding_matches_archived_reference(self):
        sources = {"Proof": "-- 中文\n".encode(), "Candidate": b"theorem k : True := trivial\n"}
        measured, archived = measure_sources(sources), archived_measure(sources)
        self.assertEqual(measured["payload_sha256"], archived["payload_sha256"])
        self.assertEqual(measured["zlib_9_bytes"], archived["compressed"]["zlib-9"]["bytes"])
        self.assertEqual(measured["bzip2_9_bytes"], archived["compressed"]["bzip2-9"]["bytes"])
        self.assertTrue(measured["roundtrip_verified"])
        self.assertNotEqual(measured["zlib_9_bytes"], sum(
            measure_sources({m: s})["zlib_9_bytes"] for m, s in sources.items()))

    def test_incumbents_sharing_and_optional_versus_mandatory(self):
        report = compare_study(self.study)
        treatment = next(r for r in report["routes"] if r["stage"] == "treatment")
        self.assertEqual(treatment["costs"]["complete"]["charged_modules"], ["Candidate", "Treatment"])
        for comparisons in report["metrics"].values():
            selected = comparisons["optional_adoption"]["selected"]
            self.assertLessEqual(selected["prepared"]["cost"], selected["historical"]["cost"])
            self.assertLessEqual(selected["treatment"]["cost"], selected["prepared"]["cost"])
            self.assertTrue(comparisons["optional_adoption"]["attribution"]["identity_verified"])
        raw = report["metrics"]["source_utf8_bytes"]
        self.assertEqual(raw["optional_adoption"]["selected"]["treatment"]["route_id"], "prepared")
        self.assertGreater(raw["mandatory_adoption"]["selected"]["cost"],
                           raw["optional_adoption"]["selected"]["treatment"]["cost"])
        self.assertFalse(report["search_executed"])
        self.assertFalse(report["package_attribution_ready"])
        self.assertEqual(report["formal_verification"], "not_run_by_source_measurer")

    def test_joint_improvement_accepts_locally_longer_proof(self):
        # Synthetic strings isolate accounting, without asserting Lean validity.
        for module, size in (("Historical", 400), ("Prepared", 300), ("Control", 300),
                             ("Candidate", 60), ("Treatment", 78)):
            self.replace_source(module, b"x" * size)
        self.write()
        report = compare_study(self.study)["metrics"]["source_utf8_bytes"]
        self.assertEqual(report["optional_adoption"]["selected"]["treatment"]["cost"], 138)
        self.assertEqual(report["optional_adoption"]["selected"]["treatment"]["route_id"], "treatment")
        self.assertEqual(report["installed_reuse"]["selected"]["cost"], 78)

    def test_control_rediscovery_and_partial_use_pay_whole_package(self):
        self.data["routes"][2]["modules"].append("Candidate")
        self.data["sources"]["CandidateExtra"] = {"path": "CandidateExtra.lean", "sha256": digest(b"extra")}
        (self.root / "CandidateExtra.lean").write_bytes(b"extra")
        self.data["candidate"]["modules"].append("CandidateExtra")
        self.write()
        report = compare_study(self.study)
        control = next(r for r in report["routes"] if r["stage"] == "control")
        self.assertEqual(control["costs"]["complete"]["charged_modules"],
                         ["Candidate", "CandidateExtra", "Control"])
        self.assertFalse(report["information_separation_established"])

    def test_fingerprints_missing_sources_and_coverage_fail_closed(self):
        original = json.dumps(self.data)
        mutations = [lambda: self.data.update(schema_version=True),
                     lambda: self.data["routes"][0].update(stage=[]),
                     lambda: self.data["routes"][0].update(targets=["Calibration.one"]),
                     lambda: self.data["routes"][0].update(modules=["Missing"]),
                     lambda: self.data["routes"][1].update(id="historical"),
                     lambda: self.data["candidate"].update(modules=["Base"]),
                     lambda: self.data["sources"]["Base"].update(path="../escape.lean"),
                     lambda: self.data["sources"]["Base"].update(sha256="0" * 64)]
        for mutate in mutations:
            self.data = json.loads(original)
            mutate()
            self.write()
            with self.assertRaises(CorpusError):
                compare_study(self.study)

    def test_cli_runs_without_lean_and_preserves_output(self):
        output = self.root / "report.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["precompression", "--study", str(self.study), "--output", str(output)]), 0)
            first = output.read_bytes()
            self.assertEqual(main(["precompression", "--study", str(self.study), "--output", str(output)]), 1)
        self.assertEqual(first, output.read_bytes())
        self.assertEqual(json.loads(first)["status"], "measured_source_portfolios")
