#!/usr/bin/env python3
"""Deterministic calculator fixtures and reports. Not a full Mathlib replication."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maam import Calculator, Corpus, ProofSystem  # noqa: E402


def write(relative, data):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def toy_corpus():
    nodes = [{"name": "Primitive", "kind": "primitive"}]
    previous = "Primitive"
    for k in range(1, 13):
        name = f"Toy.Definition{k:02}"
        nodes.append({"name": name, "kind": "definition", "signature": {"Primitive": 1},
                      "body": {previous: 2}, "domain": "toy.definitions"})
        previous = name
    nodes += [
        {"name": "Toy.Trivial", "kind": "theorem", "signature": {"Primitive": 2},
         "body": {"Primitive": 1}, "domain": "toy.logic"},
        {"name": "Toy.StructuralLemma", "kind": "theorem", "signature": {"Primitive": 2},
         "body": {previous: 4}, "domain": "toy.algebra"},
        {"name": "Toy.IsolatedLongProof", "kind": "theorem", "signature": {"Primitive": 2},
         "body": {"Primitive": 2000}, "domain": "toy.padding"},
        {"name": "Toy.OpenQuestion", "kind": "conjecture", "signature": {previous: 1},
         "statement": "An unproved toy conjecture"},
    ]
    for k in range(8):
        nodes.append({"name": f"Toy.Corollary{k}", "kind": "theorem",
                      "signature": {"Primitive": 2}, "body": {"Toy.StructuralLemma": k+1},
                      "domain": "toy.analysis" if k % 2 else "toy.geometry"})
    return {"schema_version": 1, "corpus_id": "synthetic-compression-reuse-v1", "length_basis": "references",
            "provenance": {"kind": "synthetic", "seed": None,
                           "purpose": "exercise hierarchy, reuse, proof padding, and missing-proof handling",
                           "not_human_interest_ground_truth": True}, "nodes": nodes}


def main():
    write("examples/toy_corpus.json", toy_corpus())
    paper = Calculator(Corpus.load(ROOT/"examples/paper_simple_lemma.json"))
    toy = Calculator(Corpus.load(ROOT/"examples/toy_corpus.json"))
    finite = ProofSystem.load(ROOT/"examples/finite_proofs.json")
    write("results/paper_example.json", paper.evaluate("simple_lemma"))
    write("results/toy_ranking.json", toy.rank())
    write("results/finite_efficiency.json", finite.evaluate("D"))
    write("results/unproved.json", toy.evaluate("Toy.OpenQuestion"))
    ablation = []
    for alpha in (0, .5, .85):
        for beta in (0, .5, 1):
            calc = Calculator(Corpus.load(ROOT/"examples/toy_corpus.json"), alpha=alpha, beta=beta)
            ablation.append({"alpha": alpha, "beta": beta,
                             "ranking": [{"name": r["name"], "score": r["score"], "I1": r["I1"]}
                                         for r in calc.rank()["ranking"]]})
    write("results/parameter_sensitivity.json", {"scope": "synthetic only; no human-interest calibration", "runs": ablation})
    checks = {
        "paper_reference_I0": paper.raw["simple_lemma"]["I0"]["value"] == 4/3,
        "paper_reference_T0": paper.raw["simple_lemma"]["T0"]["value"] == 1,
        "finite_E": finite.evaluate("D")["E_finite"]["value"] == 16/5,
        "open_question_not_scored": toy.raw["Toy.OpenQuestion"]["score"] is None,
        "pagerank_residual": toy.convergence["l1_residual"] < 1e-12,
    }
    write("results/reproduction_status.json", {
        "calculator_checks": checks, "all_passed": all(checks.values()),
        "paper_equations": "T0/I0 algebra and weighted personalised PageRank implemented",
        "measurement": "reference counts; not source-token counts",
        "followup": "exact minimum on a supplied finite tree-proof hypergraph",
        "not_reproduced": ["full Mathlib snapshot extraction and source-token figures",
                           "SCC condensation", "published empirical growth fits",
                           "universal minimum proof complexity", "human mathematical-interest validation"],
        "lean_adapter": "not compiled locally; run the optional pinned-toolchain workflow"})
    print(json.dumps({"checks": checks, "all_passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
