"""Constrained-construction controller checks with offline synthetic receipts."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from maam import CorpusError, construct_use as pilot
from maam import migration as mig
from maam.lean_sandbox import SandboxUnavailable
from maam.theory import digest


def synthetic_response(output="not JSON", *, usage=True, model="deepseek-flash"):
    body = {"id": "offline-construction-response", "model": model, "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": output}]}]}
    if usage:
        body["usage"] = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    return 200, "offline-construction-request", mig.canonical(body)


def unused_transport(*args):
    raise AssertionError("tests must patch the process boundary; no real transport is permitted")


class ConstructUseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="maam-construct-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.template = Path(cls.temporary.name) / "template"
        cls.prepared = pilot.prepare(pilot.FIXTURE, cls.template, verify_commit=False)
        try:
            evidence = pilot.preflight(cls.template)
        except SandboxUnavailable as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if evidence["status"] != "verified":
            raise AssertionError(evidence)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="maam-construct-case-")
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name) / "run"
        shutil.copytree(self.template, self.run)
        self.root, self.plan, self.frozen, self.guide = pilot._load(self.run)
        self.request = mig.task_request(self.run / "math", "c01")
        self.full_source = (self.run / "preflight/c01/Proof.lean").read_text()

    def call(self, response=None, *, verify=None):
        with patch.object(pilot, "bounded_response", return_value=response or synthetic_response()) as boundary:
            if verify is None:
                state = pilot.execute_next(self.run, None, transport=unused_transport)
            else:
                with (patch.object(pilot, "lean_sandbox", return_value=nullcontext("offline-lean")),
                      patch.object(mig, "verify_attempt", side_effect=verify)):
                    state = pilot.execute_next(self.run, None, transport=unused_transport)
        boundary.assert_called_once()
        return state

    def successful_verification(self, frozen, request, source, artifact, **kwargs):
        self.assertEqual(source, self.full_source)
        result = json.loads((self.run / "preflight/c01/verification.json").read_text())
        # Class preflight already checked this source; isolate state transitions here.
        result["trace"] = []
        return result

    def provider_plan(self):
        plan = mig.unseal(self.run / "plan.json")
        plan.update(execution_mode="provider", source_commit="synthetic-committed-inputs")
        (self.run / "plan.json").write_bytes(mig.canonical(mig.seal(plan)))
        (self.run / "issued.jsonl").write_bytes(mig.canonical(mig.seal({
            "plan_sha256": digest(mig.canonical(plan))})) + b"\n")

    def test_preflight_checks_six_frozen_references_and_preserves_inner_offline_limit(self):
        state = pilot.report(self.run)
        expected = {f"c0{i}" for i in range(1, 7)}
        self.assertEqual(self.prepared["sessions"], 24)
        self.assertEqual(self.prepared["max_calls"], 48)
        self.assertEqual(self.plan["execution_mode"], "offline_fixture")
        self.assertEqual(self.frozen["manifest"]["budget"]["max_attempts_per_task"], 1)
        self.assertEqual(state["actual_provider_calls"], 0)
        self.assertEqual(state["simulated_calls"], 0)
        self.assertEqual(len(state["sessions"]), 24)
        self.assertEqual(state["next"], {"session": 0, "attempt": 1, "history": None})
        evidence = mig.unseal(self.run / "preflight.json")
        self.assertEqual(set(evidence["references"]), expected)
        self.assertTrue(all(row["status"] == "verified" for row in evidence["references"].values()))
        for task in sorted(expected):
            rows = [row for row in state["sessions"] if row["task_id"] == task]
            self.assertEqual([(r["arm"], r["repetition"]) for r in rows],
                             [("A", 1), ("B", 1), ("B", 2), ("A", 2)])
        self.assertEqual(state["groups"]["positive"]["A"]["sessions"], 8)
        self.assertEqual(state["groups"]["boundary"]["B"]["sessions"], 4)
        self.assertFalse(state["scope"]["map_discovery_tested"])
        self.assertFalse(state["scope"]["executable_witness_extraction_tested"])

    def test_payloads_share_mathematics_without_references_or_role_leaks(self):
        references = json.loads((self.run / "inputs/reference_proofs.json").read_text())["tasks"]
        for task in self.plan["protocol"]["task_ids"]:
            with self.subTest(task=task):
                request = copy.deepcopy(mig.task_request(self.run / "math", task))
                request.update(incumbent={"proof": "PRIVATE_INCUMBENT"}, reference="PRIVATE_REFERENCE",
                               role="PRIVATE_ROLE", private_path="/home/private/credential")
                request["task"]["expected_method"] = "PRIVATE_EXPECTED_METHOD"
                payloads = [pilot.payload_for(request, arm, self.guide, self.plan["protocol"]["config"])
                            for arm in ("A", "B")]
                left, right = [json.loads(p["input"]) for p in payloads]
                self.assertEqual(right.pop("guide"), self.guide)
                self.assertEqual(left, right)
                self.assertEqual(set(left), {"lean_version", "sources", "target", "output_contract"})
                self.assertTrue(all(set(row) == {"module", "content"} for row in left["sources"]))
                text = json.dumps(payloads)
                self.assertNotIn("PRIVATE_", text)
                self.assertNotIn("/home/", text)
                self.assertNotIn("family", text)
                self.assertNotIn("reference_proofs", text)
                self.assertNotIn(references[task]["proof"], payloads[0]["input"])
                self.assertIn("complete Proof.lean", left["output_contract"]["proof"])

    def test_repair_success_records_constrained_contract_and_direct_named_dependency(self):
        state = self.call()
        self.assertEqual(state["sessions"][0]["status"], "repair_available")
        self.assertEqual(state["next"]["attempt"], 2)
        self.assertEqual(state["next"]["history"]["previous_candidate"], "not JSON")
        state = self.call(synthetic_response(json.dumps({"proof": self.full_source})),
                          verify=self.successful_verification)
        session = state["sessions"][0]
        self.assertEqual(session["status"], "verified")
        self.assertEqual(len(session["attempts"]), 2)
        self.assertEqual(state["next"], {"session": 1, "attempt": 1, "history": None})
        self.assertEqual(state["actual_provider_calls"], 0)
        self.assertEqual(state["simulated_calls"], 2)
        checked = session["attempts"][1]
        self.assertTrue(checked["verified_constrained_map_contract"])
        evidence = checked["method_application_evidence"]
        self.assertTrue(evidence["named_lemma_direct_dependency"])
        self.assertIn("Theory.preimage_mul_closed", evidence["direct_proof_dependencies"])
        self.assertIn("indirect", evidence["absence_means"])
        self.assertEqual(state, pilot.report(self.run))

    def test_inline_or_indirect_method_is_unclassified_not_rejected(self):
        def without_direct_dependency(*args, **kwargs):
            result = self.successful_verification(*args, **kwargs)
            result["audit"]["targets"][0]["direct_proof_dependencies"] = []
            return result

        state = self.call(synthetic_response(json.dumps({"proof": self.full_source})),
                          verify=without_direct_dependency)
        attempt = state["sessions"][0]["attempts"][0]
        self.assertEqual(state["sessions"][0]["status"], "verified")
        self.assertTrue(attempt["verified_constrained_map_contract"])
        self.assertFalse(attempt["method_application_evidence"]["named_lemma_direct_dependency"])

    def test_unknown_usage_stops_without_treating_missing_cost_as_zero(self):
        state = self.call(synthetic_response(usage=False))
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["halt_reason"], "unknown_usage")
        self.assertIsNone(state["generation_usage"])
        self.assertIsNone(state["estimated_cost_usd"])
        self.assertNotEqual(state["reserved_cost_usd"], "0")
        with self.assertRaises(CorpusError):
            pilot.execute_next(self.run, None, transport=unused_transport)

    def test_model_mismatch_stops_with_consumed_usage_preserved(self):
        state = self.call(synthetic_response(model="different-model"))
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["halt_reason"], "model_mismatch")
        self.assertEqual(state["known_generation_usage"]["total_tokens"], 120)

    def test_reserved_interruption_cannot_be_resent(self):
        with patch.object(pilot, "bounded_response", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                pilot.execute_next(self.run, None, transport=unused_transport)
        state = pilot.report(self.run)
        self.assertEqual(state["halt_reason"], "incomplete_event_do_not_resend")
        self.assertEqual(state["simulated_calls"], 1)
        self.assertIsNone(state["generation_usage"])
        with patch.object(pilot, "bounded_response") as boundary:
            with self.assertRaises(CorpusError):
                pilot.execute_next(self.run, None, transport=unused_transport)
            boundary.assert_not_called()

    def test_fixture_mode_rejects_provider_transport_before_credential_read(self):
        with patch.object(pilot, "read_private_key") as read_key:
            with self.assertRaisesRegex(CorpusError, "cannot be mixed"):
                pilot.execute_next(self.run, "/nonexistent/synthetic-key")
            read_key.assert_not_called()

    def test_provider_mode_rejects_injected_fixture_transport(self):
        self.provider_plan()
        with patch.object(pilot, "read_private_key") as read_key:
            with self.assertRaisesRegex(CorpusError, "cannot be mixed"):
                pilot.execute_next(self.run, None, transport=unused_transport)
            read_key.assert_not_called()

    def test_oversized_repair_stops_before_reading_key_or_invoking_transport(self):
        # Exercise the provider branch with mocked receipts and a mocked credential
        # reader, so ordering is tested without opening a credential or a socket.
        self.provider_plan()
        with (patch.object(pilot, "datetime") as clock,
              patch.object(pilot, "bounded_response", return_value=synthetic_response("?" * 16384)) as boundary,
              patch.object(pilot, "read_private_key", return_value="synthetic-only") as read_key):
            clock.now.return_value.date.return_value.isoformat.return_value = self.plan["protocol"]["config"]["pricing_checked_on"]
            pilot.execute_next(self.run, None)
            boundary.assert_called_once()
            read_key.assert_called_once()
            boundary.reset_mock()
            read_key.reset_mock()
            state = pilot.execute_next(self.run, None)
            boundary.assert_not_called()
            read_key.assert_not_called()
        attempt = state["sessions"][0]["attempts"][1]
        self.assertEqual(attempt["kind"], "input_budget")
        self.assertFalse(attempt["sent"])
        self.assertEqual(state["sessions"][0]["status"], "failed")
        self.assertEqual(state, pilot.report(self.run))

    def test_raw_receipt_tampering_rejects_replay(self):
        self.call()
        path = self.run / "events/001/response.bin"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(CorpusError, "response|metering"):
            pilot.report(self.run)

    def test_reference_command_log_tampering_rejects_replay(self):
        result = json.loads((self.run / "preflight/c01/verification.json").read_text())
        log = result["trace"][0]["logs"]["stdout"]["path"]
        (self.run / "preflight/c01" / log).write_text("modified log")
        with self.assertRaisesRegex(CorpusError, "evidence changed"):
            pilot.report(self.run)

    def test_frozen_guide_tampering_rejects_replay(self):
        path = self.run / "inputs/guide.txt"
        path.write_text(path.read_text() + "\nchanged")
        with self.assertRaisesRegex(CorpusError, "input snapshot changed"):
            pilot.report(self.run)

    def test_changed_tool_fingerprint_rejects_resume(self):
        with patch.object(pilot, "_hashes", return_value={}):
            with self.assertRaisesRegex(CorpusError, "tools changed"):
                pilot.report(self.run)

    def test_48_synthetic_calls_exhaust_24_sessions_without_reset_or_third_attempt(self):
        with patch.object(pilot, "bounded_response", return_value=synthetic_response()) as boundary:
            for _ in range(48):
                state = pilot.execute_next(self.run, None, transport=unused_transport)
            self.assertEqual(boundary.call_count, 48)
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["simulated_calls"], 48)
            self.assertEqual(state["actual_provider_calls"], 0)
            self.assertTrue(all(s["status"] == "failed" and len(s["attempts"]) == 2
                                for s in state["sessions"]))
            with self.assertRaises(CorpusError):
                pilot.execute_next(self.run, None, transport=unused_transport)
            self.assertEqual(boundary.call_count, 48)

    def test_new_output_name_cannot_reset_live_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-name"
            with patch.object(pilot, "commit_for") as commit:
                with self.assertRaisesRegex(CorpusError, "one ledger"):
                    pilot.prepare(pilot.FIXTURE, root)
                commit.assert_not_called()
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
