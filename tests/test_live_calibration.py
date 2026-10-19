"""Private live-call boundaries, using synthetic credentials and offline HTTP."""
import copy
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from maam import CorpusError, generation, live_calibration as live
from maam.migration import session_report, task_request, unseal

KEY = "sk-synthetic-fixture-" + "A" * 32
PRIOR_KEY = "sk-prior-fixture-" + "B" * 32


class LivePrivateBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def key_file(self, mode=0o600):
        path = self.folder / "credential.txt"
        path.write_text(KEY + "\n")
        path.chmod(mode)
        return path

    def response(self, raw=b'{"ok":true}', status=200):
        response = MagicMock()
        response.code = status
        response.headers.get.return_value = "request-fixture"
        response.read.return_value = raw
        response.__enter__.return_value = response
        return response

    def test_private_key_accepts_only_owner_only_regular_file(self):
        path = self.key_file()
        self.assertEqual(live.read_private_key(path), KEY)
        path.chmod(0o644)
        with self.assertRaises(CorpusError):
            live.read_private_key(path)

    def test_private_key_rejects_symlink_and_extra_text(self):
        path = self.key_file()
        link = self.folder / "linked-key"
        link.symlink_to(path)
        with self.assertRaises(OSError):
            live.read_private_key(link)
        path.write_text(KEY + "\nextra text")
        with self.assertRaises(CorpusError):
            live.read_private_key(path)

    def test_private_http_uses_only_explicit_endpoints_and_no_redirects(self):
        for endpoint in (generation.ENDPOINT, live.COUNT_ENDPOINT):
            with self.subTest(endpoint=endpoint):
                response = self.response()
                opener = Mock()
                opener.open.return_value = response
                with patch("maam.live_calibration.build_opener", return_value=opener) as build:
                    result = live.private_http(KEY, endpoint, {"model": live.MODEL}, 9)
                self.assertEqual(result, (200, "request-fixture", b'{"ok":true}'))
                request = opener.open.call_args.args[0]
                self.assertEqual(request.full_url, endpoint)
                self.assertEqual(request.get_header("Authorization"), "Bearer " + KEY)
                self.assertEqual(json.loads(request.data), {"model": live.MODEL})
                self.assertEqual(opener.open.call_args.kwargs["timeout"], 9)
                self.assertIsInstance(build.call_args.args[0], generation.NoRedirect)
                self.assertIsNone(build.call_args.args[0].redirect_request(
                    None, None, 302, "", {}, "https://elsewhere.invalid"))
        with patch("maam.live_calibration.build_opener") as build:
            for endpoint in ("http://api.openai.com/v1/responses", "https://elsewhere.invalid",
                             generation.ENDPOINT + "?key=blocked"):
                with self.assertRaisesRegex(OSError, "provider_endpoint_blocked"):
                    live.private_http(KEY, endpoint, {}, 9)
            build.assert_not_called()

    def test_http_errors_are_closed_without_reading_or_exposing_body(self):
        for status in (302, 401, 429):
            with self.subTest(status=status):
                body = Mock(wraps=io.BytesIO(("provider echoed " + KEY).encode()))
                error = HTTPError(generation.ENDPOINT, status, KEY, {}, body)
                opener = Mock()
                opener.open.side_effect = error
                with patch("maam.live_calibration.build_opener", return_value=opener):
                    with self.assertRaises(OSError) as caught:
                        live.private_http(KEY, generation.ENDPOINT, {}, 9)
                self.assertEqual(str(caught.exception), f"provider_http_{status}")
                body.read.assert_not_called()
                body.close.assert_called_once()

    def test_credentials_are_blocked_in_payload_and_successful_body(self):
        for fragment in (KEY, KEY[:20]):
            with self.subTest(fragment=fragment):
                with patch("maam.live_calibration.build_opener") as build:
                    with self.assertRaisesRegex(OSError, "credential_in_payload_blocked"):
                        live.private_http(KEY, generation.ENDPOINT, {"input": fragment}, 9)
                    build.assert_not_called()
                opener = Mock()
                opener.open.return_value = self.response(json.dumps({"echo": fragment}).encode())
                with patch("maam.live_calibration.build_opener", return_value=opener):
                    with self.assertRaisesRegex(OSError, "credential_echo_blocked"):
                        live.private_http(KEY, generation.ENDPOINT, {}, 9)

    def test_non_200_and_oversized_responses_are_not_returned(self):
        response = self.response(KEY.encode(), status=401)
        opener = Mock()
        opener.open.return_value = response
        with patch("maam.live_calibration.build_opener", return_value=opener):
            with self.assertRaisesRegex(OSError, "provider_http_401"):
                live.private_http(KEY, generation.ENDPOINT, {}, 9)
        response.read.assert_not_called()
        opener.open.return_value = self.response(b" " * (4 * 1024 * 1024 + 1))
        with patch("maam.live_calibration.build_opener", return_value=opener):
            with self.assertRaisesRegex(OSError, "provider_response_too_large"):
                live.private_http(KEY, generation.ENDPOINT, {}, 9)


class LiveCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / "run"
        self.key_file = self.folder / "credential.txt"
        self.key_file.write_text(KEY + "\n")
        self.key_file.chmod(0o600)
        self.sandbox = self.folder / "lean_sandbox.py"
        self.sandbox.write_text("# offline sandbox fixture\n")
        # Every environment value used by these tests is synthetic.
        self.environment = {"OPENAI_API_KEY": PRIOR_KEY, "PATH": "/fixture/bin",
                            "UNRELATED_PRIVATE_TOKEN": "unrelated-synthetic-secret"}
        environment = patch("maam.live_calibration.os.environ", self.environment)
        environment.start()
        self.addCleanup(environment.stop)
        preflight = patch("maam.generation.check_lean")
        self.preflight = preflight.start()
        self.addCleanup(preflight.stop)
        verifier = patch("maam.migration.verify_attempt", side_effect=self.verify)
        self.verifier = verifier.start()
        self.addCleanup(verifier.stop)
        self.calls = []

    def verify(self, frozen, request, source, artifact, **kwargs):
        self.assertNotIn("OPENAI_API_KEY", os.environ)
        self.assertNotIn("UNRELATED_PRIVATE_TOKEN", os.environ)
        sources = [{"module": "Proof", "source_tokens": 40}]
        if request["condition"] == "treatment":
            sources.append({"module": "Candidate", "source_tokens": 80})
        return {"status": "verified", "trace": [], "audit": {
            "targets": [{"name": "Submission.solve", "expected": request["task"]["goal"],
                         "goal_preserved": True, "proof_expr_nodes": 50,
                         "source": {"body_tokens": 30, "signature_tokens": 4,
                                    "declaration_tokens": 35}}], "sources": sources}}

    @staticmethod
    def wire(value):
        return 200, "request-fixture", json.dumps(value).encode()

    def http(self, key, endpoint, payload, timeout):
        self.assertEqual(key, KEY)
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if endpoint == live.COUNT_ENDPOINT:
            return self.wire({"object": "response.input_tokens", "input_tokens": 1000})
        self.assertEqual(endpoint, generation.ENDPOINT)
        return self.wire({"id": "resp_fixture", "model": live.MODEL, "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(
                {"proof": "by trivial", "bridge": "synthetic bridge"})}]}],
            "usage": {"input_tokens": 1000, "output_tokens": 40, "total_tokens": 1040}})

    def execute(self, http=None):
        return live.execute(self.root, self.key_file, self.sandbox, http=http or self.http)

    def assert_no_secret_archived(self):
        for path in self.root.rglob("*"):
            if path.is_file():
                content = path.read_bytes()
                for secret in (KEY, PRIOR_KEY, "unrelated-synthetic-secret", str(self.key_file)):
                    self.assertNotIn(secret.encode(), content, str(path))

    def test_preflight_counts_both_exact_payloads_before_two_live_labelled_calls(self):
        original = generation.openai_response
        result = self.execute()
        self.assertEqual(result["status"], "verified")
        self.assertEqual([endpoint for endpoint, _ in self.calls],
                         [live.COUNT_ENDPOINT] * 2 + [generation.ENDPOINT] * 2)
        self.assertEqual(result["generation_calls"], 2)
        self.assertTrue(result["result"]["provider_usage_observed"])
        self.assertTrue(all(task["status"] == "verified" for task in result["result"]["tasks"]))
        for index, condition in enumerate(("baseline", "treatment")):
            counted, generated = self.calls[index][1], self.calls[index + 2][1]
            self.assertEqual(counted, {k: v for k, v in generated.items()
                                       if k not in {"max_output_tokens", "store"}})
            self.assertEqual(generated["model"], live.MODEL)
            self.assertEqual(generated["max_output_tokens"], live.OUTPUT_LIMIT)
            self.assertFalse(generated["store"])
            self.assertEqual(len(session_report(self.root / condition)["tasks"][0]["attempts"]), 1)
            receipt = unseal(self.root / "calls" / f"{index + 1:04d}" / "receipt.json")
            self.assertEqual(receipt["transport"], "openai_responses")
        self.assertEqual(len(list((self.root / "guard-reservations").iterdir())), 2)
        self.assertIs(generation.openai_response, original)
        self.assertEqual(self.environment["OPENAI_API_KEY"], PRIOR_KEY)
        self.assert_no_secret_archived()

    def test_second_input_limit_failure_prevents_all_generation(self):
        def http(key, endpoint, payload, timeout):
            self.assertEqual(endpoint, live.COUNT_ENDPOINT)
            self.calls.append(endpoint)
            return self.wire({"input_tokens": 1000 if len(self.calls) == 1 else live.INPUT_LIMIT + 1})
        result = self.execute(http)
        self.assertEqual(result["status"], "preflight_stopped")
        self.assertEqual(result["generation_calls"], 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(list((self.root / "reservations").iterdir()), [])
        self.assertEqual(list((self.root / "guard-reservations").iterdir()), [])
        self.verifier.assert_not_called()
        self.assert_no_secret_archived()

    def test_cost_ceiling_stops_before_any_generation(self):
        with patch("maam.live_calibration.MAX_USD", Decimal("0.000001")):
            result = self.execute()
        self.assertEqual(result["reason"], "cost_preflight_exceeds_run_ceiling")
        self.assertEqual(result["generation_calls"], 0)
        self.assertEqual([endpoint for endpoint, _ in self.calls], [live.COUNT_ENDPOINT])
        self.assertEqual(list((self.root / "reservations").iterdir()), [])
        self.verifier.assert_not_called()

    def test_bad_count_and_private_error_messages_are_safely_stopped(self):
        for index, count in enumerate((True, 0, -1, "1000", None)):
            with self.subTest(count=count):
                self.root = self.folder / f"bad-count-{index}"
                result = self.execute(lambda *args: self.wire({"input_tokens": count}))
                self.assertEqual(result["generation_calls"], 0)
                self.assertEqual(result["status"], "preflight_stopped")
        self.root = self.folder / "private-error"
        result = self.execute(Mock(side_effect=OSError("sensitive provider message " + KEY)))
        self.assertEqual(result["reason"], "preflight_failed")
        self.assert_no_secret_archived()

    def test_guard_blocks_changed_payload_and_third_call_before_network(self):
        def fake_run(root, *, lean):
            _, record = generation.load_run(root)
            payloads = [generation.payload_for(record, task_request(root / item["condition"],
                       item["task_id"]), [], live.OUTPUT_LIMIT) for item in record["schedule"]]
            changed = copy.deepcopy(payloads[0])
            changed["model"] = "unapproved-model"
            with self.assertRaisesRegex(OSError, "uncounted_or_extra_payload_blocked"):
                generation.openai_response(changed, 1)
            for payload in payloads:
                generation.openai_response(payload, 1)
            with self.assertRaisesRegex(OSError, "uncounted_or_extra_payload_blocked"):
                generation.openai_response(payloads[-1], 1)
            return {"status": "fixture_finished", "provider_usage_observed": False,
                    "usage_complete": False, "tasks": []}
        with patch("maam.generation.run", side_effect=fake_run):
            result = self.execute()
        self.assertEqual(result["generation_calls"], 2)
        self.assertEqual([endpoint for endpoint, _ in self.calls],
                         [live.COUNT_ENDPOINT] * 2 + [generation.ENDPOINT] * 2)

    def test_generation_failure_consumes_one_call_and_restores_secrets(self):
        def http(key, endpoint, payload, timeout):
            if endpoint == generation.ENDPOINT:
                raise OSError("provider_http_401")
            return self.http(key, endpoint, payload, timeout)
        result = self.execute(http)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["generation_calls"], 1)
        self.assertEqual(result["result"]["stop"]["reason"], "unknown_usage_or_interrupted_call")
        self.assertFalse(result["result"]["usage_complete"])
        self.assertEqual((self.root / "calls/0001/response.bin").read_bytes(), b"")
        self.assertEqual(self.environment["OPENAI_API_KEY"], PRIOR_KEY)
        self.verifier.assert_not_called()
        self.assert_no_secret_archived()

    def test_interruption_restores_transport_and_absent_environment_key(self):
        self.environment.pop("OPENAI_API_KEY")
        original = generation.openai_response
        def http(key, endpoint, payload, timeout):
            if endpoint == generation.ENDPOINT:
                raise KeyboardInterrupt
            return self.http(key, endpoint, payload, timeout)
        with self.assertRaises(KeyboardInterrupt):
            self.execute(http)
        self.assertIs(generation.openai_response, original)
        self.assertNotIn("OPENAI_API_KEY", self.environment)
        self.assertTrue((self.root / "reservations/0001.json").exists())
        self.assertTrue((self.root / "guard-reservations/01.json").exists())
        self.assert_no_secret_archived()


if __name__ == "__main__":
    unittest.main()
