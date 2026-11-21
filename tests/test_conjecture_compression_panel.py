"""Acceptance checks against the two independently audited frozen reports."""

import json
from pathlib import Path
import unittest

from scripts.rank_conjecture_compression_panel import markdown, rank_panel


PANEL = Path(__file__).resolve().parents[1] / "experiments/conjecture_compression_v2"


class ConjectureCompressionPanelTests(unittest.TestCase):
    def test_reproduce_archived_leaderboard(self):
        report = rank_panel(PANEL / "panel.json")
        self.assertEqual(report, json.loads((PANEL / "ranking.json").read_text(encoding="utf-8")))
        self.assertEqual(markdown(report), (PANEL / "ranking.md").read_text(encoding="utf-8"))

    def test_charge_legendre_statement_once_and_retain_unmeasured_bertrand(self):
        report = rank_panel(PANEL / "panel.json")
        rows = {row["candidate"]: row for row in report["ranking"]}
        legendre, twin = rows["legendre"], rows["twin_primes"]
        self.assertEqual([task["status"] for task in legendre["targets"].values()],
                         ["verified", "verified"])
        self.assertEqual(legendre["observed_gross_tokens_saved"] - legendre["conditional_net_tokens_saved"],
                         legendre["statement_tokens"])
        self.assertEqual(twin["targets"]["bertrand"]["status"], "original_carried")
        self.assertIsNone(twin["targets"]["bertrand"]["replacement_tokens"])
        self.assertEqual(twin["conditional_net_tokens_saved"], 27)
