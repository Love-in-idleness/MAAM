"""Method-card boundaries and deterministic rendering; no Lean or provider calls."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from maam import CorpusError
from maam.method_card import generate, load_card, render, validate_card
from maam.migration import canonical, proof_source, start_session, task_request
from maam.theory import digest

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "experiments/left_inverse_method_v1/method.json"


class MethodCardTests(unittest.TestCase):
    def setUp(self):
        self.card = load_card(CARD)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.session = Path(temporary.name) / "session"
        start_session(ROOT / "experiments/metered_transfer_v1/suite.json", self.session,
                      condition="baseline", solver_id="method-card-fixture")

    def request(self, task="d04"):
        inner = task_request(self.session, task)
        value = {"task_id": task, "inner_request": inner, "incumbent": {"proof": "fixture"}}
        return {**value, "request_sha256": digest(canonical(value))}

    def reseal(self, request):
        inner = request["inner_request"]
        inner["request_sha256"] = digest(canonical({k: v for k, v in inner.items()
                                                   if k != "request_sha256"}))
        request["request_sha256"] = digest(canonical({k: v for k, v in request.items()
                                                     if k != "request_sha256"}))
        return request

    def test_render_and_generation_are_deterministic_and_bound_to_full_source(self):
        bindings = self.card["applications"]["d04"]["bindings"]
        expected = ("have hc := congrArg (h.mul (h.inv (f x))) hxx\n"
                    "simpa only [← h.mul_assoc, h.inv_mul, h.one_mul, h.mul_one] using hc")
        self.assertEqual(render(self.card, bindings), expected)
        request = self.request()
        response, evidence = generate(request, self.card)
        self.assertEqual((response, evidence), generate(request, self.card))
        self.assertEqual(set(response), {"action", "request_sha256", "proof", "bridge"})
        self.assertEqual(response["action"], "candidate")
        self.assertTrue(evidence["matched"])
        self.assertEqual(evidence["bindings"], bindings)
        self.assertEqual(evidence["card_sha256"], digest(canonical(self.card)))
        self.assertEqual(evidence["proof_sha256"],
                         digest(proof_source(request["inner_request"], response["proof"]).encode()))

    def test_chosen_argument_transport_avoids_rewriting_both_occurrences(self):
        response, _ = generate(self.request(), self.card)
        self.assertIn("congrArg (fun t => h.mul t (f x)) hx", response["proof"])
        self.assertNotIn("rw [hx", response["proof"])
        self.assertTrue(any("one chosen argument" in item for item in self.card["obligations"]))
        self.assertIn("h.mul a b = c", self.card["entry"]["hypothesis"])
        self.assertTrue(any("source d03" in item and "target d04" in item
                            for item in self.card["obligations"]))

    def test_right_cancellation_is_explicitly_unsupported(self):
        response, evidence = generate(self.request("d02"), self.card)
        self.assertEqual(set(response), {"action", "request_sha256", "reason"})
        self.assertEqual(response["action"], "retain")
        self.assertIn("right_cancellation_not_implemented", response["reason"])
        self.assertFalse(evidence["matched"])
        self.assertIsNone(evidence["bindings"])
        self.assertIsNone(evidence["proof_sha256"])

    def test_mismatched_sources_goals_and_condition_retain(self):
        mutations = [
            lambda r: r["inner_request"].update(condition="treatment"),
            lambda r: r["inner_request"]["task"].update(goal="Tasks.d03"),
            lambda r: r["inner_request"]["contract"].update(expected_goal="Tasks.d03"),
            lambda r: r["inner_request"]["sources"][0].update(content="different Base"),
            lambda r: r["inner_request"]["sources"].append({"module": "Candidate"}),
            lambda r: r.update(task_id="d02"),
            lambda r: r.update(task_id=["d04"]),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                request = self.request()
                mutate(request)
                response, evidence = generate(self.reseal(request), self.card)
                self.assertEqual(response["action"], "retain")
                self.assertFalse(evidence["matched"])
        self.assertEqual(generate(self.request("d01"), self.card)[0]["reason"], "task_not_declared")

    def test_both_request_fingerprints_are_checked(self):
        for level in ("outer", "inner"):
            request = self.request()
            target = request if level == "outer" else request["inner_request"]
            target["request_sha256"] = "0" * 64
            response, _ = generate(request, self.card)
            self.assertEqual(response["reason"], "request_fingerprint_mismatch")

    def test_binding_injection_and_unknown_bindings_are_rejected(self):
        good = self.card["applications"]["d04"]["bindings"]
        for name, value in (("group", "h.inv"), ("result", "h"), ("result", "f"),
                            ("result", "_"), ("equality", "by"),
                            ("element", "(f x)\n  sorry"), ("element", "{group}"),
                            ("element", "(f (g x))"), ("element", "(f sorry)")):
            with self.subTest(name=name, value=value), self.assertRaises(CorpusError):
                render(self.card, {**good, name: value})
        with self.assertRaises(CorpusError):
            render(self.card, {**good, "unknown": "x"})
        with self.assertRaises(CorpusError):
            render(self.card, {k: v for k, v in good.items() if k != "result"})

    def test_invalid_direction_laws_shape_and_format_access_are_rejected(self):
        mutations = [
            lambda c: c.update(schema_version=True),
            lambda c: c["entry"].update(direction="right_inverse_cancel"),
            lambda c: c["required_laws"].append("mul_inv"),
            lambda c: c.update(unknown="unused"),
            lambda c: c.update(proof_template="{group.__class__}"),
            lambda c: c.update(proof_template="{group!r}"),
            lambda c: c.update(proof_template="{group:10}"),
            lambda c: c.update(proof_template="{{group}}"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(CorpusError):
                card = deepcopy(self.card)
                mutate(card)
                validate_card(card)


if __name__ == "__main__":
    unittest.main()
