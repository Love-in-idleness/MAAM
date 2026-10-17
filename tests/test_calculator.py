import copy
import json
import math
from pathlib import Path
import unittest

from maam import Calculator, Corpus, CorpusError, direct_metrics
from maam.numeric import percentiles


def fixture():
    return {"schema_version": 1, "corpus_id": "hand-checked", "length_basis": "references",
            "provenance": {"kind": "synthetic"}, "nodes": [
                {"name": "p", "kind": "primitive"},
                {"name": "D", "kind": "definition", "signature": {"p": 1}, "body": {"p": 3}},
                {"name": "t", "kind": "theorem", "signature": {"p": 2}, "body": {"D": 3},
                 "statement": "example proposition"},
                {"name": "trivial", "kind": "theorem", "signature": {"p": 2}, "body": {"p": 1}},
            ]}


class CalculatorTests(unittest.TestCase):
    def test_four_lengths_and_multiplicity(self):
        calc = Calculator(Corpus(fixture()))
        t = calc.evaluate("t")["assessment"]
        self.assertEqual(t["unwrapped_signature"]["exact"], "2")
        self.assertEqual(t["unwrapped_body"]["exact"], "12")
        self.assertEqual(t["unwrapped_total"]["exact"], "14")
        self.assertEqual(t["wrapped_signature"], 2)
        self.assertEqual(t["wrapped_body"], 3)
        self.assertEqual(t["T0"]["value"], 14 / 5)
        self.assertEqual(t["I0"]["value"], 3 / 2)
        self.assertEqual(t["primitive_proof_to_statement"]["value"], 6)
        self.assertEqual(t["depth"], 2)

    def test_paper_simple_lemma(self):
        path = Path(__file__).parents[1] / "examples" / "paper_simple_lemma.json"
        calc = Calculator(Corpus.load(path))
        r = calc.evaluate("simple_lemma")["assessment"]
        self.assertEqual(r["unwrapped_total"]["exact"], "7")
        self.assertEqual(r["I0"]["value"], 4 / 3)
        self.assertEqual(r["T0"]["value"], 1)
        self.assertEqual(r["score"], 50)
        self.assertEqual(calc.cohort_size, 1)

    def test_source_tokens_are_distinct_from_references(self):
        data = fixture()
        data["length_basis"] = "source_tokens"
        for node in data["nodes"]:
            if node["kind"] != "primitive":
                node.update(signature_tokens=5, body_tokens=10)
        r = Calculator(Corpus(data)).evaluate("t")["assessment"]
        self.assertEqual(r["I0"]["value"], 2)
        self.assertEqual(r["T0"]["value"], 14 / 15)

    def test_missing_source_counts_not_approximated(self):
        data = fixture()
        data["length_basis"] = "source_tokens"
        with self.assertRaisesRegex(CorpusError, "source_tokens needs"):
            Corpus(data)

    def test_no_body_is_not_zero_interest_for_conjecture(self):
        data = fixture()
        data["nodes"].append({"name": "Goldbach-placeholder", "kind": "conjecture",
                              "signature": {"p": 2}, "statement": "Every even integer greater than 2 is a sum of two primes."})
        r = Calculator(Corpus(data)).evaluate("Goldbach-placeholder")["assessment"]
        self.assertIsNone(r["score"])
        self.assertIsNone(r["T0"])
        self.assertIsNone(r["I0"])
        self.assertIsNone(r["unwrapped_body"])

    def test_theorem_requires_a_proof(self):
        data = fixture()
        del data["nodes"][2]["body"]
        with self.assertRaisesRegex(CorpusError, "theorem needs a body"):
            Corpus(data)

    def test_cannot_use_conjecture_as_theorem(self):
        data = fixture()
        data["nodes"].append({"name": "Q", "kind": "conjecture", "signature": {"p": 1}})
        data["nodes"][2]["body"] = {"Q": 1}
        with self.assertRaisesRegex(CorpusError, "cannot use unproved conjecture"):
            Corpus(data)

    def test_unknown_dependency(self):
        data = fixture()
        data["nodes"][2]["body"] = {"not-exported": 4}
        with self.assertRaisesRegex(CorpusError, "unknown dependency"):
            Corpus(data)

    def test_cycle_is_not_silently_finite(self):
        data = fixture()
        data["nodes"][1]["body"] = {"t": 1}
        with self.assertRaisesRegex(CorpusError, "cyclic reference graph"):
            Corpus(data)

    def test_sorry_taints_dependents(self):
        data = fixture()
        data["nodes"].append({"name": "sorryAx", "kind": "primitive"})
        data["nodes"][1]["body"]["sorryAx"] = 1
        calc = Calculator(Corpus(data))
        self.assertTrue(calc.raw["t"]["admitted_dependency"])
        self.assertIsNone(calc.raw["t"]["score"])
        self.assertEqual([r["name"] for r in calc.rank()["ranking"]], ["trivial"])

    def test_zero_signature_is_undefined_not_infinity(self):
        data = fixture()
        data["nodes"][2]["signature"] = {}
        r = Calculator(Corpus(data)).raw["t"]
        self.assertIsNone(r["I0"])
        self.assertIsNone(r["score"])
        json.dumps(r, allow_nan=False)

    def test_duplicate_and_bad_counts(self):
        data = fixture()
        data["nodes"].append(copy.deepcopy(data["nodes"][0]))
        with self.assertRaisesRegex(CorpusError, "duplicate"):
            Corpus(data)
        for invalid in [True, False, -1, 0, 0.5, "3", None]:
            with self.subTest(invalid=invalid):
                data = fixture()
                data["nodes"][1]["signature"]["p"] = invalid
                with self.assertRaises(CorpusError):
                    Corpus(data)

    def test_query_missing_and_ambiguous(self):
        calc = Calculator(Corpus(fixture()))
        missing = calc.query("the Poincare conjecture")
        self.assertEqual(missing["status"], "insufficient_evidence")
        self.assertIsNone(missing["score"])
        self.assertEqual(calc.query("example proposition")["assessment"]["name"], "t")
        data = fixture()
        data["nodes"][3]["statement"] = "example proposition"
        self.assertEqual(Calculator(Corpus(data)).query("example proposition")["status"], "ambiguous_statement")

    def test_order_independent(self):
        data = fixture()
        a = Calculator(Corpus(data)).rank()["ranking"]
        data["nodes"].reverse()
        b = Calculator(Corpus(data)).rank()["ranking"]
        self.assertEqual(a, b)

    def test_deep_exact_expansion_without_recursive_traversal(self):
        nodes = [{"name": "p", "kind": "primitive"}]
        previous = "p"
        for k in range(1500):
            name = f"n{k}"
            nodes.append({"name": name, "kind": "definition", "signature": {}, "body": {previous: 2}})
            previous = name
        nodes.append({"name": "goal", "kind": "theorem", "signature": {"p": 1}, "body": {previous: 1}})
        calc = Calculator(Corpus({"schema_version": 1, "corpus_id": "deep", "nodes": nodes}))
        r = calc.raw["goal"]
        self.assertEqual(r["unwrapped_body"]["exact"], str(2**1500))
        self.assertIsNone(r["T0"]["value"])
        self.assertAlmostEqual(r["T0"]["log2"], 1499)
        self.assertEqual(r["depth"], 1501)
        json.dumps(calc.evaluate("goal"), allow_nan=False)

    def test_direct_metrics_do_not_invent_corpus_score(self):
        r = direct_metrics(10, 90, 100, 9000)
        self.assertEqual(r["T0"]["value"], 91)
        self.assertEqual(r["I0"]["value"], 9)
        self.assertIsNone(r["score"])
        self.assertIsNone(direct_metrics(10, None, 100, None)["I0"])
        with self.assertRaises(CorpusError):
            direct_metrics(0, 10, 0, 20)

    def test_percentile_ties_and_singletons(self):
        self.assertEqual(percentiles({"a": 1}), {"a": 50})
        self.assertEqual(percentiles({"a": 1, "b": 1}), {"a": 50, "b": 50})
        self.assertEqual(percentiles({"a": 1, "b": 2, "c": 3}), {"a": 0, "b": 50, "c": 100})

    def test_parameters(self):
        for key, value in [("alpha", 1), ("alpha", -1), ("alpha", math.nan),
                           ("beta", math.inf), ("beta", -0.1), ("smoothing", 0)]:
            with self.subTest(key=key, value=value), self.assertRaises(CorpusError):
                Calculator(Corpus(fixture()), **{key: value})


if __name__ == "__main__":
    unittest.main()
