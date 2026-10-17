#!/usr/bin/env python3
"""Recompute committed reports, allowing floating-point roundoff across platforms."""

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam import Calculator, Corpus, ProofSystem
from reproduce import toy_corpus


def compare(actual, expected, path="report"):
    if type(actual) is float and type(expected) in (float, int):
        if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-13):
            raise AssertionError(f"{path}: {actual} != {expected}")
    elif isinstance(actual, dict) and isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise AssertionError(f"{path}: different object keys")
        for k in actual:
            compare(actual[k], expected[k], path+"."+k)
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: different array lengths")
        for index, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, f"{path}[{index}]")
    elif type(actual) != type(expected) or actual != expected:
        raise AssertionError(f"{path}: {actual!r} != {expected!r}")


def main():
    corpus = Corpus.load(ROOT/"examples/toy_corpus.json")
    compare(json.loads((ROOT/"examples/toy_corpus.json").read_text()), toy_corpus())
    toy = Calculator(corpus)
    reports = {
        "paper_example.json": Calculator(Corpus.load(ROOT/"examples/paper_simple_lemma.json")).evaluate("simple_lemma"),
        "toy_ranking.json": toy.rank(),
        "unproved.json": toy.evaluate("Toy.OpenQuestion"),
        "finite_efficiency.json": ProofSystem.load(ROOT/"examples/finite_proofs.json").evaluate("D"),
    }
    runs = []
    for alpha in (0, .5, .85):
        for beta in (0, .5, 1):
            calc = Calculator(corpus, alpha=alpha, beta=beta)
            runs.append({"alpha": alpha, "beta": beta,
                         "ranking": [{"name": r["name"], "score": r["score"], "I1": r["I1"]}
                                     for r in calc.rank()["ranking"]]})
    reports["parameter_sensitivity.json"] = {"scope": "synthetic only; no human-interest calibration", "runs": runs}
    for filename, expected in reports.items():
        compare(json.loads((ROOT/"results"/filename).read_text()), expected, filename)
    print("5 committed reports reproduced; float tolerance rtol=1e-10, atol=1e-13.")


if __name__ == "__main__":
    main()
