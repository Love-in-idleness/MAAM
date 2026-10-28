# 定理声明契约验收 / Theorem-declaration contract acceptance

| 中文 | English |
| --- | --- |
| **2026-10-28 · 离线工程。** 上一轮 [构造试验](CONSTRUCTION_USE.md)有 14 次 `def/theorem` 声明拒绝，共享提示却未明确要求 theorem。本版本把该约定写进求解消息，接到完整 JSON 源码提交和已有 Lean 沙箱。修说明，不放宽检查器；旧源码、提示、计分与收据保持冻结。 | **2026-10-28 · Offline engineering.** The [construction trial](CONSTRUCTION_USE.md) has fourteen `def/theorem` rejections, while shared instructions did not explicitly require a theorem. This version states the convention in solver messages and connects complete JSON-source submission to the existing Lean sandbox. Clarify instructions without relaxing the checker; old code, prompts, scores, and receipts stay frozen. |
| 精确契约是：只返回一个 JSON 对象，唯一字段 `proof` 为完整 `Proof.lean`；按所列模块导入，用 `theorem` 声明 `Submission.solve : 所给目标`。namespace 内的 `theorem solve` 与全限定名形式均可。禁止改变目标、加公理或额外导入。 | The exact contract is one JSON object with only `proof`, containing complete `Proof.lean`. Import the listed modules and declare `Submission.solve : supplied goal` using `theorem`. Namespace-local `theorem solve` and fully qualified forms are allowed. Preserve the goal and avoid new axioms or extra imports. |
| 本地对照明确区分源码可编译、声明格式合约、目标一致性和依赖/公理安全。`def` 被声明种类审计拒绝不等于它表达了错误数学。裸证明项也不能作为完整源码提交，控制器不自动替模型包装或修改声明。 | Local controls distinguish compilation, declaration conformance, goal preservation, and dependency/axiom policy. Rejecting a `def` for its declaration kind does not establish mathematical invalidity. A bare proof term is not complete source; the controller does not wrap submissions or repair declarations for a model. |
| [v2 协议](../experiments/theorem_contract_v2/README.md)复用冻结的六题、参考和指南，不复制数学内容。12 个固定作者控制包含七个 theorem 正例和五个反例，每槽只运行一次，不是十二次模型搜索。 | The [v2 protocol](../experiments/theorem_contract_v2/README.md) reuses the frozen six tasks, references, and guide without copying mathematics. Twelve fixed author controls comprise seven theorem positives and five negatives, one run per slot, rather than twelve model searches. |
| 两组消息的数学部分相同，仅 B 增加指南；两组都明确 theorem。人工参考、任务角色、旧目标证明和宿主私有路径不进入求解消息。实际核验使用保存的完整响应源码，先落盘预约，再进沙箱。报告核对消息、源码、结果和日志的哈希；中断禁止重发。 | Both message conditions share mathematics and explicitly require a theorem; only B adds guidance. References, task roles, existing target proofs, and private host paths stay outside solver messages. Verify the preserved complete response source after persisting a reservation. Reports check message, source, result, and log hashes; interruptions cannot be resent. |
| **本入口不含付费流程。**没有 API、密钥参数或调用额度；不会自动升级冻结的旧付费调用器。零 API 验收能证明契约与检查器一致，不能证明模型遵守率提高、指南有效或方法已被独立复用。 | **This entry point has no paid workflow.** It provides no API, credential argument, or call allowance and does not upgrade frozen paid controllers. Zero-API acceptance can establish contract/checker agreement, not improved model compliance, guidance effectiveness, or independent method reuse. |

```bash
# Commit protocol and implementation before formal acceptance.
python3 scripts/check_theorem_contract.py prepare data/theorem-contract-v2
python3 scripts/check_theorem_contract.py input data/theorem-contract-v2 --task c03 --guide
python3 scripts/check_theorem_contract.py run data/theorem-contract-v2
python3 scripts/check_theorem_contract.py report data/theorem-contract-v2
```

| 中文 | English |
| --- | --- |
| 验收后不重复跑同类付费题来追求分差。下一节点是审查如何在允许内联证明、已有工具充分使用且不泄漏目标解法的条件下，测量方法组织与后续复用。这涉及研究识别策略，交由 Astra 审查后再决定新任务和预算。 | After acceptance, do not repeat similar paid tasks to seek a score difference. Next review how to measure method organization and later reuse while allowing inline proofs, adequately using existing tools, and avoiding answer leakage. This concerns research identification strategy; request Astra review before choosing new tasks and budgets. |

| 中文 | English |
| --- | --- |
| 冻结前验收：新增 18 项测试，全量 **449 项测试通过**；已有方法指南、构造试验和离线材料三份报告重算一致。负例还测试了错误阶段/错误诊断/环境故障均不能冒充预期拒绝。 | Pre-freeze acceptance: eighteen new tests and all **449 tests pass**. Existing guidance, construction, and offline-material reports replay unchanged. Additional checks reject wrong-stage, wrong-diagnostic, and environment failures as substitutes for expected negative outcomes. |
| 后续策略审查的事实、替代解释和交付要求已整理为 [Astra 审查包](METHOD_REUSE_REVIEW.md)。本轮不替它选定新任务，也不发起新付费协议。 | Facts, alternatives, and requested strategy deliverables are collected in the [Astra review packet](METHOD_REUSE_REVIEW.md). This round does not select new tasks or initiate another paid protocol. |
