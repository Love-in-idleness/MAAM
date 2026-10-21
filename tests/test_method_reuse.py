"""Bounded method reuse; Lean audits are explicit offline fixtures."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, migration
from maam.baseline import inventory_baseline
from scripts import control_method_reuse as reuse
from scripts.measure_compressed_reference import measure_sources


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"
TASKS = ("d02", "d04")


class MethodReuseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.seed = self.work / "seed"
        self.root = self.work / "reuse"
        self.model_root = self.work / "source-model"
        self.tokens = {"d01": 42, "d02": 150, "d03": 144, "d04": 230}
        self.verifier_status = "verified"
        self.verifier = self.enterContext(patch(
            "maam.migration.verify_attempt", side_effect=self.verify_fixture))
        self.network = self.enterContext(patch(
            "urllib.request.urlopen", side_effect=AssertionError("offline fixtures only")))
        migration.start_session(SUITE, self.seed, condition="baseline", solver_id="method-fixture")
        for task in self.tokens:
            request = migration.task_request(self.seed, task)
            migration.submit_attempt(self.seed, {
                "task_id": task, "request_sha256": request["request_sha256"],
                "proof": "by exact fixture_original_" + task,
                "bridge": "Synthetic fixture; no actual Lean verification"})
        self.origin = inventory_baseline([self.seed], ["d01", "d03"])
        self.origin_report = {"status": "completed", "generation_usage": {
            "input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
            "actual_provider_calls": 2, "requested_model": "synthetic-model"}
        self.enterContext(patch.object(reuse, "model_inventory",
                                      return_value=(self.origin_report, self.origin)))
        card = json.loads(reuse.CARD.read_text())
        card["origin"]["proof_sha256"] = self.origin["tasks"][1]["selected"]["proof_sha256"]
        self.card = self.work / "method.json"
        self.card.write_bytes(migration.canonical(card))
        self.enterContext(patch.object(reuse, "CARD", self.card))

    def verify_fixture(self, frozen, request, source, artifact, **kwargs):
        if self.verifier_status == "interrupt":
            raise KeyboardInterrupt("Synthetic interrupted Lean verification")
        if self.verifier_status != "verified":
            return {"status": self.verifier_status, "trace": [], "audit": None,
                    "failure": {"kind": "fixture_failure", "message": self.verifier_status}}
        return {"status": "verified", "trace": [], "audit": {
            "lean_version": frozen["manifest"]["lean_version"], "module": "Proof",
            "imported_modules": [row["module"] for row in request["sources"]],
            "package_declarations": [], "axioms_used": [],
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 20,
                         "source": {"signature_tokens": 6, "body_tokens": 4,
                                    "declaration_tokens": 11}}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens[request["task"]["id"]],
                         "source_utf8_bytes": len(source.encode("utf-8"))}]}}

    def prepare(self):
        return reuse.prepare(self.model_root, self.root)

    def complete(self):
        self.prepare()
        reuse.execute_next(self.root)
        self.tokens["d04"] = 120
        return reuse.execute_next(self.root)

    def assert_no_broader_claims(self, report):
        self.assertEqual(report["new_model_calls"], 0)
        self.assertEqual(report["new_lean_package_source_tokens"], 0)
        self.assertIsNone(report["generation_usage"])
        self.assertEqual(report["source_model_usage"], self.origin_report["generation_usage"])
        self.network.assert_not_called()

    def test_prepare_reconstructs_other_goals_without_executing_the_method(self):
        before = self.verifier.call_count
        result = self.prepare()
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["initial_source_tokens"], 380)
        self.assertEqual(result["selected_source_tokens"], 380)
        self.assertEqual(result["counts"]["scans"], 0)
        self.assertEqual(list((self.root / "generated").iterdir()), [])
        inventory = json.loads((self.root / "inventory.json").read_text())
        self.assertEqual(inventory, inventory_baseline([self.seed], list(TASKS)))
        self.assertEqual(self.verifier.call_count, before)
        self.assertEqual(result, reuse.report(self.root))
        self.assert_no_broader_claims(result)

    def test_complete_keeps_inapplicable_goal_and_checks_only_the_new_candidate(self):
        self.prepare()
        before = self.verifier.call_count
        retained = reuse.execute_next(self.root)
        self.assertEqual(retained["counts"]["retained"], 1)
        self.assertEqual(self.verifier.call_count, before)
        self.tokens["d04"] = 120
        result = reuse.execute_next(self.root)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["initial_source_tokens"], 380)
        self.assertEqual(result["selected_source_tokens"], 270)
        self.assertEqual(result["counts"], {"scans": 2, "candidates": 1, "retained": 1,
                                            "verified": 1, "rejected": 0, "incomplete": 0})
        self.assertEqual(self.verifier.call_count, before + 1)
        first = migration.unseal(self.root / "generated/0001.json")
        second = migration.unseal(self.root / "generated/0002.json")
        self.assertEqual(first["response"]["action"], "retain")
        self.assertEqual(second["response"]["action"], "candidate")
        self.assertEqual(first["request"]["task_id"], "d02")
        self.assertEqual(second["request"]["task_id"], "d04")
        self.assertEqual(result, reuse.report(self.root))
        self.assert_no_broader_claims(result)
        with self.assertRaises(CorpusError):
            reuse.execute_next(self.root)

    def test_equal_and_longer_verified_candidate_never_replace_the_incumbent(self):
        for tokens in (230, 231):
            with self.subTest(tokens=tokens):
                self.root = self.work / ("reuse-" + str(tokens))
                self.prepare()
                reuse.execute_next(self.root)
                self.tokens["d04"] = tokens
                result = reuse.execute_next(self.root)
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["selected_source_tokens"], 380)
                self.assertEqual(result["counts"]["verified"], 1)

    def test_rejected_candidate_preserves_the_original_and_failure_record(self):
        self.prepare()
        reuse.execute_next(self.root)
        self.verifier_status = "rejected"
        result = reuse.execute_next(self.root)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["selected_source_tokens"], 380)
        self.assertEqual(result["counts"]["rejected"], 1)
        self.assertEqual(result, reuse.report(self.root))

    def test_interrupted_verification_does_not_restore_a_slot(self):
        self.prepare()
        reuse.execute_next(self.root)
        self.verifier_status = "interrupt"
        with self.assertRaises(KeyboardInterrupt):
            reuse.execute_next(self.root)
        generated = (self.root / "generated/0002.json").read_bytes()
        before = self.verifier.call_count
        self.assertEqual(reuse.report(self.root)["status"], "stopped")
        with self.assertRaises(CorpusError):
            reuse.execute_next(self.root)
        self.assertEqual(self.verifier.call_count, before)
        self.assertEqual((self.root / "generated/0002.json").read_bytes(), generated)

    def test_interruption_after_generation_prevents_a_second_submission(self):
        self.prepare()
        before = self.verifier.call_count
        with patch.object(reuse.search, "submit", side_effect=KeyboardInterrupt("fixture interruption")), \
                self.assertRaises(KeyboardInterrupt):
            reuse.execute_next(self.root)
        generated = (self.root / "generated/0001.json").read_bytes()
        result = reuse.report(self.root)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["counts"]["incomplete"], 1)
        with self.assertRaises(CorpusError):
            reuse.execute_next(self.root)
        self.assertEqual(self.verifier.call_count, before)
        self.assertEqual((self.root / "generated/0001.json").read_bytes(), generated)

    def test_card_and_executable_setup_are_fully_charged_once(self):
        result = self.complete()
        setup = {"method/" + name: (self.root / "setup" / name).read_bytes()
                 for name in ("method.json", "renderer.py", "controller.py")}
        self.assertEqual(result["method_setup"]["card_only"],
                         measure_sources({"method/method.json": setup["method/method.json"]}))
        self.assertEqual(result["method_setup"]["executable"], measure_sources(setup))
        before = {task + "/Proof": (self.seed / "attempts" / task / "001/Proof.lean").read_bytes()
                  for task in TASKS}
        child_plan = migration.unseal(self.root / "search/plan.json")
        candidate = self.root / "search" / child_plan["schedule"][1]["session"] / "attempts/d04/001/Proof.lean"
        after = {**before, "d04/Proof": candidate.read_bytes()}
        self.assertEqual(result["proof_documents"]["baseline"], measure_sources(before))
        self.assertEqual(result["proof_documents"]["selected"], measure_sources(after))
        self.assertEqual(result["combined_documents"]["selected_plus_card"],
                         measure_sources({**after, "method/method.json": setup["method/method.json"]}))
        self.assertEqual(result["combined_documents"]["selected_plus_executable"],
                         measure_sources({**after, **setup}))
        for field in ("ai_card_usability_measured", "automatic_method_discovery", "fair_model_comparison",
                      "broad_baseline_prepared", "causal_theory_attribution", "held_out_evaluation"):
            self.assertIs(result["evidence"][field], False)

    def test_generated_response_tampering_is_rejected_even_with_a_fresh_local_seal(self):
        self.complete()
        path = self.root / "generated/0002.json"
        value = migration.unseal(path)
        value["response"]["proof"] += "\n-- forged output\n"
        path.write_bytes(migration.canonical(migration.seal(value)))
        with self.assertRaises(CorpusError):
            reuse.report(self.root)

    def test_generated_request_binding_cannot_be_replaced(self):
        self.complete()
        path = self.root / "generated/0002.json"
        value = migration.unseal(path)
        value["request"]["task_id"] = "d02"
        path.write_bytes(migration.canonical(migration.seal(value)))
        with self.assertRaises(CorpusError):
            reuse.report(self.root)

    def test_missing_generated_record_cannot_restore_a_completed_slot(self):
        self.complete()
        (self.root / "generated/0002.json").unlink()
        before = self.verifier.call_count
        with self.assertRaises(CorpusError):
            reuse.report(self.root)
        with self.assertRaises(CorpusError):
            reuse.execute_next(self.root)
        self.assertEqual(self.verifier.call_count, before)
        self.assertFalse((self.root / "generated/0002.json").exists())

    def test_changed_origin_or_method_card_invalidates_replay(self):
        self.prepare()
        original = self.card.read_bytes()
        self.card.write_bytes(original + b"\n")
        with self.assertRaises(CorpusError):
            reuse.report(self.root)
        self.card.write_bytes(original)
        self.origin_report["generation_usage"]["input_tokens"] += 1
        with self.assertRaises(CorpusError):
            reuse.report(self.root)

    def test_setup_copy_tampering_is_rejected(self):
        self.prepare()
        for filename in ("method.json", "renderer.py", "controller.py"):
            path = self.root / "setup" / filename
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.subTest(filename=filename), self.assertRaises(CorpusError):
                reuse.report(self.root)
            path.write_bytes(original)

    def test_report_check_is_read_only_and_compares_exact_json_types(self):
        result = self.complete()
        path = self.work / "report.json"
        path.write_bytes(migration.canonical(result))
        before = self.verifier.call_count
        reuse.check_report(path, self.root)
        self.assertEqual(self.verifier.call_count, before)
        for value in (True, 1.0):
            changed = {**result, "schema_version": value}
            path.write_bytes(migration.canonical(changed))
            with self.subTest(value=value), self.assertRaises(CorpusError):
                reuse.check_report(path, self.root)
        self.network.assert_not_called()

    def test_cli_prepares_executes_and_replays_with_exclusive_output(self):
        output = self.work / "cli-report.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(reuse.main(["prepare", "--model-root", str(self.model_root),
                                         "--root", str(self.root)]), 0)
            self.assertEqual(reuse.main(["next", "--root", str(self.root)]), 0)
            self.tokens["d04"] = 120
            self.assertEqual(reuse.main(["next", "--root", str(self.root),
                                         "--output", str(output)]), 0)
            self.assertEqual(reuse.main(["status", "--root", str(self.root),
                                         "--check", str(output)]), 0)
            before = output.read_bytes()
            self.assertEqual(reuse.main(["status", "--root", str(self.root),
                                         "--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
