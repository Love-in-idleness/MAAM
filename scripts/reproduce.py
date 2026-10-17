#!/usr/bin/env python3
"""Recompute calculator fixtures, status, and optional measured-index examples."""

import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", help="also regenerate paper-landmark assessments from the measured SQLite index")
    args = parser.parse_args()
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
    full_report = ROOT/"reports/mathlib/summary.json"
    monoid_report = ROOT/"reports/monoids/summary.json"
    baseline_report = ROOT/"results/mathlib_baseline.json"
    full = json.loads(full_report.read_text()) if full_report.exists() else None
    monoids = json.loads(monoid_report.read_text()) if monoid_report.exists() else None
    baseline = json.loads(baseline_report.read_text()) if baseline_report.exists() else None
    if args.index:
        from maam.index import score_index
        if full is None:
            parser.error("the measured reports/mathlib/summary.json is required with --index")
        assessments = []
        for landmark in full["landmarks"]:
            for match in landmark["matches"]:
                result = score_index(args.index, match["name"])
                if result["metadata"]["input_sha256"] != full["input_sha256"]:
                    parser.error("index provenance differs from reports/mathlib/summary.json")
                assessments.append(result["assessment"])
        write("results/mathlib_examples.json", {
            "revision": full["export"]["revision"], "input_sha256": full["input_sha256"],
            "exporter_commit": full["export"].get("exporter_commit"),
            "score_kind": "reference-basis I1 percentile among eligible theorems in the complete fixed corpus",
            "human_interest_calibrated": False, "assessments": assessments})
    pending = ["universal minimum proof complexity", "human mathematical-interest validation"]
    if full is None:
        pending += ["completed full Mathlib experiment; implemented workflow awaits a measured report"]
    else:
        pending += ["exact agreement with the authors' source filters and regression windows",
                    "maximum expansion differs from the paper; inspect reports/mathlib/max_expansion_dependencies.csv"]
    write("results/reproduction_status.json", {
        "calculator_checks": checks, "all_passed": all(checks.values()),
        "paper_equations": "T0/I0 algebra and weighted personalised PageRank implemented",
        "measurement": "reference-basis calculator; independently measured whole-declaration source tokens in the fixed-snapshot pipeline",
        "followup": "exact minimum on a supplied finite tree-proof hypergraph",
        "full_mathlib": ({"status": "measured", "report": "reports/mathlib/summary.json",
                          "revision": full["export"]["revision"], "input_sha256": full["input_sha256"],
                          "vertices_before_scc": full["vertices_before_scc"],
                          "vertices_after_scc": full["vertices_after_scc"],
                          "scope_counts": full.get("scope_counts"),
                          "dependency_evidence_sha256": full.get("dependency_evidence_sha256"),
                          "source_status_counts": full["source_status_counts"],
                          "baseline_graph_preserved": (full.get("dependency_evidence_sha256") == baseline.get("dependency_evidence_sha256")
                                                       if baseline and full.get("dependency_evidence_sha256") else None),
                          "reported_comparison": full["reported_comparison"],
                          "interpretation": "independent operational reproduction; numerical differences remain explicit"}
                         if full else {"status": "pipeline_implemented_not_yet_measured"}),
        "monoid_experiments": ({"status": "finite_checks_passed", "report": "reports/monoids/summary.json",
                                "checks": monoids["checks"], "scope": monoids["scope"]}
                               if monoids else {"status": "not_run"}),
        "not_reproduced": pending,
        "lean_adapter": "Lean 4.24.0 small-proposition and streaming/contextual-source-parser checks passed in GitHub Actions; see results/remote_validation.json and the fixed-snapshot workflow"})
    print(json.dumps({"checks": checks, "all_passed": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
