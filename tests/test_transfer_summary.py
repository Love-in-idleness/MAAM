"""Offline cross-protocol accounting; upstream sealed/raw replay is mocked."""
import copy
from contextlib import redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from maam import CorpusError
from maam.theory import digest
from scripts import summarize_transfer as summary


class TransferSummaryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.roots = [self.folder / str(i) for i in range(3)]
        self.states, self.loaded = {}, {}
        for i, root in enumerate(self.roots):
            root.mkdir()
            (root / "plan.json").write_text(json.dumps({"fixture": i}))
            self.states[root] = self.state()
            self.loaded[root] = {"frozen": {"fingerprints": {"suite": "same-suite", "source": "same-source"}},
                "fingerprints": {"protocol_sha256": "protocol-" + str(i)},
                "manifest": {"config": {"model": "deepseek-flash", "output_cap": 8192 + i},
                    "task_order": {"development": ["d0" + str(i + 1)], "reserved": ["r01"]},
                    "experiment_budget": {"max_cost_usd": "0.12"}}}
        self.report = patch.object(summary.transfer, "report", side_effect=lambda root: copy.deepcopy(self.states[root])).start()
        self.load = patch.object(summary.transfer, "load", side_effect=lambda root: (root, {"freeze_commit": "commit"}, copy.deepcopy(self.loaded[root]))).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def task(task, condition, proof=None, package=0, status="verified", calls=1):
        selected = None if proof is None else {"attempt": 1, "proof_source_tokens": proof,
                                              "package_source_tokens": package}
        return {"task_id": task, "condition": condition, "calls": calls,
                "status": status if selected else "call_budget_exhausted", "selected": selected}

    @staticmethod
    def state(tasks=()):
        return {"status": "stopped", "ledger": {"generation_calls": 2, "usage_complete": True,
            "input_tokens": 20, "output_tokens": 30,
            "known_input_tokens_lower_bound": 20, "known_output_tokens_lower_bound": 30,
            "charged_input_tokens": 20, "charged_output_tokens": 30,
            "guarded_cost_usd": "0.01", "known_guarded_cost_lower_bound_usd": "0.01",
            "interrupted": False, "violations": []},
            "stages": {"development": {"generation": {"tasks": list(tasks)}},
                       "reserved": {"generation": {"calls": 0}}}}

    def test_replays_every_root_retains_distinct_contexts_and_original_reports(self):
        result = summary.summarize(self.roots)
        self.assertEqual(self.report.call_count, 3)
        self.assertEqual(self.load.call_count, 3)
        for i, root in enumerate(self.roots):
            run = result["runs"][i]
            self.assertEqual(run["report"], self.states[root])
            self.assertEqual(run["plan_sha256"], digest((root / "plan.json").read_bytes()))
            self.assertEqual(run["protocol_sha256"], "protocol-" + str(i))
            self.assertEqual(run["config"], self.loaded[root]["manifest"]["config"])
            self.assertEqual(run["task_order"], self.loaded[root]["manifest"]["task_order"])
        self.assertEqual(result["totals"]["generation_calls"], 6)
        self.assertEqual(result["totals"]["input_tokens"], 60)
        self.assertEqual(Decimal(result["totals"]["guarded_cost_usd"]), Decimal("0.03"))
        for field in ("fair_model_performance_claim", "held_out_evaluation",
                      "held_out_effectiveness_claim", "matched_allocations_complete",
                      "exact_model_revision_verified", "training_eligible"):
            self.assertIs(result[field], False)

    def test_common_union_selects_best_observed_and_charges_package_once(self):
        self.states[self.roots[0]] = self.state([
            self.task("d01", "baseline", 100), self.task("d01", "treatment", 30, 1100),
            self.task("d02", "baseline", 90)])
        self.states[self.roots[1]] = self.state([
            self.task("d01", "baseline", 80), self.task("d01", "treatment", 40, 1100),
            self.task("d02", "treatment", 10, 1100), self.task("d03", "baseline", 200)])
        result = summary.summarize(self.roots[:2])
        ledger = result["common_task_source_ledger"]
        self.assertEqual(ledger["task_ids"], ["d01", "d02"])
        self.assertEqual(ledger["baseline_tokens"], 170)
        self.assertEqual(ledger["treatment_including_package_tokens"], 1140)
        self.assertEqual(ledger["package_tokens_charged_once"], 1100)
        self.assertEqual(ledger["net_tokens_saved"], -970)
        row = result["development_goals"]["d01"]
        self.assertEqual(len(row["observations"]), 4)
        self.assertEqual(row["selected"]["baseline"]["run_index"], 1)
        self.assertEqual(row["selected"]["treatment"]["run_index"], 0)

    def test_no_common_proofs_keeps_cost_unknown(self):
        self.states[self.roots[0]] = self.state([self.task("d01", "baseline", 100)])
        ledger = summary.summarize(self.roots[:1])["common_task_source_ledger"]
        self.assertEqual(ledger["task_ids"], [])
        for field in ("baseline_tokens", "treatment_including_package_tokens", "package_tokens_charged_once", "net_tokens_saved"):
            self.assertIsNone(ledger[field])

    def test_suite_or_source_mismatch_is_rejected(self):
        for field in ("suite", "source"):
            with self.subTest(field=field):
                self.loaded[self.roots[1]]["frozen"]["fingerprints"][field] = "changed"
                with self.assertRaisesRegex(CorpusError, "fingerprints"):
                    summary.summarize(self.roots[:2])
                self.loaded[self.roots[1]]["frozen"]["fingerprints"][field] = "same-" + field

    def test_inconsistent_package_cost_rejected_even_outside_common_set(self):
        self.states[self.roots[0]] = self.state([self.task("d01", "treatment", 20, 1100)])
        self.states[self.roots[1]] = self.state([self.task("d02", "treatment", 20, 1099)])
        with self.assertRaisesRegex(CorpusError, "package source cost"):
            summary.summarize(self.roots[:2])

    def test_baseline_candidate_and_invalid_source_costs_are_rejected(self):
        for proof, package in ((20, 1100), (True, 0), (-1, 0), (1.5, 0), (20, False)):
            with self.subTest(proof=proof, package=package):
                self.states[self.roots[0]] = self.state([self.task("d01", "baseline", proof, package)])
                with self.assertRaises(CorpusError):
                    summary.summarize(self.roots[:1])

    def test_all_failure_costs_unknown_reservations_and_reserved_calls_retained(self):
        old = self.states[self.roots[0]]["ledger"]
        old.update(generation_calls=16, guarded_cost_usd="0.061029750", known_guarded_cost_lower_bound_usd="0.061029750")
        unknown = self.states[self.roots[1]]["ledger"]
        unknown.update(generation_calls=1, usage_complete=False, input_tokens=None, output_tokens=None,
            known_input_tokens_lower_bound=0, known_output_tokens_lower_bound=0,
            charged_input_tokens=16384, charged_output_tokens=8192,
            guarded_cost_usd="0.018432", known_guarded_cost_lower_bound_usd="0", interrupted=True,
            violations=["provider_limit"])
        self.states[self.roots[1]]["stages"]["reserved"]["generation"]["calls"] = 1
        totals = summary.summarize(self.roots[:2])["totals"]
        self.assertEqual(totals["generation_calls"], 17)
        self.assertIsNone(totals["input_tokens"])
        self.assertIsNone(totals["output_tokens"])
        self.assertFalse(totals["usage_complete"])
        self.assertTrue(totals["interrupted"])
        self.assertEqual(totals["known_input_tokens_lower_bound"], 20)
        self.assertEqual(totals["charged_input_tokens"], 16404)
        self.assertEqual(totals["charged_output_tokens"], 8222)
        self.assertEqual(Decimal(totals["guarded_cost_usd"]), Decimal("0.079461750"))
        self.assertEqual(totals["reserved_generation_calls"], 1)
        self.assertEqual(totals["violations"], [{"run_index": 1, "violations": ["provider_limit"]}])

    def test_empty_prepared_run_is_not_unknown_paid_usage(self):
        ledger = self.states[self.roots[0]]["ledger"]
        ledger.update(generation_calls=0, usage_complete=False, input_tokens=None, output_tokens=None,
            known_input_tokens_lower_bound=0, known_output_tokens_lower_bound=0)
        totals = summary.summarize(self.roots[:1])["totals"]
        self.assertTrue(totals["usage_complete"])
        self.assertEqual(totals["input_tokens"], 0)

    def test_duplicate_resolved_roots_and_empty_list_are_rejected(self):
        for roots in ([], [self.roots[0], self.roots[0] / "."]):
            with self.assertRaisesRegex(CorpusError, "distinct"):
                summary.summarize(roots)

    def test_invalid_ceilings_rejected_and_exact_sum_preserved(self):
        for value in ("0", "-1", "NaN", "Infinity", "sNaN", "nonsense", True, None, 0.2):
            with self.subTest(value=value):
                with self.assertRaises(CorpusError):
                    summary.summarize(self.roots[:1], value)
        value = "0.12345678901234567890123456789"
        self.states[self.roots[0]]["ledger"]["guarded_cost_usd"] = value
        self.states[self.roots[1]]["ledger"]["guarded_cost_usd"] = "0.00000000000000000000000000001"
        result = summary.summarize(self.roots[:2], Decimal("0.20"))
        self.assertEqual(result["totals"]["guarded_cost_usd"], "0.12345678901234567890123456790")

    def test_upstream_tamper_replay_failure_propagates(self):
        self.report.side_effect = CorpusError("raw receipt changed")
        with self.assertRaisesRegex(CorpusError, "raw receipt"):
            summary.summarize(self.roots[:1])

    def test_cli_fresh_output_and_over_ceiling_report_retained_without_provider(self):
        output = self.folder / "summary.json"
        args = ["--run", str(self.roots[0]), "--output", str(output), "--ceiling-usd", "0.001"]
        with patch.object(summary.transfer, "run", side_effect=AssertionError("paid call")), redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(args), 2)
        value = json.loads(output.read_text())
        self.assertFalse(value["within_cost_ceiling"])
        original = output.read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(args), 2)
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
