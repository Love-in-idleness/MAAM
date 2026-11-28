# Lean 4.24.0 Adapter

[简体中文](README.zh-CN.md)

`maam/Export.lean` exports reference multiplicities from elaborated Lean signatures and proof bodies, recording every `const` and `Sort` occurrence along with explicit primitive boundaries.

This adapter passes the `Lean adapter` GitHub Actions workflow on **Lean 4.24.0** (compilation, demo export, metric checks, and `sorry`-taint exclusion; see [results/remote_validation.json](../results/remote_validation.json)). For the separate full Mathlib pipeline, source-token counting, and SCC condensation, see [docs/REPRODUCTION.md](../docs/REPRODUCTION.md).

## Standalone Smoke Check

After installing Lean `4.24.0`:

```bash
(cd lean && lean -o Demo.olean Demo.lean)
python -m maam export-lean --runner lean --project lean --module Demo \
  --target Demo.andRight --target Demo.modusPonens --target Demo.andSwap \
  --target Demo.admittedExample --output results/lean-demo.json
python -m maam rank --corpus results/lean-demo.json --format text
python -m maam score --corpus results/lean-demo.json --name Demo.admittedExample
```

## Exporting a Local Mathlib Module

Run from the MAAM root against an existing built Mathlib checkout (using its own Lean version and Lake environment):

```bash
python -m maam export-lean --project /absolute/path/to/mathlib4 \
  --module Mathlib.Analysis.Real.Hyperreal --target Hyperreal.infinitesimal_zero \
  --expand-prefix Mathlib.Analysis.Real.Hyperreal --output data/hyperreal-local.json
python -m maam score --corpus data/hyperreal-local.json --name Hyperreal.infinitesimal_zero
```

This creates a bounded local dependency closure whose scores differ from the full-corpus Mathlib index. The paper's pinned Mathlib snapshot is `d167cc6dc962ab340507362ea2f4bcfcff44f01b` (Lean `4.24.0`); changing the snapshot changes scores.

## Boundary & Length Conventions

- **Unsafe & cycles**: This small-corpus adapter marks `unsafe` declarations as admitted primitive boundaries, and the JSON calculator rejects remaining cycles. In contrast, `maam/PaperExport.lean` retains `unsafe` declarations and condenses SCCs for the full-library experiment — these policies define distinct corpora.
- **Reference counts vs. source tokens**: Tactics such as `simp` expand into larger elaborated terms, so internal reference counts are never presented as source token counts. This adapter outputs the reference-count basis; source-token metrics come only from the separate fixed-snapshot pipeline.
