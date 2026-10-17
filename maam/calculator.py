"""Freedman-lineage observables, with explicitly chosen operational conventions."""

import math

from .corpus import Corpus, CorpusError, natural
from .numeric import integer_summary, log1p_ratio, percentiles, ratio
from .pagerank import pagerank


def direct_metrics(signature_wrapped: int, body_wrapped: int | None,
                   signature_unwrapped: int | None, body_unwrapped: int | None) -> dict:
    """Four measured lengths -> the two ratios from ABFM §5, no guessed evidence."""
    natural(signature_wrapped, "signature_wrapped", positive=True)
    for key, value in [("body_wrapped", body_wrapped), ("signature_unwrapped", signature_unwrapped),
                       ("body_unwrapped", body_unwrapped)]:
        if value is not None:
            natural(value, key)
    if body_wrapped is None and body_unwrapped is not None:
        raise CorpusError("body_unwrapped supplied without a measured body_wrapped")
    total_w = signature_wrapped + body_wrapped if body_wrapped is not None else None
    total_u = (signature_unwrapped + body_unwrapped
               if signature_unwrapped is not None and body_unwrapped is not None else None)
    return {"T0": ratio(total_u, total_w), "I0": ratio(body_wrapped, signature_wrapped),
            "primitive_proof_to_statement": ratio(body_unwrapped, signature_unwrapped),
            "score": None,
            "notes": ["No I1 or percentile without an explicitly supplied comparison corpus.",
                      "These are measurements, not a validation of the proposition or its proof."]}


class Calculator:
    def __init__(self, corpus: Corpus, *, alpha=0.85, beta=0.5, smoothing=1e-12,
                 tolerance=1e-12, max_iterations=1000):
        if not math.isfinite(beta) or not 0 <= beta <= 1:
            raise CorpusError("beta must satisfy 0 <= beta <= 1")
        if not math.isfinite(smoothing) or not 0 < smoothing < 1:
            raise CorpusError("smoothing must satisfy 0 < smoothing < 1")
        self.corpus = corpus
        self.parameters = {"alpha": alpha, "beta": beta, "smoothing": smoothing,
                           "normalisation": "log1p_divide_by_corpus_max",
                           "score": "I1_midrank_percentile_among_eligible_theorems"}
        self.raw = {}
        totals: dict[str, int | None] = {}
        depths = {}
        taints = {}
        for name in corpus.order:
            n = corpus.nodes[name]
            taints[name] = n.admitted or name in {"sorryAx", "Lean.sorryAx"} or any(taints[d] for d in n.edges)
            depths[name] = 0 if n.kind == "primitive" else 1 + max((depths[d] for d in n.edges), default=-1)

            def expand(refs):
                if any(totals[d] is None for d in refs):
                    return None
                return sum(count * totals[d] for d, count in refs.items())

            if n.kind == "primitive":
                us, ub = 1, 0
            else:
                us = expand(n.signature)
                ub = None if n.kind == "conjecture" else expand(n.body or {})
            total = us + ub if us is not None and ub is not None else None
            totals[name] = total
            ws, wb = corpus.lengths(n)
            wt = ws + wb if wb is not None else None
            notes = []
            if n.kind == "conjecture":
                notes.append("unproved: no proof-dependent interest score is available")
            if ws == 0:
                notes.append("zero wrapped signature length under this measurement convention; I0 is undefined")
            if taints[name]:
                notes.append("admitted/sorry dependency: not eligible for a theorem score")
            self.raw[name] = {
                "name": name, "kind": n.kind, "statement": n.statement,
                "wrapped_signature": ws, "wrapped_body": wb,
                "unwrapped_signature": integer_summary(us) if us is not None else None,
                "unwrapped_body": integer_summary(ub) if ub is not None else None,
                "unwrapped_total": integer_summary(total) if total is not None else None,
                "depth": depths[name], "T0": ratio(total, wt), "I0": ratio(wb, ws),
                "primitive_proof_to_statement": ratio(ub, us),
                "direct_users": len(corpus.users[name]),
                "reference_occurrences_from_users": sum(corpus.users[name].values()),
                "user_domains": sorted({corpus.nodes[u].domain for u in corpus.users[name]
                                        if corpus.nodes[u].domain}),
                "admitted_dependency": taints[name], "notes": notes,
            }
        # Conjectures, undefined ratios and admitted proofs do not supply interest evidence.
        available = {k: v for k, v in self.raw.items()
                     if v["T0"] is not None and v["I0"] is not None and not v["admitted_dependency"]}
        t = {k: log1p_ratio(v["T0"]) for k, v in available.items()}
        i = {k: log1p_ratio(v["I0"]) for k, v in available.items()}
        mt, mi = max(t.values(), default=0), max(i.values(), default=0)
        j = {k: beta * (t.get(k, 0) / mt if mt else 0)
                + (1 - beta) * (i.get(k, 0) / mi if mi else 0) for k in corpus.nodes}
        z = math.fsum(j.values())
        size = len(corpus.nodes)
        teleport = {k: ((1 - smoothing) * j[k] / z + smoothing / size if z else 1 / size)
                    for k in corpus.nodes}
        pi, self.convergence = pagerank(corpus.edges, teleport, alpha=alpha,
                                        tolerance=tolerance, max_iterations=max_iterations)
        eligible = {k: pi[k] for k in available if corpus.nodes[k].kind == "theorem"}
        scores = percentiles(eligible)
        self.cohort_size = len(scores)
        for k, v in self.raw.items():
            v.update({"J0": j[k], "teleportation": teleport[k], "I1": pi[k],
                      "score": scores.get(k), "score_kind": "corpus_relative_heuristic_percentile",
                      "eligible_for_score": k in scores})
            if k not in available:
                v["notes"].append("I1 is graph mass only here; unavailable intrinsic metrics were not imputed")
            if k in scores and len(scores) < 20:
                v["notes"].append("small comparison cohort: this percentile is not a calibrated judgement of mathematical value")

    def metadata(self) -> dict:
        return {"corpus_id": self.corpus.corpus_id, "corpus_sha256": self.corpus.sha256,
                "length_basis": self.corpus.length_basis, "nodes": len(self.corpus.nodes),
                "comparison_theorems": self.cohort_size, "provenance": self.corpus.provenance,
                "parameters": self.parameters, "pagerank": self.convergence,
                "measurement_status": ("paper_alternative_reference_length" if self.corpus.length_basis == "references"
                                       else "caller_supplied_source_token_lengths"),
                "interpretation": "relative research heuristic; not an objective probability of mathematical interest",
                "formal_correctness": "not checked by the Python calculator; inspect corpus provenance",
                "sources": ["https://arxiv.org/html/2603.20396v1#S5",
                            "https://arxiv.org/abs/2604.06107v1"]}

    def evaluate(self, name: str) -> dict:
        if name not in self.raw:
            raise CorpusError(f"unknown declaration: {name}")
        row = self.raw[name]
        return {"status": "evaluated" if row["eligible_for_score"] else "metrics_only",
                "metadata": self.metadata(), "assessment": row}

    def query(self, statement: str) -> dict:
        matches = [n for n, node in self.corpus.nodes.items() if node.statement == statement]
        if len(matches) == 1:
            return self.evaluate(matches[0])
        return {"status": "ambiguous_statement" if matches else "insufficient_evidence",
                "statement": statement, "score": None, "candidates": matches,
                "required": ["a matching formal declaration", "a proof or an explicit unproved status",
                             "closed signature/body reference counts", "an identified comparison corpus"],
                "metadata": self.metadata()}

    def rank(self, limit: int | None = None) -> dict:
        rows = [v for v in self.raw.values() if v["eligible_for_score"]]
        rows.sort(key=lambda v: (-v["I1"], v["name"]))
        if limit is not None:
            natural(limit, "limit", positive=True)
            rows = rows[:limit]
        return {"metadata": self.metadata(), "ranking": rows}
