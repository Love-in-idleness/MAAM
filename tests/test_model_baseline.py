"""Synthetic provider receipts and explicit Lean fixtures; no live credentials."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError
from maam.baseline import inventory_baseline
from maam.migration import submit_attempt, start_session, task_request, unseal
from scripts import control_model_baseline as model


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/metered_transfer_v1/suite.json"
KEY = "sk-synthetic-baseline-" + "Z" * 32
PROOF = "by exact fixture_existing_certificate"
RETAIN = {"action": "retain", "proof": "", "reason": "No shorter proof found in this bounded attempt."}


class ModelBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.key_file = self.work / "private-key-outside-run.txt"
        self.tokens = 100
        self.verification_calls = 0
        self.before_verify = None
        self.payloads = []
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.verify).start()
        self.key_reader = patch.object(model, "read_private_key", return_value=KEY).start()
        patch.object(model, "check_lean", return_value=None).start()
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("No network in fixtures")).start()
        self.addCleanup(patch.stopall)

    def verify(self, frozen, request, source, artifact, **kwargs):
        self.verification_calls += 1
        if self.before_verify:
            self.before_verify()
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50}],
            "sources": [{"module": "Proof", "source_tokens": self.tokens}]}}

    def prepared(self, *, name="case", tasks=("d01", "d03")):
        seed = self.work / (name + "-seed")
        start_session(SUITE, seed, condition="baseline", solver_id="mocked-lean-fixture")
        self.tokens = 100
        for task in tasks:
            request = task_request(seed, task)
            submit_attempt(seed, {"task_id": task, "request_sha256": request["request_sha256"],
                                  "proof": PROOF, "bridge": "Fixture only; Lean is mocked"})
        inventory = self.work / (name + "-inventory.json")
        inventory.write_text(json.dumps(inventory_baseline([seed], list(tasks))))
        root = self.work / name
        key_reads = self.key_reader.call_count
        result = model.prepare(inventory, root, verify_commit=False)
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["calls"], [])
        self.assertEqual(result["actual_provider_calls"], 0)
        self.assertEqual(result, model.report(root))
        self.assertEqual(self.key_reader.call_count, key_reads)
        return root

    @staticmethod
    def wire(output=RETAIN, *, usage=True, reported_model=None, status="completed",
             request_id="request-fixture"):
        value = {"id": "response_fixture_unique", "model": reported_model or model.MODEL,
                 "status": status, "output": [{"type": "message", "content": [
                     {"type": "output_text", "text": json.dumps(output)}]}]}
        if usage:
            value["usage"] = (usage if isinstance(usage, dict) else {
                "input_tokens": 100, "output_tokens": 40, "total_tokens": 140,
                "output_tokens_details": {"reasoning_tokens": 20}})
        return 200, request_id, json.dumps(value).encode()

    def execute(self, root, output=RETAIN, **kwargs):
        def respond(key, payload, timeout):
            self.assertEqual(key, KEY)
            self.payloads.append(copy.deepcopy(payload))
            return self.wire(output, **kwargs)
        with patch.object(model.deepseek, "response", side_effect=respond):
            return model.execute_next(root, self.key_file)

    def assert_terminal(self, root):
        with patch.object(model.deepseek, "response") as provider, self.assertRaises(CorpusError):
            model.execute_next(root, self.key_file)
        provider.assert_not_called()

    def assert_no_secret_archived(self, root):
        for path in root.rglob("*"):
            if path.is_file():
                for secret in (KEY, KEY[:20], str(self.key_file)):
                    self.assertNotIn(secret.encode(), path.read_bytes(), str(path))

    def test_two_retains_are_metered_per_goal_without_lean_or_package_sources(self):
        root = self.prepared()
        before = self.verification_calls
        first = self.execute(root)
        self.assertEqual(first["status"], "in_progress")
        result = self.execute(root)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["actual_provider_calls"], 2)
        self.assertEqual(result["generation_usage"], {"input_tokens": 200, "output_tokens": 80,
                                                      "total_tokens": 280})
        self.assertEqual((result["initial_source_tokens"], result["selected_source_tokens"]), (200, 200))
        self.assertEqual(self.verification_calls, before)
        self.assertEqual(len(result["calls"]), 2)
        self.assertGreater(float(result["estimated_cost_usd"]), 0)
        for payload, own, other in zip(self.payloads, ("Tasks.D01", "Tasks.D03"), ("Tasks.D03", "Tasks.D01")):
            content = json.dumps(payload)
            self.assertIn(own, content)
            self.assertNotIn(other, content)
            self.assertNotIn("import Candidate", content)
            self.assertNotIn("import Extension", content)
            self.assertNotIn("theorem r01", content)
            self.assertNotIn(KEY, content)
            self.assertEqual(payload["model"], model.MODEL)
            self.assertEqual(payload["max_output_tokens"], model.OUTPUT_LIMIT)
            self.assertIs(payload["store"], False)
            self.assertFalse(payload.get("tools"))
        for flag in ("baseline_search_complete", "package_attribution_ready", "globally_shortest",
                     "model_search_verified", "definition_optimization_performed"):
            self.assertIs(result["search_report"][flag], False)
        self.assertEqual(result, model.report(root))
        self.assert_terminal(root)
        self.assert_no_secret_archived(root)
        self.network.assert_not_called()

    def test_receipt_is_durable_before_candidate_verification_and_longer_is_retained(self):
        root = self.prepared(tasks=("d01",))
        before = self.verification_calls
        self.tokens = 120
        self.before_verify = lambda: self.assertTrue((root / "calls/01/receipt.json").is_file())
        result = self.execute(root, {"action": "candidate", "proof": "by exact fixture_alternative",
                                     "reason": "Synthetic candidate"})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.verification_calls, before + 1)
        self.assertEqual(result["selected_source_tokens"], 100)
        self.assertFalse(result["search_report"]["attempts"][0]["replaced"])
        self.assertEqual(result, model.report(root))
        self.assert_no_secret_archived(root)

    def test_strictly_shorter_verified_candidate_is_selected(self):
        root = self.prepared(tasks=("d01",))
        self.tokens = 80
        result = self.execute(root, {"action": "candidate", "proof": "by exact shorter_fixture",
                                     "reason": "Synthetic candidate"})
        self.assertEqual(result["selected_source_tokens"], 80)
        self.assertTrue(result["search_report"]["attempts"][0]["replaced"])
        self.assert_terminal(root)

    def test_unknown_usage_stops_further_calls_and_remains_unknown(self):
        root = self.prepared()
        result = self.execute(root, usage=False)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["actual_provider_calls"], 1)
        self.assertIsNone(result["generation_usage"])
        self.assertIsNone(result["estimated_cost_usd"])
        self.assertEqual(result["selected_source_tokens"], 200)
        self.assert_terminal(root)

    def test_over_limit_usage_stops_without_replacing_the_observed_usage(self):
        for name, inputs, outputs in (("input-limit", model.INPUT_LIMIT + 1, 40),
                                      ("output-limit", 100, model.OUTPUT_LIMIT + 1)):
            with self.subTest(name=name):
                root = self.prepared(name=name)
                usage = {"input_tokens": inputs, "output_tokens": outputs,
                         "total_tokens": inputs + outputs}
                result = self.execute(root, usage=usage)
                self.assertEqual(result["status"], "stopped")
                self.assertEqual(result["generation_usage"], usage)
                self.assertEqual(result["actual_provider_calls"], 1)
                self.assert_terminal(root)

    def test_request_identifier_echoing_credential_prefix_is_scrubbed(self):
        root = self.prepared()
        self.execute(root, request_id="header-" + KEY[:20] + "-echo")
        receipt = unseal(root / "calls/01/receipt.json")
        self.assertIsNone(receipt["request_id"])
        self.assert_no_secret_archived(root)

    def test_malformed_output_keeps_known_usage_and_stops_without_repair(self):
        root = self.prepared()
        result = self.execute(root, {"action": "candidate", "proof": "", "reason": "Invalid fixture"})
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["generation_usage"], {"input_tokens": 100, "output_tokens": 40,
                                                      "total_tokens": 140})
        self.assertEqual(result["actual_provider_calls"], 1)
        self.assertGreater(float(result["estimated_cost_usd"]), 0)
        self.assert_terminal(root)

    def test_transport_failure_consumes_slot_and_never_retries(self):
        root = self.prepared()
        with patch.object(model.deepseek, "response", side_effect=OSError("provider_http_503")) as provider:
            result = model.execute_next(root, self.key_file)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["actual_provider_calls"], 1)
        self.assertIsNone(result["generation_usage"])
        self.assert_terminal(root)
        self.assert_no_secret_archived(root)

    def test_model_mismatch_or_truncation_stops_with_metering_preserved(self):
        for name, values in (("mismatch", {"reported_model": "unexpected-model"}),
                             ("truncated", {"status": "incomplete"})):
            with self.subTest(name=name):
                root = self.prepared(name=name)
                result = self.execute(root, **values)
                self.assertEqual(result["status"], "stopped")
                self.assertEqual(result["actual_provider_calls"], 1)
                self.assertIsNotNone(result["generation_usage"])
                self.assert_terminal(root)

    def test_response_tampering_is_rejected_before_new_call(self):
        root = self.prepared()
        self.execute(root)
        candidates = [path for path in (root / "calls/01").iterdir()
                      if path.is_file() and b'response_fixture_unique' in path.read_bytes()]
        self.assertTrue(candidates)
        raw = next((path for path in candidates if path.name != "receipt.json"), candidates[0])
        raw.write_bytes(raw.read_bytes().replace(b'response_fixture_unique', b'response_fixture_tampered'))
        with self.assertRaises(CorpusError):
            model.report(root)
        self.assert_terminal(root)

    def test_interrupted_call_reservation_cannot_be_reused(self):
        root = self.prepared()
        with patch.object(model.deepseek, "response", side_effect=KeyboardInterrupt("Fixture interruption")):
            with self.assertRaises(KeyboardInterrupt):
                model.execute_next(root, self.key_file)
        result = model.report(root)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["actual_provider_calls"], 1)
        self.assertIsNone(result["generation_usage"])
        self.assert_terminal(root)

    def test_interrupted_lean_keeps_the_completed_provider_receipt(self):
        root = self.prepared()

        def interrupt():
            self.assertTrue((root / "calls/01/receipt.json").is_file())
            raise KeyboardInterrupt("Fixture interrupted Lean")

        self.before_verify = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.execute(root, {"action": "candidate", "proof": "by exact fixture_candidate",
                                "reason": "Synthetic candidate"})
        result = model.report(root)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["actual_provider_calls"], 1)
        self.assertEqual(result["generation_usage"]["total_tokens"], 140)
        self.assertEqual(result["selected_source_tokens"], 200)
        self.assert_terminal(root)


if __name__ == "__main__":
    unittest.main()
