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
- [Fixed-Snapshot Reproduction](docs/REPRODUCTION.md) — Mathlib snapshot (`d167cc6dc962ab340507362ea2f4bcfcff44f01b`) and monoid coverage experiments ([summary](reports/mathlib/summary.json), [status](results/reproduction_status.json)).

## Current Status

- **Implemented**: Static metric CLI, Lean 4.24.0 export and isolated verification, hom/kernel reference migration ([experiments/hom_kernel/README.md](experiments/hom_kernel/README.md)), metered DeepSeek transfer/guidance/construction controllers, v2 explicit theorem contract, package ablations, and offline whole-package compression (`zlib`/`bzip2`).
- **Observed**: In the M1 hom/kernel reference migration, the local proof body shrinks from `77` to `29` source tokens, while total nonshared source grows from `89` to `353` tokens. Across metered DeepSeek trials and retained-proof compression comparisons, whole-package cost has not yet been offset by proof savings.
- **Open**: Baseline optimization sufficiency, causal concept attribution, broad held-out transfer, automatic multi-round candidate search, and learning-loop acceptance remain uncompleted.

## References

Metric implementations draw on [*Compression is all you need: Modeling Mathematics*](https://arxiv.org/abs/2603.20396v1) (ABFM) and [*Artificial Intelligence and the Structure of Mathematics*](https://arxiv.org/abs/2604.06107v1) (BDF).
