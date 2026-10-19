"""Offline generation controls; real migration bookkeeping, mocked Lean and HTTP."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from maam import CorpusError
from maam import generation
from maam.migration import seal, session_report, submit_attempt, task_request, unseal

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "experiments/hom_kernel_migration/suite.json"


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.preflight = patch("maam.generation.check_lean").start()
        self.addCleanup(patch.stopall)
        self.verifier = patch("maam.migration.verify_attempt", side_effect=self.fake_verify).start()

    @staticmethod
    def fake_verify(frozen, request, source, artifact, **kwargs):
        if "_reject_" in source:
            return {"status": "rejected", "trace": [], "audit": None,
                    "failure": {"kind": "verification_failed", "stage": "compile:Proof",
                                "message": "fixture: unknown identifier _reject_"}}
        target = {"name": "Submission.solve", "expected": request["task"]["goal"],
                  "goal_preserved": True, "proof_expr_nodes": 50,
                  "source": {"body_tokens": 30, "signature_tokens": 4, "declaration_tokens": 35}}
        sources = [{"module": "Proof", "source_tokens": 40}]
        if request["condition"] == "treatment":
            sources.append({"module": "Candidate", "source_tokens": 80})
        return {"status": "verified", "trace": [],
                "audit": {"targets": [target], "sources": sources}}

    def prepare(self, name="run", tasks=None, **budget):
        config = {"model": "fixture-model", "sampling": {"reasoning_effort": "high"},
                  "budget": {"max_calls_per_task": 3, "max_output_tokens_per_call": 40,
                             "max_output_tokens_per_task": 100, "request_timeout_seconds": 10}}
        config["budget"].update(budget)
        path = self.root / name
        generation.prepare(SUITE, path, config, tasks or ["d01"])
        return path

    @staticmethod
    def response(proof="by trivial", bridge="fixture bridge", *, text=None,
                 tokens=7, usage=True, status="completed", output=None):
        value = {"id": "resp_fixture", "model": "fixture-model-revision", "status": status,
                 "output": output if output is not None else [{"type": "message", "content": [
                     {"type": "output_text", "text": text if text is not None else json.dumps(
                         {"proof": proof, "bridge": bridge})}]}]}
        if usage:
            value["usage"] = {"input_tokens": 11, "output_tokens": tokens, "total_tokens": 11 + tokens,
                              "input_tokens_details": {"cached_tokens": 3},
                              "output_tokens_details": {"reasoning_tokens": min(tokens, 2)}}
        return value

    @staticmethod
    def wire(value):
        return 200, "request-fixture", json.dumps(value).encode()

    def rows(self, root):
        path, record = generation.load_run(root)
        return generation.call_records(path, record)

    def test_success_stops_after_one_call_per_condition(self):
        root = self.prepare()
        transport = Mock(return_value=self.wire(self.response()))
        result = generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(result["calls"], 2)
        self.assertEqual([t["status"] for t in result["tasks"]], ["verified", "verified"])
        self.assertTrue(result["usage_complete"])
        generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 2)

    def test_repair_retains_failed_submission_and_feedback(self):
        root = self.prepare()
        sent = []

        def transport(payload, timeout):
            sent.append(copy.deepcopy(payload))
            return self.wire(self.response(proof="by _reject_" if len(sent) == 1 else "by trivial"))

        result = generation.run(root, transport=transport)
        self.assertEqual(result["calls"], 3)
        baseline = session_report(root / "baseline")["tasks"][0]
        self.assertEqual([a["status"] for a in baseline["attempts"]], ["rejected", "verified"])
        history = json.loads(sent[1]["input"])["previous_attempts"]
        self.assertEqual(len(history), 1)
        self.assertIn("_reject_", history[0]["output"])
        self.assertIn("unknown identifier", history[0]["feedback"]["message"])
        self.assertEqual(json.loads(sent[2]["input"])["previous_attempts"], [])

    def test_history_and_sources_are_isolated_by_task_and_condition(self):
        root = self.prepare(tasks=["d01", "d02"])
        seen = {}
        sent = []

        def transport(payload, timeout):
            content = json.loads(payload["input"])
            request = content["request"]
            key = (request["condition"], request["task"]["id"])
            count = seen.get(key, 0)
            seen[key] = count + 1
            marker = "_".join(key)
            self.assertEqual(len(content["previous_attempts"]), count)
            for prior in content["previous_attempts"]:
                self.assertIn(marker, prior["output"])
                for other in seen:
                    if other != key:
                        self.assertNotIn("_".join(other), prior["output"])
            expected = ["Base", request["task"]["module"]]
            if key[0] == "treatment":
                expected.append("Candidate")
            self.assertEqual([s["module"] for s in request["sources"]], expected)
            self.assertFalse(payload["store"])
            self.assertNotIn("previous_response_id", payload)
            sent.append(key)
            return self.wire(self.response(proof="by " + marker + (" _reject_" if count == 0 else "")))

        result = generation.run(root, transport=transport)
        self.assertEqual(result["calls"], 8)
        self.assertEqual(sent, [("baseline", "d01")] * 2 + [("treatment", "d01")] * 2
                         + [("treatment", "d02")] * 2 + [("baseline", "d02")] * 2)

    def test_malformed_output_is_charged_before_repair(self):
        root = self.prepare()
        transport = Mock(side_effect=[self.wire(self.response(text="not JSON", tokens=13)),
                                     self.wire(self.response()), self.wire(self.response())])
        result = generation.run(root, transport=transport)
        self.assertEqual(result["tasks"][0]["observed_output_tokens"], 20)
        self.assertEqual(self.rows(root)[0]["result"]["status"], "invalid_response")
        self.assertEqual(len(session_report(root / "baseline")["tasks"][0]["attempts"]), 1)

    def test_refusal_preserves_usage_without_lean_submission(self):
        root = self.prepare(max_calls_per_task=1)
        refusal = self.response(tokens=9, output=[{"type": "message", "content": [
            {"type": "refusal", "refusal": "fixture refusal"}]}])
        result = generation.run(root, transport=Mock(return_value=self.wire(refusal)))
        self.assertEqual([t["observed_output_tokens"] for t in result["tasks"]], [9, 9])
        self.assertTrue(all(r["result"]["status"] == "invalid_response" for r in self.rows(root)))
        self.verifier.assert_not_called()

    def test_incomplete_output_preserves_usage_without_submission(self):
        root = self.prepare(max_calls_per_task=1)
        response = self.response(status="incomplete", tokens=17)
        response["incomplete_details"] = {"reason": "max_output_tokens"}
        result = generation.run(root, transport=Mock(return_value=self.wire(response)))
        self.assertEqual([t["charged_output_allowance"] for t in result["tasks"]], [17, 17])
        self.assertTrue(all(r["result"]["status"] == "provider_incomplete_or_error" for r in self.rows(root)))
        self.verifier.assert_not_called()

    def test_missing_usage_stops_further_calls_and_remains_unknown(self):
        root = self.prepare()
        transport = Mock(return_value=self.wire(self.response(usage=False)))
        result = generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 1)
        self.assertFalse(result["usage_complete"])
        self.assertEqual(result["stop"]["reason"], "unknown_usage_or_interrupted_call")
        task = result["tasks"][0]
        self.assertIsNone(task["observed_output_tokens"])
        self.assertEqual(task["known_output_tokens_lower_bound"], 0)
        self.assertEqual(task["charged_output_allowance"], 40)

    def test_invalid_usage_stops_without_treating_it_as_zero(self):
        invalid = [{"input_tokens": 1, "output_tokens": True, "total_tokens": 2},
                   {"input_tokens": 11, "output_tokens": 7, "total_tokens": 99},
                   {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18,
                    "output_tokens_details": {"reasoning_tokens": 8}},
                   {"input_tokens": -1, "output_tokens": 7, "total_tokens": 6}]
        for number, usage in enumerate(invalid):
            with self.subTest(usage=usage):
                root = self.prepare(name=f"usage-{number}")
                response = self.response()
                response["usage"] = usage
                transport = Mock(return_value=self.wire(response))
                result = generation.run(root, transport=transport)
                self.assertEqual(transport.call_count, 1)
                self.assertIsNone(result["tasks"][0]["observed_output_tokens"])
                self.assertEqual(result["tasks"][0]["charged_output_allowance"], 40)

    def test_transport_timeout_is_retained_and_does_not_retry(self):
        root = self.prepare()
        transport = Mock(side_effect=TimeoutError("fixture timeout"))
        result = generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 1)
        row = self.rows(root)[0]
        self.assertEqual(row["result"]["feedback"]["kind"], "transport_error")
        self.assertIsNone(row["result"]["usage"])
        self.assertTrue((root / "calls/0001/response.bin").exists())
        self.assertEqual(result["tasks"][0]["charged_output_allowance"], 40)

    def test_interruption_before_response_consumes_reservation_and_stops_resume(self):
        root = self.prepare()
        with self.assertRaises(KeyboardInterrupt):
            generation.run(root, transport=Mock(side_effect=KeyboardInterrupt))
        self.assertTrue((root / "reservations/0001.json").exists())
        self.assertIsNone(self.rows(root)[0]["result"])
        transport = Mock(side_effect=AssertionError("must not retry interrupted HTTP"))
        result = generation.run(root, transport=transport)
        transport.assert_not_called()
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["tasks"][0]["charged_output_allowance"], 40)
        self.assertEqual(result["stop"]["reason"], "unknown_usage_or_interrupted_call")

    def test_interruption_during_lean_preserves_usage_and_incomplete_attempt(self):
        root = self.prepare()
        with patch("maam.migration.verify_attempt", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                generation.run(root, transport=Mock(return_value=self.wire(self.response(tokens=9))))
        before = generation.report(root)
        self.assertEqual(before["calls"], 1)
        self.assertEqual(before["tasks"][0]["known_output_tokens_lower_bound"], 9)
        attempt = session_report(root / "baseline")["tasks"][0]["attempts"][0]
        self.assertEqual(attempt["status"], "incomplete")
        transport = Mock(side_effect=AssertionError("must not rerun after interrupted Lean"))
        after = generation.run(root, transport=transport)
        transport.assert_not_called()
        self.assertEqual(after["calls"], 1)
        self.assertEqual(after["status"], "stopped")

    def test_output_allowance_is_clipped_to_remaining_budget(self):
        root = self.prepare(max_output_tokens_per_call=32, max_output_tokens_per_task=40)
        allowances = []

        def transport(payload, timeout):
            allowance = payload["max_output_tokens"]
            allowances.append(allowance)
            return self.wire(self.response(text="malformed", tokens=18 if allowance == 32 else 22))

        result = generation.run(root, transport=transport)
        self.assertEqual(allowances, [32, 22, 32, 22])
        self.assertEqual([t["observed_output_tokens"] for t in result["tasks"]], [40, 40])
        self.assertEqual([t["status"] for t in result["tasks"]], ["output_budget_exhausted"] * 2)

    def test_call_budget_includes_invalid_responses(self):
        root = self.prepare(max_calls_per_task=2)
        transport = Mock(return_value=self.wire(self.response(text="malformed", tokens=1)))
        result = generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 4)
        self.assertEqual([t["status"] for t in result["tasks"]], ["call_budget_exhausted"] * 2)
        self.assertEqual([t["observed_output_tokens"] for t in result["tasks"]], [2, 2])
        self.verifier.assert_not_called()

    def test_reasoning_usage_is_not_added_twice_and_revision_is_not_certified(self):
        root = self.prepare()
        result = generation.run(root, transport=Mock(return_value=self.wire(self.response(tokens=9))))
        self.assertEqual([t["observed_output_tokens"] for t in result["tasks"]], [9, 9])
        self.assertEqual(result["reported_models"], ["fixture-model-revision"])
        self.assertFalse(result["scope"]["exact_model_revision_verified"])
        self.assertFalse(result["scope"]["held_out_evaluation"])
        self.assertFalse(result["scope"]["fair_model_performance_claim"])
        self.assertFalse(result["scope"]["training_eligible"])

    def test_oversize_proof_is_rejected_but_generation_is_charged(self):
        root = self.prepare(max_calls_per_task=1)
        response = self.response(proof="x" * 32769, tokens=12)
        result = generation.run(root, transport=Mock(return_value=self.wire(response)))
        self.assertEqual([t["observed_output_tokens"] for t in result["tasks"]], [12, 12])
        self.assertTrue(all(r["result"]["status"] == "invalid_response" for r in self.rows(root)))
        self.assertTrue(all("response-size" in r["result"]["feedback"]["message"] for r in self.rows(root)))
        self.verifier.assert_not_called()
        self.assertEqual(list((root / "baseline/reservations").iterdir()), [])

    def test_reservation_response_result_and_proof_tampering_are_rejected(self):
        for number, relative in enumerate(("reservations/0001.json", "calls/0001/pending.json",
                                           "calls/0001/response.bin", "calls/0001/result.json",
                                           "baseline/attempts/d01/001/submission.json",
                                           "baseline/attempts/d01/001/Proof.lean")):
            with self.subTest(file=relative):
                root = self.prepare(name=f"tamper-{number}")
                generation.run(root, transport=Mock(return_value=self.wire(self.response())))
                path = root / relative
                if path.suffix == ".json":
                    value = json.loads(path.read_text())
                    value["tampered"] = True
                    path.write_text(json.dumps(value))
                else:
                    path.write_bytes(path.read_bytes() + b"tampered")
                with self.assertRaises(CorpusError):
                    generation.report(root)
        # Even an internally resealed usage edit must disagree with the raw reply.
        root = self.prepare(name="resealed-usage")
        generation.run(root, transport=Mock(return_value=self.wire(self.response())))
        for name in ("receipt.json", "result.json"):
            path = root / "calls/0001" / name
            value = unseal(path)
            value["usage"]["output_tokens"] += 1
            value["usage"]["total_tokens"] += 1
            path.write_text(json.dumps(seal(value)))
        with self.assertRaisesRegex(CorpusError, "metering|response"):
            generation.report(root)

    def test_deleted_unverified_call_artifacts_do_not_restore_budget(self):
        root = self.prepare(max_calls_per_task=1)
        path, record = generation.load_run(root)
        state = generation.report(root)["tasks"][0]
        item = {key: state[key] for key in ("condition", "task_id")}
        generation.generate_one(path, record, item, state,
                                Mock(return_value=self.wire(self.response(text="malformed"))), "lean",
                                "injected_test_transport")
        shutil.rmtree(root / "calls/0001")
        state = generation.report(root)
        self.assertEqual(state["calls"], 1)
        self.assertIsNone(state["tasks"][0]["observed_output_tokens"])
        self.assertEqual(state["tasks"][0]["charged_output_allowance"], 40)
        self.assertTrue((root / "reservations/0001.json").exists())
        transport = Mock(side_effect=AssertionError("deleted artifacts cannot restore a call"))
        generation.run(root, transport=transport)
        transport.assert_not_called()

    def test_provider_overrun_is_preserved_as_a_stop_event(self):
        root = self.prepare(max_output_tokens_per_call=32, max_output_tokens_per_task=40)
        transport = Mock(return_value=self.wire(self.response(tokens=41)))
        result = generation.run(root, transport=transport)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result["stop"]["reason"], "provider_exceeded_output_limit")
        self.assertEqual(result["tasks"][0]["observed_output_tokens"], 41)
        self.assertEqual(self.rows(root)[0]["result"]["status"], "provider_exceeded_output_limit")
        self.verifier.assert_not_called()

    def test_config_rejects_invalid_budgets_and_sampling(self):
        valid = {"model": "fixture", "sampling": {}, "budget": {
            "max_calls_per_task": 1, "max_output_tokens_per_call": 16,
            "max_output_tokens_per_task": 16, "request_timeout_seconds": 1}}
        for field, value in (("max_calls_per_task", True), ("max_output_tokens_per_call", 15),
                             ("max_output_tokens_per_task", 0), ("request_timeout_seconds", -1)):
            with self.subTest(field=field):
                config = copy.deepcopy(valid)
                config["budget"][field] = value
                with self.assertRaises(CorpusError):
                    generation.validate_config(config)
        config = copy.deepcopy(valid)
        config["sampling"] = {"reasoning_effort": "high", "temperature": 0.5}
        with self.assertRaises(CorpusError):
            generation.validate_config(config)

    def test_prepare_rejects_reserved_tasks_and_tampered_protocol(self):
        config = {"model": "fixture", "sampling": {}, "budget": {
            "max_calls_per_task": 1, "max_output_tokens_per_call": 16,
            "max_output_tokens_per_task": 16, "request_timeout_seconds": 1}}
        with self.assertRaisesRegex(CorpusError, "development"):
            generation.prepare(SUITE, self.root / "reserved", config, ["r01"])
        root = self.prepare()
        value = json.loads((root / "generation.json").read_text())
        value["config"]["model"] = "another-model"
        (root / "generation.json").write_text(json.dumps(value))
        with self.assertRaises(CorpusError):
            generation.report(root)

    def test_provider_transport_uses_fixed_endpoint_and_rejects_redirects(self):
        response = MagicMock()
        response.code = 200
        response.headers.get.return_value = "request-fixture"
        response.read.return_value = b'{"status":"completed"}'
        response.__enter__.return_value = response
        opener = Mock()
        opener.open.return_value = response
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-not-a-real-secret"}), \
                patch("maam.generation.build_opener", return_value=opener) as build:
            actual = generation.openai_response({"model": "fixture"}, 9)
        self.assertEqual(actual, (200, "request-fixture", response.read.return_value))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, generation.ENDPOINT)
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-not-a-real-secret")
        self.assertEqual(json.loads(request.data), {"model": "fixture"})
        self.assertIsInstance(build.call_args.args[0], generation.NoRedirect)
        self.assertIsNone(generation.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.invalid"))

    def test_provider_credentials_do_not_enter_lean_or_archives(self):
        root = self.prepare()
        original = self.fake_verify

        def verify(*args, **kwargs):
            self.assertNotIn("OPENAI_API_KEY", os.environ)
            self.assertNotIn("UNRELATED_PRIVATE_TOKEN", os.environ)
            return original(*args, **kwargs)

        self.verifier.side_effect = verify
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-not-a-real-secret",
                                    "UNRELATED_PRIVATE_TOKEN": "private-fixture"}):
            generation.run(root, transport=Mock(return_value=self.wire(self.response())))
            self.assertEqual(os.environ["OPENAI_API_KEY"], "fixture-not-a-real-secret")
        for path in root.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"fixture-not-a-real-secret", path.read_bytes())
                self.assertNotIn(b"private-fixture", path.read_bytes())
        self.assertFalse(generation.report(root)["provider_usage_observed"])

    def test_missing_key_does_not_reserve_or_call_provider(self):
        root = self.prepare()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("maam.generation.openai_response") as transport:
            with self.assertRaisesRegex(CorpusError, "OPENAI_API_KEY"):
                generation.run(root)
        transport.assert_not_called()
        self.assertEqual(list((root / "reservations").iterdir()), [])

    def test_unrelated_lean_attempt_cannot_attach_to_interrupted_generation(self):
        root = self.prepare()
        with patch("maam.generation.submit_attempt", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                generation.run(root, transport=Mock(return_value=self.wire(self.response())))
        request = task_request(root / "baseline", "d01")
        submit_attempt(root / "baseline", {"task_id": "d01", "request_sha256": request["request_sha256"],
                                          "proof": "by exact True.intro", "bridge": "unrelated manual proof"})
        with self.assertRaisesRegex(CorpusError, "interrupted Lean attempt"):
            generation.report(root)

    def test_receipt_is_bound_to_its_interrupted_request(self):
        root = self.prepare()
        with patch("maam.generation.submit_attempt", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                generation.run(root, transport=Mock(return_value=self.wire(self.response())))
        before = generation.report(root)
        self.assertTrue(before["usage_complete"])
        path = root / "calls/0001/receipt.json"
        receipt = unseal(path)
        receipt["reservation_sha256"] = "0" * 64
        path.write_text(json.dumps(seal(receipt)))
        with self.assertRaisesRegex(CorpusError, "fingerprint"):
            generation.report(root)


class GenerationPreflightTests(unittest.TestCase):
    def test_custom_and_child_lean_versions_are_both_checked_without_credentials(self):
        expected = subprocess.CompletedProcess([], 0, "Lean (version 4.24.0, fixture)", "")
        wrong = subprocess.CompletedProcess([], 0, "Lean (version 4.28.0, fixture)", "")
        with patch("maam.generation.shutil.which", side_effect=["/custom/lean", "/child/lean"]), \
                patch("maam.generation.subprocess.run", side_effect=[expected, wrong]) as command, \
                patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-secret"}):
            with self.assertRaisesRegex(CorpusError, "frozen Lean"):
                generation.check_lean("/custom/lean", "4.24.0")
        self.assertEqual(command.call_count, 2)
        self.assertNotIn("OPENAI_API_KEY", command.call_args.kwargs["env"])

    def test_preflight_timeout_is_a_local_environment_error(self):
        with patch("maam.generation.shutil.which", return_value="/fake/lean"), \
                patch("maam.generation.subprocess.run", side_effect=subprocess.TimeoutExpired("lean", 30)):
            with self.assertRaisesRegex(CorpusError, "frozen Lean"):
                generation.check_lean("lean", "4.24.0")


if __name__ == "__main__":
    unittest.main()
