"""Adding optional proofs must not discard previously verified results."""
import copy
import unittest

from maam import CorpusError
from maam.reuse import retained_portfolio


def witness(tokens, attempt=1):
    return {"proof_source_tokens": tokens, "attempt": attempt}


class RetainedPortfolioTests(unittest.TestCase):
    def test_only_strictly_shorter_replaces_and_input_is_unchanged(self):
        old = {t: witness(100) for t in ("shorter", "equal", "longer", "failed", "unknown")}
        new = dict(zip(old, (witness(60), witness(100, 2), witness(150), None, witness(None))))
        before = copy.deepcopy((old, new))
        result = retained_portfolio(old, new, 200)
        self.assertEqual([r["action"] for r in result["tasks"]], ["replace_with_shorter"] + ["retain_original"] * 4)
        self.assertEqual(result["coverage"]["retained"], list(old))
        self.assertEqual(result["tasks"][1]["selected"], old["equal"])
        self.assertEqual((old, new), before)

    def test_package_once_and_newly_solved_goal_outside_net_ledger(self):
        old = {"a": witness(100), "b": witness(200), "new": None, "missing": None}
        new = {"a": witness(50), "b": witness(300), "new": witness(70), "missing": None}
        r = retained_portfolio(old, new, 90)
        self.assertEqual(r["original_goal_source_ledger"], {"baseline_tokens": 300,
            "selected_proof_tokens": 250, "gross_tokens_saved": 50, "package_tokens_charged_once": 90,
            "selected_including_package_tokens": 340, "net_tokens_saved": -40})
        self.assertEqual(r["coverage"], {"original": ["a", "b"], "retained": ["a", "b", "new"], "newly_solved": ["new"]})
        self.assertEqual(r["new_goal_proof_tokens"], 70)

    def test_failed_or_absent_new_proof_does_not_drop_old_goal(self):
        r = retained_portfolio({"a": witness(10)}, {"a": None}, 20)
        self.assertEqual(r["tasks"][0]["action"], "retain_original")
        self.assertEqual(r["original_goal_source_ledger"]["gross_tokens_saved"], 0)
        self.assertEqual(r["original_goal_source_ledger"]["net_tokens_saved"], -20)

    def test_unknown_original_length_cannot_justify_replacement_or_known_cost(self):
        r = retained_portfolio({"a": witness(None)}, {"a": witness(1)}, 20)
        self.assertEqual(r["tasks"][0]["action"], "retain_original")
        for key in ("baseline_tokens", "selected_proof_tokens", "gross_tokens_saved", "net_tokens_saved"):
            self.assertIsNone(r["original_goal_source_ledger"][key])

    def test_unknown_package_cost_is_not_zero(self):
        r = retained_portfolio({"a": witness(10)}, {"a": witness(5)}, None)
        ledger = r["original_goal_source_ledger"]
        self.assertEqual(ledger["gross_tokens_saved"], 5)
        self.assertIsNone(ledger["package_tokens_charged_once"])
        self.assertIsNone(ledger["selected_including_package_tokens"])
        self.assertIsNone(ledger["net_tokens_saved"])

    def test_no_original_goals_is_not_zero_cost_compression_success(self):
        r = retained_portfolio({"a": None}, {"a": witness(7)}, 10)
        self.assertIsNone(r["original_goal_source_ledger"]["baseline_tokens"])
        self.assertIsNone(r["original_goal_source_ledger"]["net_tokens_saved"])
        self.assertEqual(r["new_goal_proof_tokens"], 7)

    def test_invalid_cost_or_goal_sets_rejected(self):
        for value in (-1, True, 1.5, "2"):
            with self.assertRaises(CorpusError):
                retained_portfolio({"a": witness(value)}, {"a": None}, 10)
            with self.assertRaises(CorpusError):
                retained_portfolio({}, {}, value)
        with self.assertRaises(CorpusError):
            retained_portfolio({"a": None}, {"b": None}, 0)

    def test_zero_length_is_known_and_empty_portfolio_is_not_a_win(self):
        r = retained_portfolio({"a": witness(3)}, {"a": witness(0)}, 0)
        self.assertEqual(r["original_goal_source_ledger"]["net_tokens_saved"], 3)
        self.assertIsNone(retained_portfolio({}, {}, 0)["original_goal_source_ledger"]["net_tokens_saved"])
