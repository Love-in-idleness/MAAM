# Metrics and Operational Definitions

[简体中文](METRICS.zh-CN.md)

## Measurement Object

MAAM evaluates the tuple `(proposition, supplied proof, corpus, primitive boundary, representation, parameters)`. A natural-language proposition alone does not determine these metrics.

For a nonprimitive node `u` in the dependency graph, let `w(u, v)` count occurrences of `v` across `u`'s signature and body together:

```math
U(u) = \sum_v w(u, v)\,U(v), \qquad U(g) = 1 \quad (g \text{ primitive}).
```

Summing separately over signature and body references gives `Us` and `Ub`. Referencing a theorem expands its combined signature-and-body length, following the paper's graph model. This is purely recursive reference substitution — it does not perform beta reduction, search for optimal definitions, or find shortest proofs.

- The general JSON corpus interface rejects cycles.
- The separate full-library Mathlib reproduction pipeline condenses strongly connected components (SCCs), removes internal edges, sums external multiplicities, and records each node's component size.
- Whole-package compression ([COMPRESSED_PACKAGES.md](COMPRESSED_PACKAGES.md)) is an independent sidecar using canonical JSON and standard-library compressors (`zlib`/`bzip2`); it does not replace the paper metrics below.

## Paper Metrics ([ABFM §5](https://arxiv.org/html/2603.20396v1#S5))

```math
T_0 = \frac{U_s + U_b}{W_s + W_b}, \qquad
I_0 = \frac{W_b}{W_s}, \qquad
I_{\mathrm{primitive}} = \frac{U_b}{U_s}.
```

- **Length conventions**: `references` mode sets `Ws` and `Wb` to signature and body reference counts; `source_tokens` mode uses caller-supplied token counts. Do not mix modes in one corpus.
- **Boundary & missing values**: Primitive nodes use `Ws = Us = 1`, `Wb = Ub = 0`. Axioms have no body and are not treated as proved theorems. Conjectures have `null` body lengths, so `T0`, `I0`, and overall scores are `null` (as are ratios with zero denominators).

## PageRank and Relative Score

Intrinsic metrics are normalised via logarithms (zero if the corpus maximum is zero; nodes with incomplete metrics or `sorry` taint contribute no intrinsic preference):

```math
\widetilde T(u) = \frac{\log(1 + T_0(u))}{\max_v \log(1 + T_0(v))}, \qquad
\widetilde I(u) = \frac{\log(1 + I_0(u))}{\max_v \log(1 + I_0(v))}.
```

```math
J_0(u) = \beta\,\widetilde T(u) + (1 - \beta)\,\widetilde I(u), \qquad
q(u) = (1 - \epsilon)\,\frac{J_0(u)}{\sum_v J_0(v)} + \frac{\epsilon}{N}.
```

Teleportation is uniform when all `J0` vanish, with explicit smoothing `epsilon = 10^-12`. Dependency edges point from user to dependency with transition probability proportional to multiplicity, and dangling-node mass is redistributed via `q`:

```math
\pi(v) = (1 - \alpha)\,q(v)
+ \alpha \sum_{u:\,W(u) > 0} \pi(u)\,\frac{w(u, v)}{W(u)}
+ \alpha\,q(v) \sum_{u:\,W(u) = 0} \pi(u), \qquad I_1(v) = \pi(v).
```

Defaults `alpha = 0.85` and `beta = 0.5` are editable engineering choices. Reports include iteration count, L1 stationary residual, and total mass; non-convergence raises an error.

The relative `score` (0–100) is computed only for `kind = theorem` nodes with complete metrics and no admission taint, using midranks for ties (50 for a singleton cohort):

```math
\operatorname{score}(u) = 100\,\frac{\#\{v : I_1(v) < I_1(u)\} + \tfrac{1}{2}(\#\{v : I_1(v) = I_1(u)\} - 1)}{n - 1}.
```

Scores are corpus- and parameter-relative and cannot be compared across different corpora or boundaries.

## Proof Efficiency ([BDF §3.4.1](https://arxiv.org/html/2604.06107v1#S3.SS4.SSS1))

Given an explicit finite inference hypergraph (axioms `A`, statement lengths `l`, rules `r => P`):

```math
m_F(P) = \min\left(\{l(P) : P \in A\} \cup \left\{l(P) + \sum_{s \in r} m_F(s) : r \Rightarrow P\right\}\right), \qquad
E_F(P) = \frac{m_F(P)}{l(P)}.
```

Cycles without an axiom or premise-free rule cannot prove themselves (underivable statements return `null`). This computes the exact minimum in the supplied finite **tree-proof** space (repeated subproofs are charged repeatedly); it is not DAG subproof sharing or a global minimum over all formal systems, and is not mixed into `score`.

## Known Interpretive Limits

- Static metrics do not measure specification adequacy, generality, AI comprehension difficulty, or future reuse value.
- Dependency expansion does not represent repeated learning of background theory; longer modular proofs can be easier to use than shorter monolithic proofs.
- Source size, kernel-term size, reference-tree expansion, and shared-declaration ledgers are distinct cost models and must not be conflated.
- Padding a proof can inflate `I0`; MAAM does not claim to find optimal proofs, and percentile scores are testable research signals rather than probabilities of mathematical value.
