"""Synthetic HTTP only: DeepSeek never falls back to an OpenAI endpoint."""
import io
import json
import unittest
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from maam import deepseek

KEY = "sk-synthetic-deepseek-" + "F" * 32


class DeepSeekBoundaryTests(unittest.TestCase):
    @staticmethod
    def response(raw=b'{"ok":true}', status=200):
        handle = MagicMock()
        handle.code = status
        handle.headers.get.return_value = "fixture-id"
        handle.read.return_value = raw
        handle.__enter__.return_value = handle
        return handle

    def test_only_official_deepseek_endpoint_and_private_header(self):
        opener = Mock()
        opener.open.return_value = self.response()
        with patch("maam.deepseek.build_opener", return_value=opener) as build:
            result = deepseek.response(KEY, {"model": "deepseek-flash", "input": "fixture"}, 10)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + KEY)
        self.assertNotIn(KEY.encode(), request.data)
        self.assertEqual(result, (200, "fixture-id", b'{"ok":true}'))
        self.assertIsNone(build.call_args.args[0].redirect_request(None, None, 302, "", {}, "https://api.openai.com"))

    def test_auth_error_body_is_never_read_and_has_no_retry(self):
        body = Mock(wraps=io.BytesIO(KEY.encode()))
        error = HTTPError(deepseek.ENDPOINT, 401, KEY, {}, body)
        opener = Mock()
        opener.open.side_effect = error
        with patch("maam.deepseek.build_opener", return_value=opener):
            with self.assertRaisesRegex(OSError, "provider_http_401"):
                deepseek.response(KEY, {}, 10)
        body.read.assert_not_called()
        body.close.assert_called_once()
        self.assertEqual(opener.open.call_count, 1)

    def test_full_key_and_prefix_are_blocked_in_both_directions(self):
        for fragment in (KEY, KEY[:20]):
            with patch("maam.deepseek.build_opener") as build:
                with self.assertRaisesRegex(OSError, "credential_in_payload_blocked"):
                    deepseek.response(KEY, {"input": fragment}, 10)
                build.assert_not_called()
            opener = Mock()
            opener.open.return_value = self.response(fragment.encode())
            with patch("maam.deepseek.build_opener", return_value=opener):
                with self.assertRaisesRegex(OSError, "credential_echo_blocked"):
                    deepseek.response(KEY, {}, 10)

    def test_non_200_and_oversized_success_are_not_archived(self):
        opener = Mock()
        for handle in (self.response(KEY.encode(), 403), self.response(b" " * (4 * 1024 * 1024 + 1))):
            opener.open.return_value = handle
            with patch("maam.deepseek.build_opener", return_value=opener):
                with self.assertRaises(OSError):
                    deepseek.response(KEY, {}, 10)
        self.assertEqual(opener.open.call_count, 2)

    def test_input_policy_is_a_full_reservation_not_a_tokenizer_claim(self):
        status, request_id, raw = deepseek.input_allowance({"input": "fixture"}, 16384)
        value = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertIsNone(request_id)
        self.assertEqual(value["input_tokens"], 16384)
        self.assertIn("not_token_count", value["method"])
        with self.assertRaises(OSError):
            deepseek.input_allowance({"input": "x" * 16384}, 16384)


if __name__ == "__main__":
    unittest.main()
