"""Offline metered-model to portfolio chain; all Lean audits are explicit fixtures."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, migration
from maam.baseline import inventory_baseline
from scripts import control_baseline_stability as stability
from scripts import control_model_baseline as model
from scripts import measure_model_portfolio as measurement


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"
KEY = "sk-synthetic-portfolio-" + "Q" * 32
TASKS = ["d01", "d03"]


class ModelPortfolioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.seed = self.work / "seed"
        self.model_root = self.work / "model"
        self.confirmation = self.work / "confirmation"
        self.treatment = self.work / "treatment"
        self.inventory_path = self.work / "exported-inventory.json"
        self.tokens = {"d01": 150, "d03": 217}
        self.verifier = self.enterContext(patch(
            "maam.migration.verify_attempt", side_effect=self.verify_fixture))
        self.key_reader = self.enterContext(patch.object(model, "read_private_key", return_value=KEY))
        self.enterContext(patch.object(model, "check_lean", return_value=None))
        self.network = self.enterContext(patch(
            "urllib.request.urlopen", side_effect=AssertionError("offline fixtures only")))
        migration.start_session(SUITE, self.seed, condition="baseline", solver_id="unit-fixture")
        for task in TASKS:
            self.submit(self.seed, task, "by exact fixture_original_" + task)
        self.seed_inventory = self.work / "seed-inventory.json"
        migration.save_new(self.seed_inventory, inventory_baseline([self.seed], TASKS))
        model.prepare(self.seed_inventory, self.model_root, verify_commit=False)
        self.tokens = {"d01": 42, "d03": 144}
        for task in TASKS:
            output = {"action": "candidate", "proof": "by exact fixture_shorter_" + task,
                      "reason": "Synthetic candidate; no actual model or Lean execution"}
            with patch.object(model.deepseek, "response", return_value=self.wire(output)):
                model.execute_next(self.model_root, self.work / "unused-private-key.txt")
        self.model_state, self.derived = measurement.model_inventory(self.model_root)
        migration.save_new(self.inventory_path, self.derived)
        self.confirm(self.inventory_path, self.confirmation)
        migration.start_session(SUITE, self.treatment, condition="treatment", solver_id="unit-fixture")
        self.tokens = {"d01": 90, "d03": 79}
        self.submit(self.treatment, "d03", "by exact fixture_historical_treatment")

    def verify_fixture(self, frozen, request, source, artifact, **kwargs):
        treatment = request["condition"] == "treatment"
        package = frozen["package"]["modules"] if treatment else []
        sources = [{"module": module, "source_tokens": 30 + index,
                    "source_utf8_bytes": len(frozen["blobs"][module])}
                   for index, module in enumerate(package)]
        sources.append({"module": "Proof", "source_tokens": self.tokens[request["task"]["id"]],
                        "source_utf8_bytes": len(source.encode("utf-8"))})
        return {"status": "verified", "trace": [], "audit": {
            "lean_version": frozen["manifest"]["lean_version"], "module": "Proof",
            "imported_modules": [row["module"] for row in request["sources"]],
            "package_declarations": frozen["package"]["declarations"] if treatment else [],
            "axioms_used": [], "targets": [{"name": "Submission.solve",
                "expected": request["task"]["goal"], "goal_preserved": True,
                "proof_expr_nodes": 20, "source": {
                    "signature_tokens": 6, "body_tokens": 4, "declaration_tokens": 11}}],
            "sources": sources}}

    @staticmethod
    def wire(output):
        body = {"id": "portfolio_response_fixture", "model": model.MODEL, "status": "completed",
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(output)}]}],
                "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140}}
        return 200, "portfolio_request_fixture", json.dumps(body).encode()

    def submit(self, root, task, proof):
        request = migration.task_request(root, task)
        return migration.submit_attempt(root, {
            "task_id": task, "request_sha256": request["request_sha256"], "proof": proof,
            "bridge": "Unit fixture; no actual Lean verification"})

    def confirm(self, inventory, root):
        stability.prepare(inventory, root)
        for _ in range(2):
            stability.execute_round(root)
        self.assertTrue(stability.report(root)["declared_method_preparation_complete"])

    def build(self):
        return measurement.build_report(
            self.model_root, self.inventory_path, self.confirmation, self.treatment)

    def test_model_export_reconstructs_exact_child_sessions_and_selected_certificates(self):
        child = self.model_root / "search"
        plan = migration.unseal(child / "plan.json")
        roots = [str(self.seed)] + [str(child / row["path"]) for row in plan["sessions"]]
        self.assertEqual(self.derived, inventory_baseline(roots, TASKS))
        self.assertEqual([row["root"] for row in self.derived["sessions"]], roots)
        self.assertEqual([row["selected"]["proof_source_tokens"] for row in self.derived["tasks"]],
                         [42, 144])
        self.assertEqual(self.model_state["status"], "completed")
        self.assertEqual(self.model_state["actual_provider_calls"], 2)
        self.assertIsNone(self.derived["generation_usage"])

    def test_retained_copied_incumbents_reconstruct_original_artifacts(self):
        for action, costs in (("retain", {"d01": 150, "d03": 217}),
                              ("candidate", {"d01": 150, "d03": 217}),
                              ("candidate", {"d01": 151, "d03": 218})):
            with self.subTest(action=action, costs=costs):
                root = self.work / (action + "-" + str(costs["d01"]))
                model.prepare(self.seed_inventory, root, verify_commit=False)
                self.tokens = costs
                for task in TASKS:
                    output = {"action": action,
                              "proof": "" if action == "retain" else "by exact fixture_other_" + task,
                              "reason": "Synthetic retain or non-shortening candidate"}
                    with patch.object(model.deepseek, "response", return_value=self.wire(output)):
                        model.execute_next(root, self.work / "unused-private-key.txt")
                observed, inventory = measurement.model_inventory(root)
                self.assertEqual(observed["selected_source_tokens"], 367)
                for row, chosen in zip(inventory["tasks"], observed["search_report"]["tasks"]):
                    self.assertEqual(Path(row["selected"]["artifact"]).parents[2], self.seed)
                    self.assertEqual(chosen["artifact"], "incumbents/" + row["task_id"])
                    self.assertEqual(row["selected"]["session_index"], 0)

    def test_complete_chain_preserves_generation_ledger_and_charges_package_once(self):
        before, key_reads = self.verifier.call_count, self.key_reader.call_count
        result = self.build()
        self.assertEqual(result["status"], "measured_model_seeded_retained_portfolio")
        ledger = result["baseline_generation_ledger"]
        self.assertEqual(ledger["latest_model_calls"], 2)
        self.assertEqual(ledger["latest_generation_usage"], self.model_state["generation_usage"])
        self.assertEqual(ledger["latest_estimated_cost_usd"], self.model_state["estimated_cost_usd"])
        self.assertIsNone(ledger["inherited_generation_usage"])
        self.assertEqual(ledger["inherited_generation_usage_status"], "unknown")
        comparison = result["comparison"]
        portfolio = comparison["retained_portfolio"]
        self.assertEqual([row["action"] for row in portfolio["tasks"]],
                         ["retain_original", "replace_with_shorter"])
        self.assertEqual(portfolio["original_goal_source_ledger"], {
            "baseline_tokens": 186, "selected_proof_tokens": 121, "gross_tokens_saved": 65,
            "package_tokens_charged_once": 61, "selected_including_package_tokens": 182,
            "net_tokens_saved": 4})
        self.assertEqual(comparison["historical_treatment"]["missing_alternatives"], ["d01"])
        for scope in comparison["scopes"].values():
            self.assertIn("retained_treatment", scope["conditions"])
        self.assertEqual(result["evidence"]["new_model_calls"], 0)
        self.assertIs(result["evidence"]["fresh_lean_verification"], False)
        self.assertIs(result["evidence"]["fair_model_comparison"], False)
        self.assertEqual(self.verifier.call_count, before)
        self.assertEqual(self.key_reader.call_count, key_reads)
        self.network.assert_not_called()

    def test_external_export_must_exactly_match_derived_inventory(self):
        for change in (lambda v: v["tasks"][0]["selected"].update(proof_source_tokens=41),
                       lambda v: v["sessions"].pop(),
                       lambda v: v.update(generation_usage=0),
                       lambda v: v.update(schema_version=True)):
            value = copy.deepcopy(self.derived)
            change(value)
            self.inventory_path.write_bytes(migration.canonical(value))
            with self.subTest(change=change), self.assertRaises(CorpusError):
                self.build()

    def test_confirmation_must_start_from_exact_export(self):
        wrong = self.work / "wrong-confirmation"
        self.confirm(self.seed_inventory, wrong)
        with self.assertRaises(CorpusError):
            measurement.build_report(self.model_root, self.inventory_path, wrong, self.treatment)

    def test_unfinished_confirmation_is_rejected(self):
        unfinished = self.work / "unfinished-confirmation"
        stability.prepare(self.inventory_path, unfinished)
        with self.assertRaises(CorpusError):
            measurement.build_report(self.model_root, self.inventory_path, unfinished, self.treatment)

    def test_unfinished_model_run_cannot_export_an_inventory(self):
        root = self.work / "unfinished-model"
        model.prepare(self.seed_inventory, root, verify_commit=False)
        with self.assertRaises(CorpusError):
            measurement.model_inventory(root)

    def test_provider_receipt_tampering_is_rejected(self):
        path = self.model_root / "calls/01/response.bin"
        path.write_bytes(path.read_bytes().replace(b'portfolio_response_fixture', b'tampered_response_fixture'))
        with self.assertRaises(CorpusError):
            self.build()

    def test_model_selected_summary_must_match_reconstructed_inventory(self):
        value = copy.deepcopy(self.model_state)
        value["search_report"]["tasks"][0]["proof_source_tokens"] += 1
        with patch.object(model, "report", return_value=value), self.assertRaises(CorpusError):
            measurement.model_inventory(self.model_root)

    def test_equal_and_longer_treatment_keep_optimized_baseline(self):
        path = self.treatment / "attempts/d03/001/result.json"
        original = migration.unseal(path)
        for tokens in (144, 145):
            value = copy.deepcopy(original)
            value["audit"]["sources"][-1]["source_tokens"] = tokens
            path.write_bytes(migration.canonical(migration.seal(value)))
            with self.subTest(tokens=tokens):
                portfolio = self.build()["comparison"]["retained_portfolio"]
                self.assertEqual([row["action"] for row in portfolio["tasks"]],
                                 ["retain_original", "retain_original"])
                self.assertEqual(portfolio["original_goal_source_ledger"]["selected_proof_tokens"], 186)
                self.assertEqual(portfolio["original_goal_source_ledger"]["package_tokens_charged_once"], 61)

    def test_strict_report_check_rejects_type_and_measurement_changes(self):
        path = self.work / "report.json"
        report = self.build()
        path.write_bytes(migration.canonical(report))
        args = (self.model_root, self.inventory_path, self.confirmation, self.treatment)
        measurement.check_report(path, *args)
        for value in (True, 1.0):
            changed = {**report, "schema_version": value}
            path.write_bytes(migration.canonical(changed))
            with self.subTest(value=value), self.assertRaises(CorpusError):
                measurement.check_report(path, *args)
        changed = copy.deepcopy(report)
        changed["baseline_generation_ledger"]["latest_model_calls"] += 1
        path.write_bytes(migration.canonical(changed))
        with self.assertRaises(CorpusError):
            measurement.check_report(path, *args)

    def test_cli_create_replay_and_exclusive_output(self):
        path = self.work / "report.json"
        common = ["--model-root", str(self.model_root), "--inventory", str(self.inventory_path),
                  "--baseline-root", str(self.confirmation), "--treatment-session", str(self.treatment)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(measurement.main(common + ["--output", str(path)]), 0)
            original = path.read_bytes()
            self.assertEqual(measurement.main(common + ["--check", str(path)]), 0)
            self.assertEqual(measurement.main(common + ["--output", str(path)]), 2)
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
