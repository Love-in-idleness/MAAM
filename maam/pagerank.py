"""Personalised weighted PageRank, with edges from users to dependencies."""

import math

from .corpus import CorpusError


def pagerank(edges: dict[str, dict[str, int]], teleport: dict[str, float], *,
             alpha=0.85, tolerance=1e-12, max_iterations=1000) -> tuple[dict[str, float], dict]:
    if not math.isfinite(alpha) or not 0 <= alpha < 1:
        raise CorpusError("alpha must satisfy 0 <= alpha < 1")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise CorpusError("tolerance must be positive and finite")
    if type(max_iterations) is not int or max_iterations < 1:
        raise CorpusError("max_iterations must be a positive integer")
    if not edges or set(teleport) != set(edges):
        raise CorpusError("teleportation must cover exactly the graph vertices")
    if any(not math.isfinite(p) or p <= 0 for p in teleport.values()):
        raise CorpusError("teleportation entries must be positive and finite")
    z = math.fsum(teleport.values())
    p = {k: v / z for k, v in teleport.items()}
    rows = {}
    for u, deps in edges.items():
        if any(v not in edges or type(w) is not int or w <= 0 for v, w in deps.items()):
            raise CorpusError("invalid weighted edge")
        total = sum(deps.values())
        rows[u] = {v: w / total for v, w in deps.items()}

    def step(current):
        dangling = math.fsum(current[u] for u in rows if not rows[u])
        out = {v: (1 - alpha + alpha * dangling) * p[v] for v in rows}
        for u, deps in rows.items():
            mass = alpha * current[u]
            for v, weight in deps.items():
                out[v] += mass * weight
        return out

    current = dict(p)
    for iteration in range(1, max_iterations + 1):
        nxt = step(current)
        delta = math.fsum(abs(nxt[k] - current[k]) for k in rows)
        current = nxt
        if delta <= tolerance:
            check = step(current)
            residual = math.fsum(abs(check[k] - current[k]) for k in rows)
            return current, {"converged": True, "iterations": iteration,
                             "l1_residual": residual, "mass": math.fsum(current.values()),
                             "dangling_policy": "redistribute_to_personalisation"}
    raise CorpusError(f"PageRank did not converge in {max_iterations} iterations; no scores returned")
