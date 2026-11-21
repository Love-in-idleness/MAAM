import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from maam.conjectures import rank_conjectures
from maam.corpus import CorpusError


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "experiments/conjecture_ranking/corpus-v1.json"


class ConjectureRankingTests(unittest.TestCase):
    def test_replays_published_ranking(self):
        result = subprocess.run(
            [sys.executable, "-m", "maam", "rank-conjectures",
             "--corpus", str(CORPUS), "--format", "markdown"],
            cwd=ROOT, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout, CORPUS.with_name("ranking-v1.md").read_bytes())
        report = rank_conjectures(CORPUS)
        self.assertEqual(
            {row["id"]: (row["rank"], row["coverage"]) for row in report["ranking"]},
            {"hodge": (1, 4), "lefschetz-finite": (2, 3), "p-eq-np": (2, 3),
             "rh": (4, 2), "artin-reciprocity": (5, 1), "bsd-rank": (5, 1),
             "p-ne-np": (5, 1), "goldbach": (8, 0), "lindelof": (8, 0)},
        )
        rh = next(row for row in report["ranking"] if row["id"] == "rh")
        self.assertEqual(rh["recorded_equivalences"][0]["reverse_rule_ids"], ["prime-count-rh"])
        moments = next(target for target in rh["new_open_targets"] if target["id"] == "zeta-moments")
        self.assertEqual(moments["rule_ids"], ["rh-lindelof", "lindelof-moments"])
        self.assertEqual(report["baseline_targets"], ["ternary-goldbach"])

    def test_open_premise_and_duplicate_equivalences(self):
        data = json.loads(CORPUS.read_text(encoding="utf-8"))
        # Make the gap result require a second open conjecture. It cannot count for RH alone.
        rule = next(rule for rule in data["rules"] if rule["id"] == "rh-short-gaps")
        rule["premises"].append("goldbach")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "corpus.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            report = rank_conjectures(path)
            rh = next(row for row in report["ranking"] if row["id"] == "rh")
            self.assertEqual(rh["families"], ["zeta-growth"])
            data["statements"]["zeta-moments"]["family"] = "extra-unearned-point"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(CorpusError, "equivalent targets must share a family"):
                rank_conjectures(path)
