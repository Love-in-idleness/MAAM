import math
import random
import unittest

from maam.corpus import CorpusError
from maam.pagerank import pagerank


def dense_stationary(edges, teleport, alpha):
    """Independent small-graph oracle: solve (I-alpha*M)x=(1-alpha)*p."""
    names = list(edges)
    z = sum(teleport.values())
    p = [teleport[k] / z for k in names]
    n = len(names)
    rows = [[float(i == j) for j in range(n)] + [(1-alpha)*p[i]] for i in range(n)]
    for j, u in enumerate(names):
        total = sum(edges[u].values())
        for i, v in enumerate(names):
            transition = edges[u].get(v, 0) / total if total else p[i]
            rows[i][j] -= alpha * transition
    for i in range(n):
        pivot = max(range(i, n), key=lambda k: abs(rows[k][i]))
        rows[i], rows[pivot] = rows[pivot], rows[i]
        d = rows[i][i]
        rows[i] = [v / d for v in rows[i]]
        for k in range(n):
            if k != i:
                factor = rows[k][i]
                rows[k] = [a - factor*b for a, b in zip(rows[k], rows[i])]
    return {k: rows[i][-1] for i, k in enumerate(names)}


class PageRankTests(unittest.TestCase):
    def test_direction_and_dangling_analytic_solution(self):
        result, info = pagerank({"a": {"b": 3}, "b": {}}, {"a": .8, "b": .2}, alpha=.5)
        self.assertAlmostEqual(result["a"], 4/7, places=11)
        self.assertAlmostEqual(result["b"], 3/7, places=11)
        self.assertAlmostEqual(info["mass"], 1, places=12)
        self.assertLess(info["l1_residual"], 1e-12)

    def test_against_dense_linear_system_on_random_weighted_graphs(self):
        rng = random.Random(20261017)
        for _ in range(25):
            names = [f"n{k}" for k in range(7)]
            edges = {u: {v: rng.randint(1, 9) for v in names if rng.random() < .25} for u in names}
            p = {u: rng.random() + .01 for u in names}
            alpha = rng.choice([0, .2, .5, .85, .95])
            actual, _ = pagerank(edges, p, alpha=alpha, tolerance=1e-13)
            expected = dense_stationary(edges, p, alpha)
            for name in names:
                self.assertAlmostEqual(actual[name], expected[name], places=11)

    def test_all_sinks_and_no_edges(self):
        scores, _ = pagerank({"a": {}, "b": {}}, {"a": 1, "b": 3})
        self.assertAlmostEqual(scores["a"], .25)
        self.assertAlmostEqual(scores["b"], .75)

    def test_zero_alpha_is_personalisation(self):
        scores, _ = pagerank({"a": {"b": 1}, "b": {}}, {"a": 1, "b": 3}, alpha=0)
        self.assertEqual(scores, {"a": .25, "b": .75})

    def test_nonconvergence_is_an_error(self):
        with self.assertRaisesRegex(CorpusError, "did not converge"):
            pagerank({"a": {"b": 1}, "b": {}}, {"a": .8, "b": .2},
                     alpha=.999, tolerance=1e-30, max_iterations=1)

    def test_invalid_probability(self):
        for p in [{"a": 0}, {"a": math.nan}, {"a": -1}, {"b": 1}]:
            with self.subTest(p=p), self.assertRaises(CorpusError):
                pagerank({"a": {}}, p)


if __name__ == "__main__":
    unittest.main()
