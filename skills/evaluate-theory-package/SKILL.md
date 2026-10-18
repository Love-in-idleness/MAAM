---
name: evaluate-theory-package
description: Evaluate new mathematical concepts, propositions or connected theory packages by migrating existing goals into a frozen Lean candidate library. Use for MAAM theory-package experiments, task-local proof requests, representation bridges, bounded proof attempts and contextual comparisons intended to inform later learning.
---

# Evaluate a theory package

Use verified changes in mathematical work as evidence. Keep proof generation, formal correctness, cost accounting and mathematical-value interpretation separate.

## Choose your role

**Task-local worker:** If given a request JSON, use only this skill and that request. Read its source strings and goal. Do not inspect the repository, other task statements, opposite-condition attempts, public reference proofs or archived reports. Follow the worker steps below. The controller submits your response.

**Experiment controller:** If asked to run an experiment in an MAAM checkout, use the controller steps. Keep each worker context restricted to one exported request and this skill.

## Worker steps

1. Read the condition, original goal, supplied modules and budgets. Treat the goal and foundation as fixed. In baseline, use only the supplied foundation; in treatment, candidate definitions and proved lemmas are available. Never import a larger library or add axioms.
2. Identify the proof obligation in the original vocabulary. For treatment, inspect candidate definitions and find a representation bridge: bundle raw data, prove its structure fields, transport hypotheses, use a candidate property, and return to the original goal. A short definitional bridge can suffice. If the package does not help, prove directly and say so.
3. Write a Lean term after the controller-owned declaration's := delimiter, usually a by block. Put any helper lemma inside this term. Do not edit frozen files, replace the theorem statement, alter checker options or reset the attempt budget.
4. Explain the bridge in a short text file. State which candidate properties are used and where raw hypotheses discharge their preconditions. Do not invent a successful compilation.
5. Package the response with the bundled script:

~~~bash
python /path/to/evaluate-theory-package/scripts/pack_submission.py \
  --request request.json --proof proof.lean --bridge bridge.txt \
  --output submission.json
~~~

The proof file contains only the term, not imports or a theorem wrapper. The script checks request/source fingerprints and response size; it does not run Lean.

6. Return submission.json to the controller. If given verification feedback, inspect the exact failure and revise within the remaining attempt count. Treat timeouts, interruptions and unsolved tasks as unknown under a budget. Stop when the controller reports exhaustion. Never hide or erase failed attempts.
7. Report separately: supplied proof, submitted attempt, verified witness, or no verified witness observed. A JSON response or successful packaging is not proof verification.

## Controller steps

1. Locate the requested MAAM checkout. Read its docs/MIGRATION_PROTOCOL.md and suite manifest. Use a candidate frozen before evaluation. If changing it after development feedback, create a new package/suite version and new sessions; never silently refresh hashes.
2. Start baseline and treatment with the same explicit solver identity, mode and suite. For example:

~~~bash
python -m maam migration-start --suite experiments/hom_kernel_migration/suite.json \
  --session data/run-baseline --condition baseline --solver-id solver-version
python -m maam migration-start --suite experiments/hom_kernel_migration/suite.json \
  --session data/run-treatment --condition treatment --solver-id solver-version
python -m maam migration-request --session data/run-treatment \
  --task d01 --output request.json
~~~

3. Give a fresh worker only the request and skill. Do not supply intended proofs or the other condition's feedback. Record model/version, prompt, sampling settings, task order and actual generation usage externally. The runner enforces submission and Lean verification budgets; it cannot independently meter an external model's generation budget.
4. Submit the worker artifact:

~~~bash
python -m maam migration-submit --session data/run-treatment \
  --submission submission.json --output attempt-report.json
~~~

Read the returned status and retained command logs. Use a new report filename for each attempt. Lean and the auditor must accept the original proposition and dependency policy before calling an attempt verified. The CLI writes a failed report before returning a nonzero exit code.

5. Summarize and compare:

~~~bash
python -m maam migration-report --session data/run-treatment --output session-report.json
python -m maam migration-compare --baseline data/run-baseline \
  --treatment data/run-treatment --output comparison.json
~~~

Compare coverage separately from cost on common solved tasks. Charge all candidate source once. Do not interpret a local proof-body saving, an unsolved task, or a supplied calibration proof as an independently established preference or a general interest score.

6. Keep the candidate fixed when inspecting reserved results. Public reference proofs make the bundled suite calibration material. Independent held-out evidence requires a separate controlled run with recorded information boundaries; this release always marks held_out_evaluation and training_eligible false.

Read [protocol.md](references/protocol.md) for statuses, interruption handling and scope.
