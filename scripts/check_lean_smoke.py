#!/usr/bin/env python3
"""Meaningful post-export checks, only after actually running Lean."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maam import Calculator, Corpus

calc = Calculator(Corpus.load(sys.argv[1]))
for name in ("Demo.andRight", "Demo.modusPonens", "Demo.andSwap"):
    assert calc.raw[name]["eligible_for_score"], calc.raw[name]
assert calc.raw["Demo.admittedExample"]["admitted_dependency"]
assert calc.raw["Demo.admittedExample"]["score"] is None
and_right = calc.raw["Demo.andRight"]
assert and_right["wrapped_signature"] == 3
assert and_right["wrapped_body"] == 4
assert and_right["T0"]["value"] == 1
assert and_right["I0"]["value"] == 4/3
assert calc.convergence["l1_residual"] < 1e-12
print("Lean smoke checks passed; normal theorems eligible and sorry excluded.")
