# MAAM

[简体中文](README.zh-CN.md)

MAAM is a research toolkit for measuring how formal mathematics is organised in Lean. It computes static compression and dependency metrics over Lean declarations, and evaluates the full cost of introducing reusable theory packages (definitions, lemmas, and bridges) into a fixed base library.

## Quick Start

Requires Python 3.11+ (core commands use only the Python standard library):

```bash
python -m maam score --corpus examples/paper_simple_lemma.json --name simple_lemma --format text
python -m maam rank --corpus examples/toy_corpus.json --format text
```

The first command measures a supplied proof of `A ∧ B → B`, reporting reductive compression `T0 = 1` and proof-to-statement ratio `I0 = 4/3`. The second ranks a small synthetic corpus. All metrics depend on the chosen corpus, representation, and primitive boundary.

## Documentation

### Research Objective & Plan
- [Tool Reuse & Whole-Package Compression Objective](docs/REUSE_COMPRESSION_OBJECTIVE.md) — Current research focus, full-cost accounting, proof-selection rules, and stopping criteria.
- [Research Plan & Progress](docs/RESEARCH_PLAN.md) — Milestones (M0–M4), observed experimental evidence, and open research questions.

### User & Technical Guides
- [Metrics & Operational Definitions](docs/METRICS.md) — `T0`, `I0`, PageRank `I1`, `E_finite`, and known interpretive limits.
- [Data Formats](docs/DATA.md) — JSON schemas for reference corpora, precision handling, and finite proof hypergraphs.
- [Lean Adapter](lean/README.md) — Exporting declarations and dependencies from Lean 4.24.0 projects.
- [Theory-Package Evaluation](docs/THEORY_PACKAGES.md) — Isolated Lean verification and full-package cost ledgers.
- [Proof Precompression & Portfolio Accounting](docs/PROOF_PRECOMPRESSION.md) — Complete-route measurement (`maam precompression --study ...`), charging shared modules once across optional adoption, mandatory delivery, and installed reuse.
- [Grouped Proof Search Controller](docs/GROUPED_PROOF_SEARCH.md) — Shared preparation, freezing, control/treatment phases, and local shared helpers (`maam group-*`).
- [Cross-Module Proof Refactoring](docs/PROOF_REFACTORING.md) — Extracting shared lemmas across archived group-theory proofs, verifying rewritten goals, and accounting over all 15 goal subsets (`maam refactor-proofs`).
- [Conjecture Conditional Compression](experiments/conjecture_compression_v2/README.md) — Checking original and conjecture-dependent proofs (`maam measure-conjecture-compression`, `maam rank-conjectures`); see also the [single-goal experiment](experiments/conjecture_compression/README.md) and [open-goal coverage experiment](experiments/conjecture_ranking/README.md).
- [Fixed-Snapshot Reproduction](docs/REPRODUCTION.md) — Mathlib snapshot (`d167cc6dc962ab340507362ea2f4bcfcff44f01b`) and monoid coverage experiments ([summary](reports/mathlib/summary.json), [status](results/reproduction_status.json)).

## Current Status

- **Implemented**: Static metric CLI, Lean 4.24.0 export and isolated verification, hom/kernel reference migration ([experiments/hom_kernel/README.md](experiments/hom_kernel/README.md)), metered DeepSeek transfer/guidance/construction controllers, v2 explicit theorem contract, package ablations, proof precompression (`maam precompression`), grouped proof search (`maam group-*`), cross-module proof refactoring (`maam refactor-proofs`), conjecture compression ranking (`maam rank-conjectures` / `measure-conjecture-compression`), and offline whole-package compression (`zlib`/`bzip2`).
- **Observed**: In the M1 hom/kernel reference migration, the local proof body shrinks from `77` to `29` source tokens, while total nonshared source grows from `89` to `353` tokens. In the four-goal cross-module refactoring experiment, old-tool source tokens drop `1985 → 1855 → 1772 → 1651`, while the full-package archived portfolio is `1574` tokens / `1685` compressed bytes vs. `1651` compressed bytes for continued old-tool proofs (diverging between token count and joint compression).
- **Open**: Baseline optimization sufficiency, causal concept attribution, broad held-out transfer, automatic multi-round candidate search, and learning-loop acceptance remain uncompleted.

## References

Metric implementations draw on [*Compression is all you need: Modeling Mathematics*](https://arxiv.org/abs/2603.20396v1) (ABFM) and [*Artificial Intelligence and the Structure of Mathematics*](https://arxiv.org/abs/2604.06107v1) (BDF).
