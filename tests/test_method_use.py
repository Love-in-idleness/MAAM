"""Offline guidance-controller evidence; synthetic receipts are never provider calls."""
from contextlib import nullcontext
import copy
import json
import multiprocessing
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from maam import CorpusError, method_use as pilot
from maam import migration as mig
from maam.lean_sandbox import SandboxUnavailable, lean_sandbox
from maam.theory import digest


def synthetic_response(output="not JSON", *, usage=True, model="deepseek-flash", status="completed"):
    body = {"id": "offline-response", "model": model, "status": status,
            "output": [{"type": "message", "content": [{"type": "output_text", "text": output}]}]}
    if usage:
        body["usage"] = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    return 200, "offline-request", mig.canonical(body)


def unused_transport(*args):
    raise AssertionError("controller tests patch the process boundary; no real transport is permitted")


class MethodUseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="maam-method-controller-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.template = Path(cls.temporary.name) / "template"
        pilot.prepare(pilot.FIXTURE, cls.template, verify_commit=False)
        try:
            evidence = pilot.preflight(cls.template)
        except SandboxUnavailable as exc:
            raise unittest.SkipTest(str(exc)) from exc
        if evidence["status"] != "verified":
            raise AssertionError(evidence)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="maam-method-controller-case-")
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name) / "run"
        shutil.copytree(self.template, self.run)
        self.root, self.plan, self.frozen, self.guide = pilot._load(self.run)
        self.request = mig.task_request(self.run / "math", "u01")
        self.full_source = (self.run / "preflight/u01/Proof.lean").read_text()

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
        result = json.loads((self.run / "preflight/u01/verification.json").read_text())
        # Lean already verified this exact source in class preflight; this mock
        # isolates controller transitions rather than repeating six compilations.
        result["trace"] = []
        return result

    def test_preflight_has_six_verified_references_and_explicit_fixture_mode(self):
        state = pilot.report(self.run)
        self.assertEqual(self.plan["execution_mode"], "offline_fixture")
        self.assertEqual(state["actual_provider_calls"], 0)
        self.assertEqual(state["simulated_calls"], 0)
        self.assertEqual(len(state["sessions"]), 24)
        self.assertEqual(state["next"], {"session": 0, "attempt": 1, "history": None})
        evidence = mig.unseal(self.run / "preflight.json")
        self.assertEqual(set(evidence["references"]), {f"u0{i}" for i in range(1, 7)})
        self.assertTrue(all(row["status"] == "verified" for row in evidence["references"].values()))

    def test_provider_payload_is_whitelisted_and_math_identical_between_arms(self):
        request = copy.deepcopy(self.request)
        request.update(incumbent={"proof": "PRIVATE_INCUMBENT"}, reference="PRIVATE_REFERENCE",
                       role="PRIVATE_ROLE", private_path="/home/private/credential",
                       other_sessions=["PRIVATE_OTHER_SESSION"])
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
        self.assertNotIn("incumbent", text)
        self.assertNotIn("reference_proofs", text)
        self.assertIn("complete Proof.lean", left["output_contract"]["proof"])

    def test_malformed_output_allows_only_one_repair_then_stops_after_success(self):
        state = self.call()
        self.assertEqual(state["sessions"][0]["status"], "repair_available")
        self.assertEqual(state["next"]["attempt"], 2)
        self.assertEqual(state["next"]["history"]["previous_candidate"], "not JSON")
        state = self.call(synthetic_response(json.dumps({"proof": self.full_source})),
                          verify=self.successful_verification)
        self.assertEqual(state["sessions"][0]["status"], "verified")
        self.assertEqual(len(state["sessions"][0]["attempts"]), 2)
        self.assertEqual(state["next"], {"session": 1, "attempt": 1, "history": None})
        self.assertEqual(state["actual_provider_calls"], 0)
        self.assertEqual(state["simulated_calls"], 2)
        self.assertEqual(state, pilot.report(self.run))
        evidence = state["sessions"][0]["attempts"][1]["method_application_evidence"]
        self.assertTrue(evidence["named_lemma_direct_dependency"])

    def test_two_malformed_outputs_exhaust_session_without_third_attempt(self):
        self.call()
        state = self.call()
        self.assertEqual(state["sessions"][0]["status"], "failed")
        self.assertEqual(state["next"]["session"], 1)
        self.assertEqual(state["next"]["attempt"], 1)
        self.assertEqual(len(state["sessions"][0]["attempts"]), 2)

    def test_unknown_usage_stops_batch_and_preserves_unknown(self):
        state = self.call(synthetic_response(usage=False))
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["halt_reason"], "unknown_usage")
        self.assertIsNone(state["generation_usage"])
        self.assertIsNone(state["estimated_cost_usd"])
        self.assertNotEqual(state["reserved_cost_usd"], "0")
        with self.assertRaises(CorpusError):
            pilot.execute_next(self.run, None, transport=unused_transport)

    def test_model_mismatch_stops_even_with_known_usage(self):
        state = self.call(synthetic_response(model="different-model"))
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["halt_reason"], "model_mismatch")
        self.assertEqual(state["known_generation_usage"]["total_tokens"], 120)

    def test_generation_truncation_ends_session_without_repair(self):
        state = self.call(synthetic_response(status="incomplete"))
        self.assertEqual(state["sessions"][0]["status"], "failed")
        self.assertEqual(state["sessions"][0]["attempts"][0]["kind"], "provider_incomplete")
        self.assertEqual(state["next"], {"session": 1, "attempt": 1, "history": None})

    def test_raw_response_tampering_is_rejected(self):
        self.call()
        path = self.run / "events/001/response.bin"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(CorpusError, "response|metering"):
            pilot.report(self.run)

    def test_reference_command_log_tampering_is_rejected(self):
        result = json.loads((self.run / "preflight/u01/verification.json").read_text())
        log = result["trace"][0]["logs"]["stdout"]["path"]
        (self.run / "preflight/u01" / log).write_text("modified log")
        with self.assertRaisesRegex(CorpusError, "evidence changed"):
            pilot.report(self.run)

    def test_changed_tool_fingerprint_rejects_resume(self):
        with patch.object(pilot, "_hashes", return_value={}):
            with self.assertRaisesRegex(CorpusError, "tools changed"):
                pilot.report(self.run)

    def test_oversized_input_is_recorded_without_transport_or_key_access(self):
        self.call(synthetic_response("?" * 16384))
        with (patch.object(pilot, "bounded_response") as boundary,
              patch.object(pilot, "read_private_key") as read_key):
            state = pilot.execute_next(self.run, None, transport=unused_transport)
        boundary.assert_not_called()
        read_key.assert_not_called()
        self.assertEqual(state["sessions"][0]["status"], "failed")
        self.assertEqual(state["sessions"][0]["attempts"][1]["kind"], "input_budget")
        self.assertFalse(state["sessions"][0]["attempts"][1]["sent"])
        self.assertEqual(state["simulated_calls"], 1)
        self.assertEqual(state, pilot.report(self.run))

    def test_interrupted_reserved_call_cannot_be_resent(self):
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

    def test_fixture_plan_rejects_paid_transport_before_reading_credentials(self):
        with patch.object(pilot, "read_private_key") as read_key:
            with self.assertRaisesRegex(CorpusError, "cannot be mixed"):
                pilot.execute_next(self.run, "/nonexistent/synthetic-key")
            read_key.assert_not_called()

    def test_provider_plan_rejects_injected_fixture_transport(self):
        plan = mig.unseal(self.run / "plan.json")
        plan.update(execution_mode="provider", source_commit="synthetic-committed-inputs")
        (self.run / "plan.json").write_bytes(mig.canonical(mig.seal(plan)))
        (self.run / "issued.jsonl").write_bytes(mig.canonical(mig.seal({
            "plan_sha256": digest(mig.canonical(plan))})) + b"\n")
        with patch.object(pilot, "read_private_key") as read_key:
            with self.assertRaisesRegex(CorpusError, "cannot be mixed"):
                pilot.execute_next(self.run, None, transport=unused_transport)
            read_key.assert_not_called()

    def test_all_48_synthetic_calls_complete_24_failed_sessions_and_cannot_reset(self):
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

    def test_real_checker_rejects_wrong_goal_extra_axiom_import_and_term_only(self):
        cases = {
            "wrong_goal": self.full_source.replace("theorem solve : MethodUse.Tasks.u01 :=",
                                                   "theorem solve : True :=").split("by\n", 1)[0]
                          + "by exact True.intro\nend Submission\n",
            "unused_axiom": self.full_source + "\naxiom unrequested : False\n",
            "extra_import": "import Lean\n" + self.full_source,
            "term_only": "by\n  trivial\n",
        }
        with lean_sandbox(check=False) as lean:
            for name, source in cases.items():
                with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                    result = mig.verify_attempt(self.frozen, self.request, source,
                                                Path(directory), lean=str(lean))
                    self.assertEqual(result["status"], "rejected", result)


class MethodUseDeadlineTests(unittest.TestCase):
    def test_new_output_name_cannot_reset_the_approved_live_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-name"
            with patch.object(pilot, "commit_for") as commit:
                with self.assertRaisesRegex(CorpusError, "one ledger"):
                    pilot.prepare(pilot.FIXTURE, root)
                commit.assert_not_called()
            self.assertFalse(root.exists())

    def test_transport_errors_and_header_echo_never_publish_secret_text(self):
        key = "synthetic-private-marker-1234567890"

        def echoed_header(key, payload, timeout):
            return 200, key, b"{}"

        def unsafe_error(key, payload, timeout):
            raise OSError("server echoed " + key)

        def http_error(key, payload, timeout):
            raise OSError("provider_http_429")

        for transport, expected in ((echoed_header, "credential_echo_blocked"),
                                    (unsafe_error, "provider_request_failed"),
                                    (http_error, "provider_http_429")):
            with self.subTest(expected=expected):
                with self.assertRaises(OSError) as raised:
                    pilot.bounded_response(key, {}, 3, transport=transport)
                self.assertEqual(str(raised.exception), expected)
                self.assertNotIn(key, str(raised.exception))

    def test_short_deadline_reaps_transport_process(self):
        before = {process.pid for process in multiprocessing.active_children()}

        def sleeping_transport(key, payload, timeout):
            time.sleep(10)

        started = time.monotonic()
        with self.assertRaisesRegex(OSError, "provider_deadline_exceeded"):
            pilot.bounded_response("synthetic-only", {}, 0.05, transport=sleeping_transport)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual({process.pid for process in multiprocessing.active_children()}, before)


if __name__ == "__main__":
    unittest.main()
