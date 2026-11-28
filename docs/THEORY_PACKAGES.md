# Theory-Package Evaluation (M1 Reference Interface)

[简体中文](THEORY_PACKAGES.zh-CN.md)

This interface implements the M1 reference migration: checking two supplied proofs in an isolated base library before and after introducing a candidate theory package, and producing an auditable cost ledger.

## Usage

Requires Python 3.11+ and Lean 4.24.0. Reference sources and manifests live in [experiments/hom_kernel/](../experiments/hom_kernel/).

```bash
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json
```

Write a new report and run live Lean rejection checks (output paths must not already exist):

```bash
mkdir -p data/theory-package
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json \
  --output data/theory-package/theory-package-reference.json
python scripts/check_theory_package.py \
  --report data/theory-package/theory-package-reference.json \
  --negative-output data/theory-package/theory-package-negative.json
```

**Exit codes**: `0` completed comparison; `1` input/runtime config error; `2` verification budget exhausted; `3` proof or dependency audit rejected.

## Input Manifests

- `experiment.json` pins base modules, baseline/treatment conditions, original goals, source SHA-256 digests, Lean version, and verification resource limits.
- `package.json` describes the core idea and the package's definitions, theorems, and objects.
- v1 accepts only `reference_migration` and `development` tasks; supplied proofs are reference witnesses, not held-out discovery evidence.
- All source files must stay inside the experiment directory, match frozen SHA-256 digests, remain mutually disjoint across base/candidate/proofs, and avoid shadowing Lean core modules. Create a new experiment version whenever sources or candidates change.

## Verification Pipeline

1. Each condition's sources are copied into a fresh temporary directory with `LEAN_PATH` replaced and compiled in a fixed order so pre-existing `.olean` files cannot leak in.
2. The baseline gets only the base library and original proof; treatment gets the same base, candidate package, and migrated proof.
3. The auditor checks transitive imports, every experiment-module declaration and dependency, and verifies that targets prove the original propositions.
4. Only the standard Lean axioms `propext`, `Quot.sound`, and `Classical.choice` are permitted (actual axioms used are listed). Other axioms, `sorryAx`, and `unsafe` dependencies are rejected, including inside unused candidate declarations.
5. Note: module/dependency checks enforce experimental validity and do not act as an OS security sandbox.

## Cost Conventions

- **Source tokens**: original-position atom and identifier leaves from Lean's command parser, deduplicated with comments excluded. For `:=` target declarations, syntax positions split header, separator, and proof body.
- **Internal proof size**: expression-constructor count (including binder types, excluding metadata wrappers) of the proof body, without expanding referenced lemmas.
- **Whole-package ledger**: local proof shortening is descriptive only. Net source cost compares all nonshared modules, charging candidate definitions, lemma proofs, auxiliaries, and migration code once. The identical base cancels out. Source tokens and internal proof sizes are reported separately.
- **Timing**: records compilation/verification overhead only, not proof-search efficiency.

## Interpreting Reports

- `verified_reference_comparison` means both conditions compiled, passed auditing, and completed the comparison.
- A net source increase after charging the package is a valid result.
- For M2's 20 calibration tasks, skill, and task-local submission protocol, see [MIGRATION_PROTOCOL.md](MIGRATION_PROTOCOL.md). See also [RESEARCH_PLAN.md](RESEARCH_PLAN.md) and [.github/workflows/theory-package.yml](../.github/workflows/theory-package.yml).
