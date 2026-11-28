# Tool Reuse and Whole-Package Compression Objective

[简体中文](REUSE_COMPRESSION_OBJECTIVE.zh-CN.md) | [Research Plan](RESEARCH_PLAN.md)

**Status (2026-10-29):** Current research entry point. This phase establishes the primary question, full-cost accounting boundary, proof-selection policy, and stopping criteria as documentation, without adding new tasks, measurement entry points, model calls, or experimental budgets.

## Primary Question

Under the same background library, original-goal coverage, and correctness requirements, **can space saved in subsequent proofs offset the full cost of organizing existing arguments into reusable tools?**

- **Success criterion**: A trustworthy, computable comparison — a candidate win is **not** required. Smaller, equal, larger, and insufficient-evidence outcomes are all valid conclusions.
- **Boundary**: AI usability and comprehension effects are reported separately and remain unknown unless backed by dedicated evidence.
- **Lineage**: Follows the strategy review ([METHOD_REUSE_REVIEW.md](METHOD_REUSE_REVIEW.md)) and preserves the semantic, correctness, proof-retention, and full-cost rules from [METHOD_RESEARCH_DESIGN.md](METHOD_RESEARCH_DESIGN.md). Historical trial plans do not grant new API call budgets.

## Comparison Objects and Full-Cost Accounting

Compare two portfolios with identical goal coverage:

```text
D_A = K ∪ H_A ∪ Π_A
D_B = K ∪ P ∪ H_B ∪ Π_B
ΔC  = C(encode(D_A)) − C(encode(D_B))
```

| Symbol | Meaning |
| --- | --- |
| `K` | Shared background: listed foundation sources and original goal declarations (same Lean version, allowed axioms, and targets). External dependencies such as `Init` and the toolchain are pinned and listed, not claimed to be inside local source size. |
| `P` | Complete candidate package: all candidate modules, definitions, proved lemmas, and inherited modules charged once, regardless of how many goals adopt them or whether some declarations go unused. |
| `H_A`, `H_B` | Additional required auxiliary materials per condition (realizations, instances, existence certificates, bridges, guidance, dedicated execution code). |
| `Π_A`, `Π_B` | Complete proof sources selected under the fixed proof-selection rule. |

### Accounting Rules

1. **Goal equivalence**: Objects, parameters, assumptions, and conclusions must match. Reformulations require structural correspondence and certified transport back to the original goal; an arbitrary `iff` is insufficient. Generalization scope is reported separately; savings may not be obtained by dropping goals, weakening targets, or adding axioms.
2. **Deduplication & amortization**: Overlapping inherited modules are counted once by matching identity and exact source. Only goals actually covered in the comparison share the cost; hypothetical future uses cannot amortize `P`.
3. **Encoding & codecs**: `encode` follows [measure_compressed_reference.py](../scripts/measure_compressed_reference.py): canonical JSON mapping fixed document labels to exact UTF-8 source, deterministically ordered, preserving names, imports, comments, and whitespace.
   - Primary metric `C`: absolute `zlib` (level 9, `wbits=15`) byte count.
   - Sensitivity check: `bzip2` (level 9). Compression ratio is not the primary metric.
4. **Joint serialization**: Serialize and compress `D_A` and `D_B` jointly so baseline repetition receives the same compression opportunity. Report both the full portfolio (with `K` counted once per side) and nonshared material (excluding `K`). Because compression is non-additive, never cancel compressed `K` algebraically or sum individually compressed files.
5. **Independent contexts**: Identically named `Proof` modules or `Submission.solve` declarations from separate sessions receive predetermined distinct document labels to avoid overwrites while preserving source and imports. Such an archive reconstructs independent contexts and is not automatically one unified compilable Lean library.
6. **Preservation & separate reporting**: Originals, failures, longer candidates, budget reservations, and receipts are always retained. Runtime logs and research archives stay outside deployment-source ranking. Shared infrastructure, preparation costs, generation usage, and verification costs are reported separately; unknowns remain unknown.

## Baselines, Proof Selection, and Evidence Limits

- **Baseline preparation**: Follow [BASELINE_PREPARATION.md](BASELINE_PREPARATION.md). Existing lemmas, automation, helpers, and ordinary cleanup are executed, logged, and frozen within declared bounds. Causal attribution additionally requires matched continued-search opportunities after freezing; otherwise comparisons are descriptive only.
- **Strict-shorter retention**: Verified originals are always kept. Replace a goal's selected proof only when the goal matches, verification succeeds, and complete `Proof` source tokens strictly decrease; otherwise retain the original and its imports. Fix per-goal selection before compression rather than cherry-picking combinations by compressed size.
- **Modularity & dependencies**: Longer modular artifacts may remain as fully charged candidate tools without replacing originals. Named lemma dependencies establish explicit references, while inline proofs remain valid. Existence certificates support reasoning without automatically providing executable constructions.
- **Interpretive limits**: `ΔC > 0` means storage savings for this fixed portfolio and encoding only. It does **not** establish easier AI comprehension, better method selection, mathematical importance, or unseen-task transfer.

## Acceptance Scenarios and Stopping Rules

| Scenario | Required Decision |
| --- | --- |
| Shorter proof, larger package | Retain strict-shorter per-goal selection and report higher total package cost; never show proof savings alone. |
| Smaller complete portfolio | With complete coverage, provenance, verification, and accounting, report local net storage savings and absolute byte difference. |
| Missing bridge, module, or goal | Reject the comparison; missing material is not zero cost and cannot support a portfolio ranking. |
| Conflicting compressor rankings | Report both `zlib` and `bzip2`, mark as codec-sensitive, and do not claim robust superiority. |
| Changed payload or runtime | Strict replay reports drift; save a new version rather than rewriting history. Decompression must recover the exact payload. |
| Unknown generation/preparation cost | Byte differences may still be reported descriptively, without claiming total-resource gains, baseline sufficiency, or fair model comparisons. |

### Freezing & Stopping

- Before any formal comparison, freeze all goals, package versions, source manifests, labels, ordering, codecs/runtime, selection policy, and preparation/search budgets.
- The full goal set is primary; any cumulative prefix curve must follow the fixed order and report all prefixes without selecting favorable subsets.
- Stop once the fixed comparison completes. Zero/negative savings, codec sensitivity, incomplete coverage, or missing costs are valid closing outcomes. Never add tasks to chase a win, rename/switch codecs to improve original scores, or relabel development tasks as held-out.

## Next Decision Point

The archived four-goal, three-representation dataset ([results/evolution/summary.json](../results/evolution/summary.json)) can be mapped to this accounting without creating new tasks (strictly marked as post-hoc description, retaining its unverified-budget caveats). The next step is to map one concrete source manifest to this specification — verifying baseline, proof selection, dependency closure, and omissions — before deciding on a separate measurement implementation or a new experiment.
