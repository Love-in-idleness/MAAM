# Research Plan and Progress

[简体中文](RESEARCH_PLAN.zh-CN.md) | [Current Objective](REUSE_COMPRESSION_OBJECTIVE.md)

## Current Phase (2026-10-29)

The active research entry point is [Tool Reuse and Whole-Package Compression](REUSE_COMPRESSION_OBJECTIVE.md), focusing on whether proof savings offset the complete cost of introducing reusable mathematical tools under fixed goals and strict verification. Earlier designs, trials, and historical experiment logs remain archived under `docs/` without creating new API call allowances.

## Research Objective

MAAM evaluates new propositions, definitions, and cohesive **candidate theory packages** (definitions, properties, lemmas, and transport bridges) in Lean to provide auditable feedback for mathematical exploration and future AI learning:

- **Evaluation unit**: A candidate theory package (`base`, `core`, `declarations`, `bridges`, `dependencies`, `conjectures`, `applicability`, `provenance`) evaluated jointly first, then inspected via ablations (e.g., naming only, definitions only, full package) rather than summing static node scores.
- **Core comparison**: With background library `K`, predetermined task set `T`, and proof-search budget `B` fixed, compare `Run(K, T, B)` vs. `Run(K + P, T, B)`, charging the complete cost of `P` once and keeping source size, internal proof size, search resources, verification time, and solved goals separate.
- **Comparison outputs**: Contextual dominance, trade-offs (incomparability), empirical equivalence, or insufficient evidence — no single scalar score or universal ranking is forced.
- **Role of static metrics**: Static metrics ([METRICS.md](METRICS.md)) remain descriptive and retrieval signals, not validated predictors of a new concept's future value.

## Milestones & Progress Summary

| Phase | Target Deliverable | Implemented Controls | Observed Evidence | Remaining Gaps |
| --- | --- | --- | --- | --- |
| **M0: Design** | Scope, package schema, evidence conventions | Complete (`RESEARCH_PLAN`, `REUSE_COMPRESSION_OBJECTIVE`, theoretical notes) | — | Cognitive/future-value models deferred as non-blocking research |
| **M1: Verified Comparison** | Isolated Lean runner, manifests, hom/kernel reference migration, audit checks | Complete ([THEORY_PACKAGES.md](THEORY_PACKAGES.md), [COMPRESSED_PACKAGES.md](COMPRESSED_PACKAGES.md)) | Local proof body `77 → 29` tokens; total nonshared source `89 → 353` tokens | Single reference task; does not establish general value |
| **M2: Systematic Migration** | ~20 goals, `evaluate-theory-package` skill, metered LLM interface, held-out split | Partially complete: independent contexts, DeepSeek stage-gated & budgeted runner, retained-proof selector, bounded old-tool sweeps, guidance/construction trials, v2 theorem contract | 40 verified independent witnesses; formal metered v1: 16 DeepSeek calls (US\$0.296767125 est.), 13/16 verified, 5 shared goals `2572 → 3679` tokens (incl. 1100-token package); guidance trial `24/24` (26 calls, US\$0.057759); construction trial `24/24` (39 calls, exposed `def/theorem` contract ambiguity); v2 contract `12/12` fixed controls & 449 passing tests | Baseline optimization sufficiency, strict causal attribution, broader task coverage, and held-out effectiveness remain unaccepted |
| **M3: Packages & Delayed Value** | Ablations, version archives, cost/use comparison, multi-round search | Partially complete: ablations, `v1 → v2` evolution, provenance adapter (`receipts → inventory → bounded sweeps → retained compression`) | 2 dev goals after DeepSeek old-tool search: `367 → 186` tokens; with package `121 + 1100 = 1221` tokens (compressed bytes also grew) | Automatic multi-round candidate search and distant transfer unimplemented |
| **M4: Learning Interface** | Replayable traces, preference/comparison datasets, training feedback adapter | Not started | — | Replayable training loop and reward-hacking checks unimplemented |

## Protocol Principles

1. **Freeze & isolate**: Fix base library, goals, equivalence criteria, cost conventions, prover config, and budgets. Check transitive imports and automation so candidate concepts cannot leak into the baseline.
2. **Dev/held-out split**: Group tasks by reasoning pattern so near-duplicates do not cross splits. Develop candidates only on development tasks; once held-out results inform revisions, fresh unused tasks are required.
3. **Local migration & retention**: Preserve verified originals. Adopt a migrated proof only when verified and strictly shorter in complete `Proof` source tokens; record longer reusable decompositions separately.
4. **Honest accounting**: Report gross savings and net savings after charging `P` once. Retain failed/interrupted runs and keep unknown generation costs unknown rather than zero.

## Archived Design & Experiment Index

Historical documents in `docs/` remain preserved as immutable records of earlier stages:

- **Baselines & selection**: [BASELINE_PREPARATION.md](BASELINE_PREPARATION.md), [BASELINE_SEARCH.md](BASELINE_SEARCH.md), [BASELINE_METHODS.md](BASELINE_METHODS.md), [BASELINE_STABILITY.md](BASELINE_STABILITY.md), [MODEL_BASELINE.md](MODEL_BASELINE.md), [RETAINED_COMPRESSION.md](RETAINED_COMPRESSION.md), [MODEL_PORTFOLIO.md](MODEL_PORTFOLIO.md)
- **Migration & metered trials**: [MIGRATION_PROTOCOL.md](MIGRATION_PROTOCOL.md), [INDEPENDENT_EXPERIMENT.md](INDEPENDENT_EXPERIMENT.md), [GENERATION.md](GENERATION.md), [METERED_TRANSFER.md](METERED_TRANSFER.md), [PACKAGE_ABLATIONS.md](PACKAGE_ABLATIONS.md), [VERSION_EVOLUTION.md](VERSION_EVOLUTION.md)
- **Method use & contracts**: [METHOD_RESEARCH_DESIGN.md](METHOD_RESEARCH_DESIGN.md), [METHOD_USE.md](METHOD_USE.md), [CLOSURE_TRANSPORT.md](CLOSURE_TRANSPORT.md), [CONSTRUCTION_USE.md](CONSTRUCTION_USE.md), [THEOREM_CONTRACT.md](THEOREM_CONTRACT.md), [METHOD_REUSE_REVIEW.md](METHOD_REUSE_REVIEW.md)
- **Theoretical notes**: [COMPRESSION_FRAMEWORK.md](COMPRESSION_FRAMEWORK.md), [COGNITIVE_COMPRESSION.md](COGNITIVE_COMPRESSION.md), [PROOF_METHODS.md](PROOF_METHODS.md), [EXECUTABLE_METHOD.md](EXECUTABLE_METHOD.md)
