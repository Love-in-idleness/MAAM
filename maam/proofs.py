"""Minimum tree-proof cost in a supplied finite AND/OR hypergraph.

This is not the uncomputable minimum over all mathematical proofs, and it does
not model shared-subproof DAG optimisation. Every premise occurrence is charged.
"""

from collections import Counter, defaultdict
import heapq
import json
from pathlib import Path

from .corpus import CorpusError, natural
from .numeric import integer_summary, ratio


class ProofSystem:
    def __init__(self, data: dict):
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise CorpusError("expected a proof system with schema_version: 1")
        self.system_id = data.get("system_id")
        if not isinstance(self.system_id, str) or not self.system_id:
            raise CorpusError("system_id is required")
        self.lengths = data.get("statement_lengths")
        if not isinstance(self.lengths, dict) or not self.lengths:
            raise CorpusError("statement_lengths must be a non-empty object")
        for name, length in self.lengths.items():
            if not isinstance(name, str) or not name:
                raise CorpusError("statement names must be non-empty strings")
            natural(length, f"length of {name}", positive=True)
        axioms = data.get("axioms", [])
        rules = data.get("rules", [])
        if not isinstance(axioms, list) or not isinstance(rules, list):
            raise CorpusError("axioms and rules must be arrays")
        if any(not isinstance(a, str) or a not in self.lengths for a in axioms):
            raise CorpusError("axioms must be known statements")
        self.axioms = set(axioms)
        self.rules = []
        seen = set()
        for r in rules:
            if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]:
                raise CorpusError("each rule requires a non-empty id")
            if r["id"] in seen:
                raise CorpusError(f"duplicate rule id: {r['id']}")
            seen.add(r["id"])
            conclusion, premises = r.get("conclusion"), r.get("premises")
            if not isinstance(conclusion, str) or conclusion not in self.lengths:
                raise CorpusError(f"{r['id']}: unknown conclusion")
            if not isinstance(premises, list) or any(not isinstance(p, str) or p not in self.lengths for p in premises):
                raise CorpusError(f"{r['id']}: premises must be known statements")
            self.rules.append({"id": r["id"], "conclusion": conclusion, "premises": list(premises)})

    @classmethod
    def load(cls, path: str | Path):
        with open(path, encoding="utf-8") as handle:
            return cls(json.load(handle))

    def solve(self, *, reusable: str | None = None) -> tuple[dict[str, int], dict[str, dict]]:
        if reusable is not None and reusable not in self.lengths:
            raise CorpusError(f"unknown reusable proposition: {reusable}")
        pending = []
        partial = []
        watchers = defaultdict(list)
        best, witness, final = {}, {}, set()
        heap = []

        def relax(name, cost, reason):
            if name not in best or cost < best[name]:
                best[name], witness[name] = cost, reason
                heapq.heappush(heap, (cost, name))

        for name in sorted(self.axioms | ({reusable} if reusable else set())):
            relax(name, self.lengths[name], {"kind": "reusable" if name == reusable else "axiom"})
        for index, rule in enumerate(self.rules):
            counts = Counter(rule["premises"])
            pending.append(sum(counts.values()))
            partial.append(self.lengths[rule["conclusion"]])
            for p, multiplicity in counts.items():
                watchers[p].append((index, multiplicity))
            if not counts:
                relax(rule["conclusion"], partial[index], {"kind": "rule", "rule": rule["id"]})
        while heap:
            cost, name = heapq.heappop(heap)
            if name in final or best[name] != cost:
                continue
            final.add(name)
            for index, multiplicity in watchers[name]:
                pending[index] -= multiplicity
                partial[index] += multiplicity * cost
                if pending[index] == 0:
                    rule = self.rules[index]
                    relax(rule["conclusion"], partial[index], {"kind": "rule", "rule": rule["id"]})
        return best, witness

    def evaluate(self, name: str) -> dict:
        if name not in self.lengths:
            raise CorpusError(f"unknown proposition: {name}")
        costs, witness = self.solve()
        cost = costs.get(name)
        return {"system_id": self.system_id, "name": name,
                "status": "derived" if cost is not None else "not_derivable_in_supplied_system",
                "statement_length": self.lengths[name],
                "minimum_tree_proof_cost": integer_summary(cost) if cost is not None else None,
                "E_finite": ratio(cost, self.lengths[name]), "witness": witness.get(name),
                "cost_witnesses": {n: {"cost": integer_summary(c), **witness[n]} for n, c in sorted(costs.items())},
                "scope": "exact minimum for the supplied finite tree-proof hypergraph; each premise occurrence is counted",
                "global_minimum_status": "not computed; no search over all proofs, equivalent statements, or formal systems",
                "correctness": "rule validity is supplied by the caller, not verified by this solver",
                "source": "https://arxiv.org/html/2604.06107v1#S3.SS4.SSS1"}

    def reuse_gain(self, name: str, goals: list[str]) -> dict:
        """Amortised savings after paying once to build a reusable theorem.

        This operational utility metric is our extension, not a paper formula.
        """
        if len(set(goals)) != len(goals) or any(g not in self.lengths or g == name for g in goals):
            raise CorpusError("goals must be distinct known statements other than the reusable theorem")
        if not goals:
            raise CorpusError("at least one goal is required")
        before, _ = self.solve()
        after, _ = self.solve(reusable=name)
        if name not in before:
            return {"status": "theorem_unproved", "name": name, "net_savings": None}
        unavailable = [g for g in goals if g not in before or g not in after]
        if unavailable:
            return {"status": "unreachable_goals", "goals": unavailable, "net_savings": None}
        saved = sum(before[g] - after[g] for g in goals)
        construction = before[name]
        return {"status": "evaluated", "name": name, "goals": goals,
                "gross_savings": saved, "construction_cost": construction,
                "net_savings": saved - construction,
                "attribution": "MAAM operational extension; not a published Freedman metric"}
