#!/usr/bin/env python3
"""Finite, exact checks of the source paper's monoid regimes."""
import csv
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from maam.monoids import additive_lengths, coverage, free_sphere_worst, place_coverage


def main():
    radius=65536
    powers=[2**j for j in range(1,17)]
    doublelog=[2**(2**j) for j in range(5)]
    squares=[k*k for k in range(1,math.isqrt(radius)+1)]
    models={"A1_powers_of_two":powers,"A1_double_logarithmic":doublelog,
            "A1_finite_macros":[2,5,13],"A1_squares":squares}
    curves=[]
    for name, macros in models.items():
        lengths=additive_lengths(radius,macros)
        for budget in range(19):
            result=coverage(lengths,budget)
            if name=="A1_powers_of_two":
                expected=place_coverage(budget,2)
                assert (result["right_censored"] and expected >= radius) or result["radius"]==expected
            if name=="A1_squares":
                assert max(lengths) <= 4
            curves.append({"model":name,"enumeration_radius":radius,**result})
    free_radius=12
    macros=[c*(2**j) for c in ("a","b") for j in range(1,4)]
    worst=free_sphere_worst(free_radius,("a","b"),macros)
    assert worst==list(range(free_radius+1))
    for budget in range(13):
        curves.append({"model":"F2_unary_power_macros","enumeration_radius":free_radius,
                       **coverage(worst,budget)})
    out=ROOT/"reports/monoids"
    out.mkdir(parents=True,exist_ok=True)
    with (out/"finite_coverage.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(curves[0]));writer.writeheader();writer.writerows(curves)
    summary={"source":"https://arxiv.org/abs/2603.20396v1", "models":list(models)+["F2_unary_power_macros"],
             "additive_radius":radius,"binary_word_radius":free_radius,
             "checks":{"powers_of_two_match_exact_digit_sum_boundary":True,
                       "all_integers_through_cutoff_use_at_most_four_squares":True,
                       "binary_unary_power_macros_have_worst_length_equal_to_radius_through_cutoff":True},
             "scope":"exact finite computations consistent with selected regimes; not proofs of the paper's universal asymptotics",
             "censoring":"radius=null means only a lower bound at the enumeration cutoff, never infinity",
             "method":"shortest additive representations and shortest noncommutative substring segmentations",
             "not_tested":["all polynomial-density macro sets in the free monoid",
                           "almost-sure probabilistic macro construction", "general nilpotent monoids"]}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
