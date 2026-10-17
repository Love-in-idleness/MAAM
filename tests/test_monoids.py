from collections import deque
from itertools import product
import random
import unittest

from maam import CorpusError
from maam.monoids import additive_lengths, coverage, free_length, free_sphere_worst, place_coverage


class MonoidTests(unittest.TestCase):
    def test_additive_dynamic_programme_matches_breadth_first_search(self):
        rng=random.Random(2026)
        for _ in range(15):
            macros=rng.sample(range(2,20),5)
            radius=60
            best={0:0};queue=deque([0])
            while queue:
                n=queue.popleft()
                for c in [1]+macros:
                    if n+c<=radius and n+c not in best:
                        best[n+c]=best[n]+1;queue.append(n+c)
            self.assertEqual(additive_lengths(radius,macros),[best[n] for n in range(radius+1)])

    def test_place_coverage_matches_exhaustive_digit_sum_cutoffs(self):
        for base in (2,3,5):
            radius=5000
            macros=[];power=base
            while power<=radius:
                macros.append(power);power*=base
            lengths=additive_lengths(radius,macros)
            for budget in range(9):
                observed=coverage(lengths,budget);exact=place_coverage(budget,base)
                if exact<radius:
                    self.assertEqual(observed["radius"],exact)
                else:
                    self.assertTrue(observed["right_censored"])
                    self.assertEqual(observed["lower_bound"],radius)

    def test_free_word_order_is_preserved(self):
        self.assertEqual(free_length("ababab",("a","b"),["aa","bb","aaaa","bbbb"]),6)
        self.assertEqual(free_length("aaaabb",("a","b"),["aa","bb","aaaa","bbbb"]),2)
        self.assertEqual(free_sphere_worst(6,("a","b"),["aa","bb","aaaa","bbbb"]),list(range(7)))

    def test_multidimensional_place_boundary_matches_exhaustive_vectors(self):
        radius=24
        for base in (2,3):
            macros=[];power=base
            while power<=radius:
                macros.append(power);power*=base
            lengths=additive_lengths(radius,macros)
            for dimension in (2,3):
                worst=[0]*(radius+1)
                for vector in product(range(radius+1),repeat=dimension):
                    total=sum(vector)
                    if total<=radius:
                        worst[total]=max(worst[total],sum(lengths[c] for c in vector))
                for budget in range(7):
                    result=coverage(worst,budget)
                    exact=place_coverage(budget,base,dimension)
                    if exact<radius:
                        self.assertEqual(result["radius"],exact)
                    else:
                        self.assertTrue(result["right_censored"])

    def test_finite_cutoff_does_not_claim_infinite_expansion(self):
        result=coverage([0,1,1,2],10)
        self.assertIsNone(result["radius"])
        self.assertTrue(result["right_censored"])
        self.assertEqual(result["lower_bound"],3)
        with self.assertRaises(CorpusError):
            additive_lengths(10,[0])


if __name__=="__main__":
    unittest.main()
