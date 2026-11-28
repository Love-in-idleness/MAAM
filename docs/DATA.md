# Data Input Formats

[简体中文](DATA.zh-CN.md)

## Reference Corpus

Minimal valid corpus JSON (all referenced dependencies must be declared; multiplicities must be positive integers):

```json
{
  "schema_version": 1,
  "corpus_id": "your-fixed-corpus-v1",
  "length_basis": "references",
  "provenance": {"kind": "manual", "revision": "your-data-revision"},
  "nodes": [
    {"name": "Primitive", "kind": "primitive"},
    {
      "name": "YourTheorem",
      "kind": "theorem",
      "statement": "Your formal proposition",
      "signature": {"Primitive": 2},
      "body": {"Primitive": 3}
    }
  ]
}
```

- `signature` and `body` map declaration names to occurrence counts (multisets, not sets).
- `primitive` marks an explicit expansion boundary and must have no outgoing references. Undeclared dependencies raise an error rather than becoming primitives automatically.

| Field | Values | Meaning |
| --- | --- | --- |
| `kind` | `primitive`, `axiom`, `definition`, `theorem`, `conjecture` | Node role |
| `body` | Reference map or `null` | Required for `theorem`; must be `null` for `conjecture` and `axiom` |
| `signature_tokens` | Positive integer | Required when `length_basis = "source_tokens"` |
| `body_tokens` | Nonnegative integer | Required for nodes with bodies in `source_tokens` mode |
| `statement` | Optional string | Exact text lookup (not semantically parsed) |
| `domain` | Optional module tag | Descriptive metadata for direct users |
| `admitted` | Boolean | Admission taint flag, propagated through dependents |

### Soundness & Taint Caveats

- Unproved statements must use `kind: "conjecture"` and `body: null`.
- `body: {}` indicates a supplied proof with zero counted references (not a missing proof) and must be substantiated by the data provider.
- Importing JSON into Python does not confer Lean type-checking guarantees; record verification provenance separately.
- Nodes with `admitted: true` or named `sorryAx` / `Lean.sorryAx` taint all transitive dependents, excluding them from the scoring cohort. This does not defend against adversarial JSON falsification.

## Precision Handling

Primitive expansions use arbitrary-precision integers without materialising expanded strings. Reports include bit length, `log2`, and an exact decimal string up to 3,300 bits (`exact: null` above that). Ratios exceeding floating-point range set `value: null` while retaining `log2`, and normalisation operates directly in log space to avoid overflow.

## Finite Proof Hypergraph

Used for `E_finite` without conflating a reference graph with a proof-search space:

```json
{
  "schema_version": 1,
  "system_id": "your-finite-system",
  "statement_lengths": {"A": 2, "B": 3},
  "axioms": ["A"],
  "rules": [{"id": "derive-B", "conclusion": "B", "premises": ["A"]}]
}
```

Here `m(A) = 2`, `m(B) = 3 + 2 = 5`, and `E_finite(B) = 5/3`. Premise lists preserve duplicates; logical validity of rules is the caller's responsibility.

## Bundled Examples

- `examples/paper_simple_lemma.json`: manual transcription of the paper's displayed internal-expression counts (not regenerated locally with Lean).
- `examples/toy_corpus.json`: synthetic corpus exercising hierarchical compression, reuse, and proof padding (no human interest labels).
