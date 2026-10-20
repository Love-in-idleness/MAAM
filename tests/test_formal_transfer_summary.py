"""Offline reporting preserves formal phases and excludes calibration witnesses."""
import copy
from contextlib import redirect_stdout
from decimal import Decimal
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from scripts import summarize_formal_transfer as summary


class FormalSummaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "plan.json").write_text("{}")
        self.formal = self.state()
        self.calibration = self.root / "calibration"
        self.cost_only = self.state(calls=16)
        self.cost_only["ledger"]["guarded_cost_usd"] = "0.07"
        self.cost_only["ledger"]["known_guarded_cost_lower_bound_usd"] = "0.07"
        self.states = {self.root: self.formal, self.calibration: self.cost_only}
        self.report = patch.object(summary.transfer, "report", side_effect=lambda root: copy.deepcopy(self.states[root])).start()
        patch.object(summary.transfer, "load", return_value=(self.root, {"freeze_commit": "frozen"}, {
            "fingerprints": {"protocol_sha256": "hash"}, "manifest": {"config": {"model": "alias"}}})).start()
        patch.object(summary.generation, "load_run", side_effect=lambda root: (root, {})).start()
        patch.object(summary.generation, "call_records", return_value=[]).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def state(calls=8):
        stages = {}
        for phase, prefix in (("development", "d"), ("reserved", "r")):
            goals, tasks = [], []
            for index in (1, 2):
                task = prefix + str(index)
                goals.append({"id": task, "family": "fixture", "baseline": "verified", "treatment": "verified"})
                for condition in ("baseline", "treatment"):
                    tasks.append({"task_id": task, "condition": condition, "status": "verified", "calls": 1,
                        "selected": {"attempt": 1, "proof_source_tokens": 50,
                                     "package_source_tokens": 2300 if condition == "treatment" else 0}})
            stages[phase] = {"complete": True,
                "generation": {"tasks": tasks, "calls": 4, "reported_models": ["alias"]},
                "comparison": {"tasks": goals,
                    "coverage": {"baseline": [prefix + "1", prefix + "2"], "treatment": [prefix + "1", prefix + "2"]},
                    "common_task_source_ledger": {"task_ids": [prefix + "1", prefix + "2"],
                        "baseline_tokens": 1000, "treatment_including_package_tokens": 2400,
                        "package_tokens_charged_once": 2300, "net_tokens_saved": -1400}}}
        return {"status": "completed", "study_id": "formal", "stop": None,
            "matched_allocations_complete": True, "stages": stages,
            "ledger": {"generation_calls": calls, "usage_complete": True, "input_tokens": 800,
                "output_tokens": 80, "known_input_tokens_lower_bound": 800, "known_output_tokens_lower_bound": 80,
                "charged_input_tokens": 800, "charged_output_tokens": 80, "guarded_cost_usd": "0.02",
                "known_guarded_cost_lower_bound_usd": "0.02", "provider_evidence": True,
                "interrupted": False, "violations": []}}

    def test_completed_run_preserves_phases_package_once_and_honest_claims(self):
        result = summary.summarize(self.root)
        self.assertTrue(result["matched_allocations_complete"])
        self.assertTrue(result["reserved_evaluation_started"])
        self.assertTrue(result["reserved_evaluation_completed"])
        for phase, prefix in (("development", "d"), ("reserved", "r")):
            stage = result["stages"][phase]
            self.assertEqual([g["task_id"] for g in stage["goals"]], [prefix + "1", prefix + "2"])
            self.assertEqual(stage["common_task_source_ledger"]["package_tokens_charged_once"], 2300)
            self.assertEqual(stage["common_task_source_ledger"]["treatment_including_package_tokens"], 2400)
        for field in ("fair_model_performance_claim", "held_out_effectiveness_claim", "exact_model_revision_verified", "training_eligible"):
            self.assertIs(result[field], False)

    def test_partial_stage_reports_exhausted_without_proof_and_failures(self):
        self.formal.update(status="in_progress", matched_allocations_complete=False)
        stage = self.formal["stages"]["reserved"]
        stage["complete"] = False
        stage["comparison"]["tasks"][0]["baseline"] = "not_observed_solved"
        stage["generation"]["tasks"][0].update(status="call_budget_exhausted", selected=None)
        with patch.object(summary.generation, "call_records", return_value=[{
            "pending": {"call_id": "0001", "task_id": "r1", "condition": "baseline", "allowance": 10},
            "result": {"status": "provider_incomplete_or_error", "feedback": {"kind": "truncated"}},
            "receipt": {"usage": {"input_tokens": 1, "output_tokens": 10}}}]):
            goal = summary.summarize(self.root)["stages"]["reserved"]["goals"][0]["baseline"]
        self.assertEqual(goal["generation_status"], "call_budget_exhausted")
        self.assertIsNone(goal["selected_source_cost"])
        self.assertEqual(goal["call_outcomes"][0]["failure"], {"kind": "truncated"})

    def test_unknown_usage_remains_null_and_retains_charged_allowance(self):
        self.formal["ledger"].update(usage_complete=False, input_tokens=None, output_tokens=None,
            interrupted=True, charged_output_tokens=1000)
        result = summary.summarize(self.root)
        self.assertIsNone(result["cumulative_cost_only"]["output_tokens"])
        self.assertEqual(result["cumulative_cost_only"]["charged_output_tokens"], 1000)
        self.assertEqual(result["cumulative_cost_only"]["known_output_tokens_lower_bound"], 80)

    def test_known_usage_interrupted_verification_does_not_erase_metering(self):
        self.formal["ledger"]["interrupted"] = True
        self.formal["stages"]["reserved"]["complete"] = False
        self.formal["matched_allocations_complete"] = False
        result = summary.summarize(self.root)
        self.assertTrue(result["cumulative_cost_only"]["usage_complete"])
        self.assertEqual(result["cumulative_cost_only"]["output_tokens"], 80)
        self.assertFalse(result["reserved_evaluation_completed"])

    def test_all_calibration_calls_cost_only_without_proof_mixing(self):
        result = summary.summarize(self.root, [self.calibration])
        self.assertEqual(result["cumulative_cost_only"]["generation_calls"], 24)
        self.assertEqual(Decimal(result["cumulative_cost_only"]["guarded_cost_usd"]), Decimal("0.09"))
        self.assertEqual(result["stages"], summary.summarize(self.root)["stages"])
        self.assertEqual(set(result["calibration_cost_only"][0]), {"root", "ledger"})

    def test_duplicate_root_and_upstream_tamper_fail_closed(self):
        with self.assertRaises(CorpusError):
            summary.summarize(self.root, [self.root])
        self.report.side_effect = CorpusError("raw replay changed")
        with self.assertRaises(CorpusError):
            summary.summarize(self.root)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(["--root", str(self.root), "--output", str(self.root / "absent.json")]), 2)
        self.assertFalse((self.root / "absent.json").exists())

    def test_output_is_fresh_and_zero_call_stage_is_unrun(self):
        self.formal["stages"]["reserved"]["generation"]["calls"] = 0
        self.formal["stages"]["reserved"]["complete"] = False
        self.assertFalse(summary.summarize(self.root)["reserved_evaluation_started"])
        output = self.root / "summary.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(["--root", str(self.root), "--output", str(output)]), 0)
            original = output.read_bytes()
            self.assertEqual(summary.main(["--root", str(self.root), "--output", str(output)]), 2)
        self.assertEqual(output.read_bytes(), original)
