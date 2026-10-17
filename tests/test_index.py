import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from maam import CorpusError
from maam.index import score_index


class IndexTests(unittest.TestCase):
    def create_index(self, path):
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO metadata VALUES ('summary', ?)", (json.dumps({"revision":"fixed-fixture"}),))
        db.execute("CREATE TABLE metrics (name TEXT PRIMARY KEY, module TEXT, kind TEXT, component_size INTEGER, depth INTEGER, unwrapped_exact TEXT, unwrapped_log2 REAL, wrapped_source INTEGER, source_status TEXT, signature_references INTEGER, body_references INTEGER, I1_reference REAL, score_reference REAL, admitted_dependency INTEGER)")
        db.execute("INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            "Example.theorem", "Example", "theorem", 1, 2, "14", math.log2(14), 10,
            "named_source", 2, 3, .2, 75, 0))
        db.commit()
        db.close()

    def test_measured_metrics_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"index.sqlite"
            self.create_index(path)
            result=score_index(str(path),"Example.theorem")
            self.assertEqual(result["assessment"]["score"],75)
            self.assertEqual(result["assessment"]["I0_reference"],1.5)
            self.assertAlmostEqual(result["assessment"]["T0_reference_log2"],math.log2(14/5))
            self.assertEqual(result["metadata"]["revision"],"fixed-fixture")

    def test_queries_are_parameterised_and_unknown_names_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"index.sqlite"
            self.create_index(path)
            with self.assertRaisesRegex(CorpusError,"unknown indexed declaration"):
                score_index(str(path),"'; DROP TABLE metrics; --")
            self.assertEqual(score_index(str(path),"Example.theorem")["assessment"]["score"],75)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"missing.sqlite"
            with self.assertRaises(CorpusError):
                score_index(str(path),"unknown")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
