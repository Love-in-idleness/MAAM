import json
from pathlib import Path
import unittest

from maam.conjecture_compression import _portfolio, _suite


SUITE = Path(__file__).resolve().parents[1] / "experiments/conjecture_compression/suite.json"


class ConjectureCompressionTests(unittest.TestCase):
    def test_incomplete_witnesses_cannot_create_a_rankable_zero(self):
        before = {"one": {"proof_module_tokens": 110, "proof_body_tokens": 90},
                  "two": {"proof_module_tokens": 120, "proof_body_tokens": 100}}
        replacements = {"one": {"status": "verified", "proof": {"proof_module_tokens": 50, "proof_body_tokens": 24}},
                        "two": {"status": "missing_witness"}}
        report = _portfolio(before, replacements, 31)
        self.assertEqual(report["observed_verified_retained_module_tokens_saved"], 60)
        self.assertIsNone(report["conditional_net_tokens_saved"])
        self.assertEqual(report["status"], "unmeasured")

    def test_charge_assumption_once_and_keep_original_when_replacement_costs_more(self):
        before = {"one": {"proof_module_tokens": 110, "proof_body_tokens": 90},
                  "two": {"proof_module_tokens": 120, "proof_body_tokens": 100},
                  "three": {"proof_module_tokens": 100, "proof_body_tokens": 80}}
        replacements = {
            "one": {"status": "verified", "proof": {"proof_module_tokens": 50, "proof_body_tokens": 24}},
            "two": {"status": "verified", "proof": {"proof_module_tokens": 90, "proof_body_tokens": 60}},
            "three": {"status": "verified", "proof": {"proof_module_tokens": 105, "proof_body_tokens": 74}},
        }
        report = _portfolio(before, replacements, 31)
        self.assertEqual(report["conditional_net_tokens_saved"], 59)
        self.assertEqual(report["tasks"]["three"]["retain"], "original")
        self.assertEqual(report["tasks"]["three"]["observed_proof_body_tokens_saved"], 6)
        self.assertIsNone(report["net_tokens_saved_after_proving_conjecture"])

    def test_archived_scores_recalculate_from_matching_frozen_sources(self):
        suite, _, fingerprints = _suite(SUITE)
        report = json.loads(SUITE.with_name("report-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "measured")
        self.assertEqual(report["fingerprints"], fingerprints)
        for row in report["ranking"]:
            candidate = report["candidates"][row["candidate"]]
            before = {task: record["original"] for task, record in candidate["tasks"].items()}
            savings = _portfolio(before, candidate["tasks"], candidate["assumption_statement_module_tokens"])
            self.assertEqual(savings["conditional_net_tokens_saved"], row["conditional_net_tokens_saved"])
            self.assertEqual(set(before), set(suite["targets"]))
