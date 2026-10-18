# Protocol details

- Keep the controller's session directory private from task-local workers. The request exports only the current task and condition. This is an information-boundary procedure, not filesystem access control.
- Use Lean 4.24.0 for the bundled suite. Install and warm the pinned toolchain before timed verification; otherwise a download can consume verification time.
- Submission fields: task_id, request_sha256, proof, bridge; optional generation is caller-reported metadata. Extra fields cannot alter targets or budgets.
- verified means the Lean witness and module/axiom/goal audit passed. rejected means compilation or the formal policy failed. inconclusive means a resource limit or environment/controller problem prevented verification.
- A pending attempt without a result is incomplete and still consumes its slot. If the controller died while holding controller.lock, inspect the process and pending artifacts before removing that stale lock. Preserve the attempt directory.
- Attempt records, source bytes and full command stdout/stderr have SHA-256 checks. These detect accidental edits; they are unsigned local records, not tamper-proof attestations.
- Use fresh directories for each condition and attempt. Precompiled local objects and the opposite condition's library are not copied into verification.
- Source costs count parsed Lean tokens in every nonshared proof module plus the whole candidate once. The common foundation and unchanged task statements cancel. Elaborated local expression sizes do not expand referenced lemmas.
- The runner selects the smallest observed full proof-module source among verified in-budget attempts; this is not a global minimum proof.
- Lean source can execute metaprograms. Run only trusted inputs here; hostile inputs require a separate OS/container sandbox without credentials.
- This skill performs evidence collection. Package ablations, independent held-out validation and a learning-algorithm-specific feedback policy are separate experimental stages.
