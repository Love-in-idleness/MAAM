"""Bounded round stability; all Lean verification results are explicit fixtures."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, baseline_search
from maam.baseline import inventory_baseline
from maam.migration import canonical, proof_source, seal, start_session, submit_attempt, task_request, unseal
from maam.theory import digest
from scripts import control_baseline_stability as stability


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"
MATCHING_PROOF = "by\n  have h := f x\n  rw [r] at h\n  exact h\n"
TWO_BLOCK_PROOF = ("by\n  constructor\n  ·\n    have hx := f x\n    rw [r] at hx\n"
                   "    exact hx\n  ·\n    have hy := f y\n    rw [r] at hy\n    exact hy\n")


class BaselineStabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.tokens = 100
        self.verifier_status = "verified"
        self.verification_calls = 0
        patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError(
            "No provider calls in deterministic stability tests")).start()
        self.addCleanup(patch.stopall)

    def verify(self, frozen, request, source, artifact, **kwargs):
        self.verification_calls += 1
        if self.verifier_status == "interrupt":
            raise KeyboardInterrupt("Fixture interrupted verification")
        if self.verifier_status != "verified":
            return {"status": self.verifier_status, "trace": [], "audit": None,
                    "failure": {"kind": "fixture_failure", "message": self.verifier_status}}
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens}]}}

    def inventory(self, *, proof=MATCHING_PROOF, name="case", tasks=("d01",)):
        seed = self.work / (name + "-seed")
        start_session(SUITE, seed, condition="baseline", solver_id="mocked-lean-fixture")
        self.tokens, self.verifier_status = 100, "verified"
        for task in tasks:
            request = task_request(seed, task)
            submit_attempt(seed, {"task_id": task, "request_sha256": request["request_sha256"],
                                  "proof": proof, "bridge": "Fixture only; Lean is mocked"})
        path = self.work / (name + "-inventory.json")
        path.write_text(json.dumps(inventory_baseline([seed], list(tasks))))
        return path

    def prepared(self, *, proof=MATCHING_PROOF, name="case", tasks=("d01",)):
        inventory = self.inventory(proof=proof, name=name, tasks=tasks)
        root = self.work / name
        stability.prepare(inventory, root)
        return root

    def assert_no_broader_claims(self, report):
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "model_search_verified", "definition_optimization_performed"):
            self.assertIs(report[flag], False)
        self.assertIsNone(report["generation_usage"])
        self.assertEqual(report["actual_provider_calls"], 0)
        self.network.assert_not_called()

    def test_prepare_reserves_no_round_and_does_not_execute_methods(self):
        inventory = self.inventory()
        before = self.verification_calls
        root = self.work / "outer"
        report = stability.prepare(inventory, root)
        self.assertEqual(report["status"], "in_progress")
        self.assertEqual(report["rounds"], [])
        self.assertEqual(report["stable_rounds"], 0)
        self.assertFalse(report["declared_method_preparation_complete"])
        self.assertEqual(list((root / "rounds").iterdir()), [])
        self.assertEqual(len((root / "issued.jsonl").read_bytes().splitlines()), 1)
        self.assertEqual(self.verification_calls, before)
        self.assertEqual(report, stability.report(root))
        self.assert_no_broader_claims(report)

    def test_first_round_improvement_needs_two_further_clean_rounds(self):
        root = self.prepared()
        self.tokens = 50
        for index, stable in ((1, 0), (2, 1), (3, 2)):
            report = stability.execute_round(root)
            self.assertEqual(len(report["rounds"]), index)
            self.assertEqual(report["stable_rounds"], stable)
            self.assertEqual((report["initial_source_tokens"], report["selected_source_tokens"]), (100, 50))
            self.assertEqual(report["declared_method_preparation_complete"], index == 3)
            self.assertEqual(report["status"], "declared_method_preparation_complete"
                             if index == 3 else "in_progress")
        first = unseal(root / "rounds/01/execution/generated/0001.json")
        second = unseal(root / "rounds/02/execution/generated/0001.json")
        expected_source = proof_source(first["request"]["inner_request"], first["response"]["proof"])
        self.assertEqual(second["request"]["incumbent"]["proof"], first["response"]["proof"])
        self.assertEqual(second["request"]["incumbent"]["proof_source_sha256"],
                         digest(expected_source.encode()))
        self.assertEqual(second["request"]["incumbent"]["proof_source_tokens"], 50)
        self.assertEqual(report, stability.report(root))
        before = self.verification_calls
        with self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assertEqual(self.verification_calls, before)
        self.assert_no_broader_claims(report)

    def test_improvement_in_round_two_leaves_insufficient_stability_budget(self):
        root = self.prepared(proof=TWO_BLOCK_PROOF)
        for tokens, stable in ((80, 0), (60, 0), (60, 1)):
            self.tokens = tokens
            report = stability.execute_round(root)
            self.assertEqual(report["stable_rounds"], stable)
            self.assertEqual(report["selected_source_tokens"], tokens)
        self.assertEqual(report["status"], "round_budget_exhausted")
        self.assertFalse(report["declared_method_preparation_complete"])
        self.assertEqual(len(report["rounds"]), 3)
        with self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assert_no_broader_claims(report)

    def test_two_clean_rounds_stop_without_verification_or_third_round(self):
        root = self.prepared(proof="by exact existing_certificate", tasks=("d01", "d02"))
        before = self.verification_calls
        first = stability.execute_round(root)
        self.assertEqual((first["status"], first["stable_rounds"]), ("in_progress", 1))
        final = stability.execute_round(root)
        self.assertEqual((final["status"], final["stable_rounds"]),
                         ("declared_method_preparation_complete", 2))
        self.assertEqual((final["initial_source_tokens"], final["selected_source_tokens"]), (200, 200))
        self.assertEqual(self.verification_calls, before)
        for number in ("01", "02"):
            execution = root / "rounds" / number / "execution"
            self.assertEqual(len(list((execution / "generated").glob("*.json"))), 4)
        with self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assertFalse((root / "rounds/03").exists())
        self.assert_no_broader_claims(final)

    def test_rejected_candidates_never_count_as_clean(self):
        root = self.prepared()
        self.verifier_status = "rejected"
        for number in range(1, 4):
            report = stability.execute_round(root)
            self.assertEqual(report["stable_rounds"], 0)
            self.assertFalse(report["declared_method_preparation_complete"])
            self.assertEqual(report["selected_source_tokens"], 100)
            self.assertEqual(report["status"], "round_budget_exhausted" if number == 3 else "in_progress")
        self.assert_no_broader_claims(report)

    def test_unknown_or_inconclusive_verification_stops_without_retry(self):
        for status in ("inconclusive", "unknown_fixture_result"):
            with self.subTest(status=status):
                root = self.prepared(name=status)
                self.verifier_status = status
                report = stability.execute_round(root)
                self.assertEqual(report["status"], "interrupted_or_inconclusive")
                self.assertEqual(report["stable_rounds"], 0)
                self.assertFalse(report["declared_method_preparation_complete"])
                journal = (root / "issued.jsonl").read_bytes()
                before = self.verification_calls
                with self.assertRaises(CorpusError):
                    stability.execute_round(root)
                self.assertEqual(self.verification_calls, before)
                self.assertEqual((root / "issued.jsonl").read_bytes(), journal)

    def test_writeahead_interruption_never_restores_outer_round_slot(self):
        for boundary in ("prepare_search", "execute_next", "verification"):
            with self.subTest(boundary=boundary):
                root = self.prepared(name=boundary)
                if boundary == "verification":
                    self.verifier_status = "interrupt"
                    with self.assertRaises(KeyboardInterrupt):
                        stability.execute_round(root)
                else:
                    target = ("maam.baseline_search.prepare_search" if boundary == "prepare_search"
                              else "maam.baseline_execution.execute_next")
                    with patch(target, side_effect=KeyboardInterrupt("Fixture interrupted round")), \
                            self.assertRaises(KeyboardInterrupt):
                        stability.execute_round(root)
                journal = (root / "issued.jsonl").read_bytes()
                self.assertEqual(len(journal.splitlines()), 2)
                self.assertEqual(stability.report(root)["status"], "interrupted_or_inconclusive")
                before = self.verification_calls
                with self.assertRaises(CorpusError):
                    stability.execute_round(root)
                self.assertEqual(self.verification_calls, before)
                self.assertEqual((root / "issued.jsonl").read_bytes(), journal)

    def test_deleting_issued_round_evidence_cannot_restore_slot(self):
        root = self.prepared(proof="by exact existing_certificate")
        stability.execute_round(root)
        journal = (root / "issued.jsonl").read_bytes()
        shutil.rmtree(root / "rounds/01")
        before = self.verification_calls
        with self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assertEqual(self.verification_calls, before)
        self.assertEqual((root / "issued.jsonl").read_bytes(), journal)
        self.assertFalse((root / "rounds/01").exists())
        self.assertFalse((root / "rounds/02").exists())

    def test_forged_inherited_inventory_is_rejected_before_next_verification(self):
        root = self.prepared()
        self.tokens = 50
        stability.execute_round(root)
        real_prepare = baseline_search.prepare_search

        def changed_inventory(path, policy, output):
            path = Path(path)
            value = json.loads(path.read_text())
            value["tasks"][0]["selected"]["proof_source_tokens"] -= 1
            path.write_text(json.dumps(value))
            return real_prepare(path, policy, output)

        before = self.verification_calls
        with patch("maam.baseline_search.prepare_search", side_effect=changed_inventory), \
                self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assertEqual(self.verification_calls, before)
        with self.assertRaises(CorpusError):
            stability.execute_round(root)
        self.assertEqual(self.verification_calls, before)
        self.assertFalse((root / "rounds/03").exists())

    def test_cli_runs_to_terminal_and_output_never_overwrites(self):
        inventory = self.inventory(proof="by exact existing_certificate")
        root = self.work / "cli"
        output = self.work / "status.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(stability.main(["prepare", "--root", str(root),
                                            "--inventory", str(inventory)]), 0)
            self.assertEqual(stability.main(["run", "--root", str(root)]), 0)
            self.assertEqual(stability.main(["status", "--root", str(root), "--output", str(output)]), 0)
            original = output.read_bytes()
            self.assertEqual(stability.main(["status", "--root", str(root), "--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), original)
        self.assertEqual(stability.report(root)["status"], "declared_method_preparation_complete")

    def test_resealed_child_schedule_or_incumbent_cannot_change_declared_scope(self):
        for field in ("schedule", "initial"):
            with self.subTest(field=field):
                root = self.prepared(name=field, proof="by exact existing_certificate")
                stability.execute_round(root)
                path = root / "rounds/01/search/plan.json"
                plan = unseal(path)
                if field == "schedule":
                    plan[field][0]["method"] = dict(stability.POLICY["methods"][1])
                else:
                    plan[field][0]["proof_source_tokens"] += 1
                path.write_bytes(canonical(seal(plan)))
                with patch("maam.baseline_execution.report", side_effect=AssertionError(
                        "scope must be checked before child replay")), self.assertRaises(CorpusError):
                    stability.report(root)

    def test_more_than_two_goals_cannot_start_a_stability_run(self):
        inventory = self.inventory(tasks=("d01", "d02", "d03"))
        root = self.work / "too-many"
        with self.assertRaises(CorpusError):
            stability.prepare(inventory, root)
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
