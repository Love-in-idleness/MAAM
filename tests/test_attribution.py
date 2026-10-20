"""Do not credit old-tool optimisation or extra search to a new package."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import random
import tempfile
import unittest

from maam import CorpusError
from maam.attribution import source_attribution
from scripts.check_baseline_attribution import check, main


class AttributionTests(unittest.TestCase):
    def test_old_cleanup_and_continued_search_are_separate(self):
        r = source_attribution(historical=100, prepared=60, control=50, treatment=45, package=20)
        self.assertEqual((r["historical_net_saving"], r["old_tool_preparation_saving"],
                          r["continued_old_tool_search_saving"], r["package_associated_net_difference"]), (35, 40, 10, -15))
        self.assertTrue(r["identity_verified"])
        self.assertFalse(r["causal_effect_established"])

    def test_identity_over_varied_retained_portfolios(self):
        rng = random.Random(2041)
        for _ in range(100):
            h = rng.randrange(1000)
            b = rng.randrange(h + 1)
            r = source_attribution(historical=h, prepared=b, control=rng.randrange(b + 1),
                                   treatment=rng.randrange(b + 1), package=rng.randrange(1000))
            self.assertEqual(r["historical_net_saving"], r["decomposition_total"])

    def test_unknown_costs_do_not_become_zero_or_a_verified_identity(self):
        r = source_attribution(historical=100, prepared=60, control=None, treatment=45, package=20)
        self.assertEqual(r["old_tool_preparation_saving"], 40)
        self.assertIsNone(r["continued_old_tool_search_saving"])
        self.assertIsNone(r["package_associated_net_difference"])
        self.assertIsNone(r["identity_verified"])

    def test_invalid_costs_and_discarded_incumbents_reject(self):
        args = dict(historical=100, prepared=60, control=50, treatment=45, package=20)
        for invalid in (-1, True, 1.5, "2"):
            with self.assertRaises(CorpusError):
                source_attribution(**{**args, "package": invalid})
        for change in ({"prepared": 101}, {"control": 61}, {"treatment": 61}):
            with self.assertRaises(CorpusError):
                source_attribution(**{**args, **change})

    def test_exact_finite_baseline_exposes_apparent_gain(self):
        r = check()
        self.assertEqual(r["attribution"]["historical_net_saving"], 45)
        self.assertEqual(r["attribution"]["package_associated_net_difference"], -15)
        self.assertEqual(r["attribution"]["unit"], "finite_tree_statement_length_units")
        self.assertFalse(r["attribution"]["global_minimum_established"])

    def test_output_never_overwrites_previous_evidence(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            path = Path(temp) / "result.json"
            self.assertEqual(main(["--output", str(path)]), 0)
            first = path.read_bytes()
            self.assertEqual(main(["--output", str(path)]), 2)
            self.assertEqual(path.read_bytes(), first)
