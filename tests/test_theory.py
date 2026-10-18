import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam.theory import compare_audits, load_experiment, run_experiment

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "hom_kernel" / "experiment.json"


class TheoryExperimentTests(unittest.TestCase):
    def copied(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "experiment"
        shutil.copytree(EXPERIMENT.parent, folder)
        return folder / "experiment.json"

    def edit(self, path, change):
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))
        return path

    def test_actual_frozen_reference_is_complete(self):
        frozen = load_experiment(EXPERIMENT)
        self.assertEqual(set(frozen["blobs"]), {"Base", "Baseline", "Candidate", "Treatment"})
        self.assertEqual(frozen["manifest"]["phase"], "reference_migration")
        self.assertEqual(frozen["manifest"]["tasks"][0]["split"], "development")

    def test_modified_source_is_rejected_before_execution(self):
        path = self.copied()
        source = path.parent / "Candidate.lean"
        source.write_text(source.read_text() + "\naxiom forged : False\n")
        with self.assertRaisesRegex(CorpusError, "fingerprint mismatch"):
            load_experiment(path)

    def test_candidate_cannot_expand_the_axiom_policy(self):
        path = self.copied()
        self.edit(path, lambda d: d["base"]["allowed_axioms"].append("forged"))
        with self.assertRaisesRegex(CorpusError, "standard core axioms"):
            load_experiment(path)

    def test_candidate_must_belong_to_the_frozen_base(self):
        path = self.copied()
        package = path.parent / "package.json"
        data = json.loads(package.read_text())
        data["base_id"] = "different-foundation"
        package.write_text(json.dumps(data))
        with self.assertRaisesRegex(CorpusError, "different base"):
            load_experiment(path)

    def test_reference_run_cannot_be_labelled_held_out(self):
        path = self.copied()
        self.edit(path, lambda d: d["tasks"][0].update(split="held_out"))
        with self.assertRaisesRegex(CorpusError, "not held-out"):
            load_experiment(path)

    def test_source_paths_cannot_escape_the_experiment(self):
        path = self.copied()
        self.edit(path, lambda d: d["sources"]["Base"].update(path="../other.lean"))
        with self.assertRaisesRegex(CorpusError, "leaves the experiment"):
            load_experiment(path)

    def test_baseline_and_candidate_modules_cannot_overlap(self):
        path = self.copied()
        self.edit(path, lambda d: d["conditions"]["baseline"].update(
            modules=["Candidate"], entry_module="Candidate"))
        with self.assertRaisesRegex(CorpusError, "disjoint"):
            load_experiment(path)

    def test_invalid_name_shape_is_a_schema_error(self):
        path = self.copied()
        self.edit(path, lambda d: d["base"].update(modules=[["not", "a", "name"]]))
        with self.assertRaisesRegex(CorpusError, "invalid name"):
            load_experiment(path)

    def test_core_modules_cannot_be_shadowed(self):
        path = self.copied()
        self.edit(path, lambda d: d["base"].update(modules=["Init"]))
        with self.assertRaisesRegex(CorpusError, "shadow core"):
            load_experiment(path)

    def test_verification_timeout_is_inconclusive_not_rejection(self):
        version = subprocess.CompletedProcess([], 0, "Lean (version 4.24.0, test)", "")
        with patch("maam.theory.shutil.which", return_value="/tool/lean"), \
             patch("maam.theory.subprocess.run", side_effect=[
                 version, subprocess.TimeoutExpired("lean", 1)]):
            result = run_experiment(EXPERIMENT)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["failure"]["kind"], "budget_exhausted")
        self.assertIsNone(result["comparison"])

    def test_compilation_failure_cannot_produce_a_comparison(self):
        version = subprocess.CompletedProcess([], 0, "Lean (version 4.24.0, test)", "")
        failure = subprocess.CompletedProcess([], 1, "unknown identifier", "")
        with patch("maam.theory.shutil.which", return_value="/tool/lean"), \
             patch("maam.theory.subprocess.run", side_effect=[version, failure]):
            result = run_experiment(EXPERIMENT)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["failure"]["kind"], "verification_failed")
        self.assertIsNone(result["comparison"])

    def test_local_shortcut_does_not_hide_the_package_cost(self):
        manifest = load_experiment(EXPERIMENT)["manifest"]
        def target(name, body, nodes):
            return {"name": name, "expected": "Foundation.kernelMulGoal",
                    "goal_preserved": True, "proof_expr_nodes": nodes,
                    "source": {"signature_tokens": 5, "body_tokens": body,
                               "declaration_tokens": body + 6}}
        audits = {
            "baseline": {"targets": [target("Baseline.kernelMul", 80, 120)],
                         "sources": [{"module": "Baseline", "source_tokens": 100}]},
            "treatment": {"targets": [target("Treatment.kernelMul", 30, 70)],
                          "sources": [{"module": "Candidate", "source_tokens": 80},
                                      {"module": "Treatment", "source_tokens": 40}]},
        }
        comparison = compare_audits(manifest, audits)
        self.assertEqual(comparison["tasks"][0]["local_proof_body_tokens_saved"], 50)
        self.assertEqual(comparison["source_ledger"]["net_tokens_saved"], -20)
        self.assertEqual(comparison["source_ledger"]["outcome"], "higher_cost")
        self.assertEqual(comparison["judgement"], "reference_evidence_only")

    def test_changed_audit_goal_is_not_accepted_as_compression(self):
        manifest = load_experiment(EXPERIMENT)["manifest"]
        audits = {"baseline": {"targets": [{"name": "Baseline.kernelMul",
                                             "expected": "True", "goal_preserved": True}]}}
        with self.assertRaisesRegex(CorpusError, "audit target mismatch"):
            compare_audits(manifest, audits)


if __name__ == "__main__":
    unittest.main()
