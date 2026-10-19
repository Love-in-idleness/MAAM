# Metered transfer v1: frozen task assets

This is an author-constructed eight-goal calibration cohort for the existing
`hom-kernel-group-v2` package, with four public development goals and four
reserved goals. It does not establish representative mathematical performance,
pretraining novelty, externally blind testing, or a fair model comparison.

`Base.lean`, `Candidate.lean`, `Extension.lean`, `package.json`, and
`lean-toolchain` are byte-identical copies of the frozen evolution v2 assets.
The source commit is `22b8e9b0258907e81692d9791822c7cbebefbcbe`; the candidate
therefore predates this cohort. No lemma was added to the foundation or package
for these goals. The unchanged migration loader reads `suite.json` and checks
all Lean source hashes.

## Families and exposure

| Split | Goals | Declared family | Required construction or reasoning |
| --- | --- | --- | --- |
| Development | d01, d02 | inverse_equation_solving | Solve left and right multiplication equations in homomorphic images. |
| Development | d03, d04 | image_torsion | Relate square-neutral and inverse-fixed images, including transported order dividing two. |
| Reserved | r01, r02 | split_section_decomposition | Factor an element into a kernel element times a chosen section, and prove uniqueness of both factors. |
| Reserved | r03, r04 | commutator_obstruction | Characterize commuting images by a neutral commutator, then relate universal vanishing to a surjective codomain being abelian. |

The development algebra deliberately exercises familiar cancellation and image
laws, with author reference proofs for both conditions. Those proofs are public
harness inputs and never model output. Reference generation usage is unknown
rather than zero.

The reserved patterns go beyond the earlier suites' postcomposition, pullback,
equalizer, finite/recursive product, balanced closure, fibre recovery, hom law,
carrier, range lifting, quotient-relation, indexed construction, conjugation,
subobject group, restriction, intersection, and group-word goals. Specifically,
the old section-based range-lifting goal only supplied a preimage of a product;
r01/r02 instead demand a kernel/section factorization and its uniqueness. The
old conjugation goals transport an assumed image equality; r03/r04 instead
characterize the obstruction to commuting images and a global abelian target.
This is an author judgment about distinct mathematical reasoning patterns, not
a measured independence or novelty guarantee. Goals within each pair are
intentionally correlated, and all goals remain elementary group theory.

Reserved statements are visible to their authors and protocol reviewers.
Preparation compiles their `Prop` declarations only; it neither constructs nor
submits a proof of a reserved goal. `reference_proofs.json` includes exactly the
four development IDs. Running these reserved tasks later must follow a separate
frozen admission and spending protocol. This suite alone grants no live-call
permission.

## Offline validation

Run from the repository root:

```bash
.venv/bin/python scripts/check_transfer_tasks.py --output data/transfer-task-smoke-NEW
```

The default executable is `scripts/lean_sandbox.py`. The check compiles all
frozen module declarations, then submits only the eight development reference
attempts through the unchanged migration verifier, covering four goals in both
conditions. It retains the actual Lean audit artifacts under the requested
new directory. No model provider is contacted. A successful check means the
declarations elaborate and the public development references preserve their
original goals; it says nothing about reserved solvability or model success.
