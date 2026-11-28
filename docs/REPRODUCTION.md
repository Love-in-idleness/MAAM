# Fixed-Snapshot Reproduction

[简体中文](REPRODUCTION.zh-CN.md)

The `Fixed Mathlib reproduction` workflow pins Mathlib commit `d167cc6dc962ab340507362ea2f4bcfcff44f01b` and Lean `4.24.0` from [ABFM §3](https://arxiv.org/html/2603.20396v1#S3), ensuring newer Mathlib revisions are never conflated with the original paper dataset.

## Running the Mathlib Pipeline

```bash
python -m pip install '.[reproduction]'
bash scripts/build_paper_exporter.sh
cd /absolute/path/to/the/fixed/mathlib4
lake exe cache get
LEAN_SYSROOT="$(lean --print-prefix)" lake env /absolute/path/to/MAAM/build/maam-paper-export \
  Mathlib Mathlib . /absolute/path/to/MAAM/data/mathlib.jsonl \
  d167cc6dc962ab340507362ea2f4bcfcff44f01b
cd /absolute/path/to/MAAM
python scripts/analyze_mathlib.py --input data/mathlib.jsonl \
  --output reports/mathlib --index data/mathlib-metrics.sqlite
```

- The native exporter is built with the pinned Lean Lake configuration and verified in CI against interpreted execution on small cases for identical dependency multiplicities, declaration ranges, and token counts.
- Summary statistics, plots, bucket medians, cycle lists, and top-100 reference-basis theorem scores are written to `reports/mathlib/`. Large artifacts (`mathlib.jsonl` and `mathlib-metrics.sqlite.gz`) are stored as 30-day workflow artifacts.

### Querying a Built SQLite Index (No Lean Required)

```bash
gzip -dk mathlib-metrics.sqlite.gz
python -m maam score-index --index mathlib-metrics.sqlite \
  --name AlgebraicGeometry.Scheme.exists_hom_hom_comp_eq_comp_of_locallyOfFiniteType
python scripts/reproduce.py --index data/mathlib-metrics.sqlite
```

`reproduce.py` checks index fingerprint compatibility and writes measured paper examples to [results/mathlib_examples.json](../results/mathlib_examples.json).

## Method & Conventions

- **Graph scope**: Module-scope vertices condense from `463,719 → 463,661`; retaining `9,626` explicit primitive boundary vertices gives `473,345 → 473,287`. Every `const` and `Sort` occurrence is counted with multiplicity; Mathlib `unsafe` definitions are retained, while external declarations and `Sort` form the primitive boundary.
- **SCC condensation**: Internal edges are removed, external multiplicities are summed, and condensed sinks receive expansion length `1` (a graph-statistical convention, not a finite unrolling of recursive code). Multi-declaration SCCs return `null` compression ratios rather than mixing per-declaration and per-component metrics.
- **Source tokens**: Counted via Lean's command parser over distinct original atom/identifier leaf starts (comments excluded, strings retained), replaying `namespace`/`section`/`open`/local syntax/`set_option` per file without re-elaborating proofs. Primary counts include attributes/modifiers (`declModifiers`); a systematic modifier-excluded sensitivity analysis is also exported. Missing ranges or parse failures remain missing (see [source_failures.json](../reports/mathlib/source_failures.json)) and are never filled with internal reference counts.
- **Ranking basis**: Full-corpus theorem rankings use the reference-count convention, since whole-declaration source tokens are not split into statement and proof lengths.

## Observed Results vs. Paper Targets

The [completed full workflow run](https://github.com/Love-in-idleness/MAAM/actions/runs/39060623030) verified archive download, fingerprints, and landmark queries (dependency fingerprints unchanged across source-parser repairs; see [results/mathlib_baseline.json](../results/mathlib_baseline.json)):

| Landmark | Full tokens | Without modifiers | Paper | Measured expansion |
| --- | ---: | ---: | ---: | ---: |
| `VectorBundleCore.isOpenMap_proj` | 7 | 7 | 7 | ≈1.066×10^48 |
| `ContDiffBump.integrable` | 10 | 9 | 9 | ≈2.437×10^54 |
| `Hyperreal.infinitesimal_zero` | 8 | 8 | 8 | ≈3.635×10^31 |

**Known discrepancies** (retained transparently without dropping nodes or tuning windows):
- **Token slope**: ≈`0.228` (unweighted fit over fixed bucket windows depth `[10, 250]`, tokens `[10, 200]`, ≥20 items/bucket) vs. paper's ≈`0.4`.
- **Maximum expansion**: `10^110.6394` vs. paper's ≈`10^104` (maximised by the same theorem; root cause remains open).

## Monoid Coverage Experiments

Runs with the Python standard library only (no Lean or scientific dependencies):

```bash
python scripts/reproduce_monoids.py
```

Produces exact finite coverage curves for five models in [reports/monoids/summary.json](../reports/monoids/summary.json) and [reports/monoids/finite_coverage.csv](../reports/monoids/finite_coverage.csv):
- `A1` dynamic programming up to `65536` with macro sets: powers of `2`, `2^(2^j)`, `{2, 5, 13}`, and squares (reporting lower bounds with `right_censored=true` when no counterexample appears before the cutoff).
- `A_n` coordinate-wise powers of `b`: exact formula `n(b^q - 1) + r·b^q - 1` (for `s + 1 = q·n(b - 1) + r`), cross-checked against 2D/3D exhaustive enumeration.
- `F2` ordered binary strings up to length `12` with unary power macros (alternating strings retain full length).
