#!/usr/bin/env python3
"""Analyse a streaming Lean export without retaining every expression record.

The published observables use SCC-condensed components. Internal SCC edges are
removed and external multiplicities summed. Source-range measurements are kept
separate from the reference-basis interest calculator; missing source is never
zero-imputed. Optional scientific dependencies are isolated from the core CLI.
"""
from array import array
from collections import Counter, deque
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

import numpy as np
from scipy.sparse import csr_matrix, coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import linregress

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from maam.numeric import percentiles


def records(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def grouped(x, y, valid=None):
    if valid is not None:
        x, y = x[valid], y[valid]
    buckets = {}
    for a, b in zip(x, y):
        if np.isfinite(a) and np.isfinite(b):
            buckets.setdefault(int(a), []).append(float(b))
    return [{"x": k, "median": float(np.median(v)), "count": len(v)} for k, v in sorted(buckets.items())]


def fit(rows, low, high, minimum_count=20):
    selected = [r for r in rows if low <= r["x"] <= high and r["count"] >= minimum_count]
    if len(selected) < 2:
        return {"status": "insufficient_bins", "bins": len(selected), "range": [low, high], "minimum_count": minimum_count}
    r = linregress([v["x"] for v in selected], [v["median"] for v in selected])
    return {"status": "fitted", "slope": float(r.slope), "intercept": float(r.intercept),
            "r_squared": float(r.rvalue**2), "stderr": float(r.stderr), "bins": len(selected),
            "range": [low, high], "minimum_count": minimum_count,
            "weighting": "unweighted regression of exact-bucket medians; prespecified range"}


def save_rows(path, rows, fields=None):
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            return
        writer = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def condensed(graph):
    count, labels = connected_components(graph, directed=True, connection="strong")
    sizes = np.bincount(labels, minlength=count)
    rows = np.repeat(np.arange(graph.shape[0], dtype=np.int32), np.diff(graph.indptr))
    self_loops = rows == graph.indices
    cyclic = sizes > 1
    cyclic[labels[rows[self_loops]]] = True
    source, target = labels[rows], labels[graph.indices]
    keep = source != target
    dag = coo_matrix((graph.data[keep], (source[keep], target[keep])), shape=(count, count)).tocsr()
    dag.sum_duplicates()
    return dag, labels, sizes, cyclic


def expansion(dag, admitted=None):
    n = dag.shape[0]
    reverse = dag.transpose().tocsr()
    pending = np.diff(dag.indptr).copy()
    queue = deque(np.flatnonzero(pending == 0).tolist())
    values = [0] * n
    depths = np.zeros(n, dtype=np.int32)
    tainted = np.zeros(n, dtype=bool) if admitted is None else admitted.copy()
    done = 0
    while queue:
        u = queue.popleft()
        start, end = dag.indptr[u:u+2]
        if start == end:
            values[u] = 1
        else:
            deps = dag.indices[start:end]
            values[u] = sum(int(w)*values[int(v)] for v, w in zip(deps, dag.data[start:end]))
            depths[u] = 1 + max(int(depths[v]) for v in deps)
            tainted[u] |= any(tainted[v] for v in deps)
        done += 1
        for user in reverse.indices[reverse.indptr[u]:reverse.indptr[u+1]]:
            pending[user] -= 1
            if pending[user] == 0:
                queue.append(int(user))
    if done != n:
        raise ValueError("condensation graph is unexpectedly cyclic")
    return values, depths, tainted


def interest(dag, values, ws, wb, tainted, theorem, alpha=.85, beta=.5):
    logu = np.array([math.log2(v) for v in values])
    wt = ws + wb
    good = (ws > 0) & (wt > 0) & ~tainted
    t = np.zeros(len(values))
    t[good] = np.logaddexp(0, (logu[good]-np.log2(wt[good]))*math.log(2))
    i = np.zeros(len(values))
    i[good] = np.log1p(wb[good] / ws[good])
    j = beta * (t/t.max() if t.max() else t) + (1-beta)*(i/i.max() if i.max() else i)
    q = (1-1e-12)*j/j.sum()+1e-12/len(j) if j.sum() else np.full(len(j), 1/len(j))
    weights = np.asarray(dag.sum(axis=1)).ravel().astype(float)
    sinks = weights == 0
    divisor = np.where(sinks, 1, weights)
    matrix = dag.transpose().tocsr()
    p = q.copy()
    for iteration in range(1, 1001):
        nxt = (1-alpha+alpha*p[sinks].sum())*q + alpha*matrix.dot(p/divisor)
        if np.abs(nxt-p).sum() <= 1e-12:
            p = nxt
            check = (1-alpha+alpha*p[sinks].sum())*q + alpha*matrix.dot(p/divisor)
            residual = float(np.abs(check-p).sum())
            break
        p = nxt
    else:
        raise ValueError("personalised PageRank did not converge")
    eligible = theorem & good
    scored = percentiles({str(k): float(p[k]) for k in np.flatnonzero(eligible)})
    scores = np.full(len(p), np.nan)
    for k, v in scored.items():
        scores[int(k)] = v
    return p, scores, {"alpha": alpha, "beta": beta, "length_basis": "references",
                        "iterations": iteration, "l1_residual": residual, "mass": float(p.sum()),
                        "eligible_theorems": int(eligible.sum())}


def analyse(input_path, output, index_path, config_path):
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text())
    names, kinds, modules, source_tokens, source_status, unsafe = [], [], [], [], [], []
    metadata = None
    for row in records(input_path):
        if row["record"] == "metadata":
            metadata = row
            continue
        names.append(row["name"])
        kinds.append(row["kind"])
        modules.append(sys.intern(row.get("module", "")))
        source = row.get("source", {})
        source_status.append(sys.intern(source.get("status", "absent")))
        source_tokens.append(source.get("tokens", -1))
        unsafe.append(row.get("unsafe", False))
    if metadata is None or not names:
        raise ValueError("missing export metadata or nodes")
    index = {name: i for i, name in enumerate(names)}
    if len(index) != len(names):
        raise ValueError("duplicate exported declarations")
    n = len(names)
    print(f"Read {n} vertices", flush=True)
    columns, weights, ptr = array("i"), array("q"), array("q", [0])
    ws, wb = np.zeros(n, dtype=np.int64), np.zeros(n, dtype=np.int64)
    primitive = np.array([k == "primitive" for k in kinds])
    cursor = 0
    for row in records(input_path):
        if row["record"] != "node":
            continue
        if row["name"] != names[cursor]:
            raise ValueError("input order changed between passes")
        refs = Counter(row.get("signature", {}))
        ws[cursor] = sum(refs.values())
        body = row.get("body") or {}
        wb[cursor] = sum(body.values())
        refs.update(body)
        for dep, weight in refs.items():
            if dep not in index or type(weight) is not int or weight <= 0:
                raise ValueError(f"invalid dependency: {row['name']} -> {dep}")
            columns.append(index[dep])
            weights.append(weight)
        ptr.append(len(columns))
        cursor += 1
    ws[primitive], wb[primitive] = 1, 0
    graph = csr_matrix((np.frombuffer(weights, dtype=np.int64),
                        np.frombuffer(columns, dtype=np.int32), np.frombuffer(ptr, dtype=np.int64)), shape=(n, n))
    dag, labels, sizes, cyclic = condensed(graph)
    print(f"Condensed to {dag.shape[0]} vertices ({int(cyclic.sum())} cyclic components)", flush=True)
    admitted = np.zeros(dag.shape[0], dtype=bool)
    for name in ("sorryAx", "Lean.sorryAx"):
        if name in index:
            admitted[labels[index[name]]] = True
    values, depth, tainted = expansion(dag, admitted)
    logu = np.array([math.log2(v) for v in values])
    cws = np.bincount(labels, weights=ws, minlength=len(values))
    cwb = np.bincount(labels, weights=wb, minlength=len(values))
    is_theorem = (np.bincount(labels, weights=np.array([k == "theorem" for k in kinds]), minlength=len(values)) == 1) & (sizes == 1)
    pi, scores, rank_info = interest(dag, values, cws, cwb, tainted, is_theorem)
    raw_source = np.array(source_tokens, dtype=np.int64)
    named = np.array([s == "named_source" for s in source_status]) & (raw_source > 0)
    any_source = (raw_source > 0)
    raw_source[primitive] = 1
    named[primitive], any_source[primitive] = True, True

    def wrapped(mask):
        counts = np.bincount(labels, weights=mask, minlength=len(values))
        total = np.bincount(labels, weights=np.where(mask, raw_source, 0), minlength=len(values))
        total[counts != sizes] = np.nan
        return total

    source_wrapped, any_wrapped = wrapped(named), wrapped(any_source)
    med_depth = grouped(depth, logu)
    med_source = grouped(source_wrapped, logu)
    med_wrapped = grouped(depth, source_wrapped)
    med_any_source = grouped(any_wrapped, logu)
    med_any_wrapped = grouped(depth, any_wrapped)
    for filename, rows in [("log_unwrapped_by_depth.csv", med_depth), ("log_unwrapped_by_source_tokens.csv", med_source),
                            ("source_tokens_by_depth.csv", med_wrapped), ("log_unwrapped_by_any_source_tokens.csv", med_any_source),
                            ("any_source_tokens_by_depth.csv", med_any_wrapped)]:
        save_rows(output/filename, rows)
    expected = config["reported"]
    max_c = int(np.argmax(logu))
    max_names = [names[k] for k in np.flatnonzero(labels == max_c)]
    landmarks = []
    for target in config["landmarks"]:
        matches = [k for k, name in enumerate(names) if
                   (name == target["name"] if "name" in target else name.endswith(target["suffix"]))
                   and modules[k] == target["module"]]
        landmarks.append({"expected": target, "matches": [
            {"name": names[k], "source_status": source_status[k], "source_tokens": int(raw_source[k]),
             "unwrapped_log10": float(logu[labels[k]]/math.log2(10)), "depth": int(depth[labels[k]])}
            for k in matches]})
    status_counts = dict(Counter(source_status))
    with open(input_path, "rb") as raw_input:
        fingerprint = hashlib.file_digest(raw_input, "sha256").hexdigest()
    summary = {
        "export": metadata, "input_sha256": fingerprint,
        "vertices_before_scc": n, "vertices_after_scc": len(values),
        "edges_before_scc": int(graph.nnz), "edges_after_scc": int(dag.nnz),
        "cyclic_components": int(cyclic.sum()), "vertices_in_cyclic_components": int(sizes[cyclic].sum()),
        "scc_policy": "remove internal arcs, sum external multiplicities, assign each condensed sink primitive length 1",
        "unsafe_definitions_retained": sum(unsafe), "maximum_depth": int(depth.max()),
        "maximum_unwrapped_log10": float(logu.max()/math.log2(10)), "maximising_declarations": max_names,
        "source_status_counts": status_counts, "named_source_components": int(np.isfinite(source_wrapped).sum()),
        "any_source_components": int(np.isfinite(any_wrapped).sum()),
        "fits": {"log2_unwrapped_by_depth": fit(med_depth, 10, 250),
                 "log2_unwrapped_by_source_tokens": fit(med_source, 10, 200),
                 "source_tokens_by_depth": fit(med_wrapped, 10, 250)},
        "reported_comparison": {"expected": expected,
            "vertex_count_difference_before_scc": n-expected["vertices_before_scc"],
            "vertex_count_difference_after_scc": len(values)-expected["vertices_after_scc"]},
        "landmarks": landmarks, "reference_basis_interest": rank_info,
        "interpretation": "independent operational reproduction; discrepancies are reported, not fitted away",
        "source_measurement": "full declaration-range Lean lexical tokens; comments excluded; named and shared/generated ranges analysed separately",
        "unresolved": ["paper does not specify exact source-range filtering or regression windows",
                       "no source-level signature/proof token split is inferred from whole-range counts",
                       "no empirical validation against human interest judgements"]}
    write_json(output/"summary.json", summary)
    cycles = [{"members": [names[k] for k in np.flatnonzero(labels == c)], "size": int(sizes[c])}
              for c in np.flatnonzero(cyclic)]
    write_json(output/"cycles.json", cycles)
    top = sorted((k for k in range(n) if kinds[k] == "theorem" and np.isfinite(scores[labels[k]])),
                 key=lambda k: (-pi[labels[k]], names[k]))[:100]
    save_rows(output/"top_theorems_reference_basis.csv", [{
        "name": names[k], "module": modules[k], "score_reference": float(scores[labels[k]]),
        "I1_reference": float(pi[labels[k]]), "I0_reference": float(wb[k]/ws[k]) if ws[k] else None,
        "unwrapped_log2": float(logu[labels[k]]), "source_tokens": int(raw_source[k]),
        "source_status": source_status[k], "depth": int(depth[labels[k]])} for k in top])
    if index_path:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(index_path)
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO metadata VALUES ('summary', ?)", (json.dumps(summary),))
        db.execute("CREATE TABLE metrics (name TEXT PRIMARY KEY, module TEXT, kind TEXT, component_size INTEGER, depth INTEGER, unwrapped_exact TEXT, unwrapped_log2 REAL, wrapped_source INTEGER, source_status TEXT, signature_references INTEGER, body_references INTEGER, I1_reference REAL, score_reference REAL, admitted_dependency INTEGER)")
        db.executemany("INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            (name, modules[k], kinds[k], int(sizes[labels[k]]), int(depth[labels[k]]), str(values[labels[k]]),
             float(logu[labels[k]]), int(raw_source[k]) if raw_source[k] >= 0 else None, source_status[k],
             int(ws[k]), int(wb[k]), float(pi[labels[k]]),
             float(scores[labels[k]]) if np.isfinite(scores[labels[k]]) and kinds[k] == "theorem" else None,
             int(tainted[labels[k]])) for k, name in enumerate(names)))
        db.commit()
        db.close()
    plot(output, logu, depth, source_wrapped, med_depth, med_source, med_wrapped)
    print(json.dumps({k: summary[k] for k in ("vertices_before_scc", "vertices_after_scc", "maximum_depth", "maximum_unwrapped_log10", "source_status_counts")}, indent=2))
    return summary


def plot(output, logu, depth, wrapped, med_depth, med_source, med_wrapped):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 140, "axes.spines.top": False, "axes.spines.right": False})
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, data, label in zip(axs, [logu, wrapped[np.isfinite(wrapped)], depth],
                               ["log2 primitive expansion", "source tokens (named ranges)", "dependency depth"]):
        ax.hist(data, bins=70, color="#356b85")
        ax.set(xlabel=label, ylabel="components", yscale="log")
    fig.suptitle("Fixed-snapshot reproduction: distributions")
    fig.tight_layout()
    fig.savefig(output/"figure2_distributions.png")
    plt.close(fig)
    for filename, rows, xlabel, ylabel in [
        ("figure3_expansion_by_tokens.png", med_source, "source tokens (named ranges)", "median log2 primitive expansion"),
        ("figure4_tokens_by_depth.png", med_wrapped, "dependency depth", "median source tokens (named ranges)"),
        ("figure5_expansion_by_depth.png", med_depth, "dependency depth", "median log2 primitive expansion")]:
        fig, ax = plt.subplots(figsize=(7, 4))
        if rows:
            ax.scatter([r["x"] for r in rows], [r["median"] for r in rows], s=9, alpha=.65, color="#356b85")
        ax.set(xlabel=xlabel, ylabel=ylabel, title="Independent fixed-snapshot measurement")
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(output/filename)
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT/"scripts/paper_config.json")
    args = parser.parse_args()
    analyse(args.input, args.output, args.index, args.config)
