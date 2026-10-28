# 方法复用研究的下一道审查 / Next review of method reuse

| 中文 | English |
| --- | --- |
| **2026-10-28 · 策略审查材料，非新试验协议。** 这份材料供切到 Astra 后审查；它整理已知事实、替代解释与必须作出的研究选择，不授权新调用或扩充任务。应先读[声明契约验收](THEOREM_CONTRACT.md)，再讨论如何测量方法复用。 | **2026-10-28 · Strategy-review material, not a new trial protocol.** This packet is for review after switching to Astra. It records facts, alternatives, and research decisions without authorizing calls or additional tasks. Read [declaration-contract acceptance](THEOREM_CONTRACT.md) before discussing method-reuse measurement. |

## 已知证据 / Established evidence

| 中文 | English |
| --- | --- |
| [首次指南试验](METHOD_USE.md)：相同数学库下，两组预算内均 12/12，首轮均 11/12；两次首次拒绝均是 `def/theorem` 声明种类问题。记录资源与压缩取舍，未建立一般指南收益。 | [First guidance trial](METHOD_USE.md): with shared mathematics, both arms verify 12/12 within budget and 11/12 initially. Both initial rejections concern `def/theorem` declarations. Resource/compression tradeoffs do not establish general guidance gains. |
| [构造试验](CONSTRUCTION_USE.md)：39 次真实调用、24 个会话，16 份正向存在性证书和 8 份前提边界证明预算内通过。15 次首次拒绝中 14 次是声明约定，另一次是未知 Lean 名称。原计分保留，不能据此判断指南影响数学推理。 | [Construction trial](CONSTRUCTION_USE.md): 39 live calls verify 24 sessions within budget, including sixteen positive existential certificates and eight premise-boundary proofs. Fourteen of fifteen initial rejections concern declarations; one uses an unknown Lean name. Preserve original scores without attributing them to mathematical guide effects. |
| 正向目标已指定同态类型及逐点行为，所以核验的是受约束构造完成，不是发现未知映射。模型打包同态、内联证明封闭性，16 份成功正向源码均未命名调用一般运输引理。不能把内联证明视为失败，也不能据此声称完全没有使用概念方法。 | Positive goals specify homomorphism types and pointwise behavior, so verification establishes constrained construction completion rather than map discovery. Models bundle homomorphisms and prove closure inline; none of sixteen successful positive sources names the transport lemma. Inline proofs are valid, and their presence does not establish absence of conceptual method use. |
| 同一作者后备证明为 556 源码 token；择优后 A 为 519、B 为 506。指南计一次后，共同数学加所选材料 zlib 为 1883/2812 字节。它们是明确范围的存储计量，不能代替未观察到的后续价值。 | Shared author fallbacks cost 556 source tokens; selected A/B proofs cost 519/506. Charging the guide once, joint mathematics and selected material compress to 1883/2812 zlib bytes. These scoped storage measurements do not establish unobserved later value. |
| [新 v2](THEOREM_CONTRACT.md)已完成 12/12 本地作者控制验收（七个正例、五个预期拒绝），449 项测试通过；它只修正输出声明约定。旧付费调用器保持冻结，v2 尚无独立模型遵守率、预留任务、跨领域迁移或训练验收结果。 | [v2](THEOREM_CONTRACT.md) completes 12/12 local author controls (seven positives and five expected rejections), with 449 tests passing; it only clarifies the declaration convention. Frozen paid controllers are unchanged. v2 has no independent model-compliance rate, reserved-task, cross-domain, or training-acceptance result. |

## 需要决策的问题 / Decisions needed

| 中文 | English |
| --- | --- |
| **首先选定唯一主问题。** 下一步是在测说明组织是否改善调用，还是结构化构造能否降低后续组合成本，还是模型能否从任务中选择方法？它们需要不同对照，不能把所有目标装进一次小试验。 | **Choose one primary question.** Should the next step measure instructional organization, downstream composition using structured constructions, or selection of a method from a task? These require different controls and should not be combined into one small trial. |
| **给方法使用一个可计算且不强迫答案的判据。** 命名引理依赖是可核验的行为记录；概念上相同的内联证明也可能合理。判据需要容纳这种等价实现，或明确放弃内部方法归因，转而只测后续表现与整包成本。 | **Choose a computable criterion without forcing an answer.** Named dependencies are auditable behavior; conceptually similar inline proofs can also be reasonable. Either accommodate equivalent implementations or explicitly forgo internal-method attribution and measure subsequent performance and package cost. |
| **审查任务是否已经给出了关键选择。** 目标中的映射类型、逐点行为、构造输出要求可能提示方法；删去这些条件又可能允许平凡见证或偷换原任务。需要明确保留的数学问题，以及哪些选择确实交给模型。 | **Audit how much strategy the task supplies.** Map types, pointwise behavior, and construction requirements can cue a method; removing them may admit trivial witnesses or change the problem. Specify the mathematical problem and choices genuinely left to the model. |
| **充分利用旧工具后再比较。** 同一背景、已有引理、搜索与验证反馈保持一致，记录搜索成本；不把格式修复、额外尝试、命名或普通整理误归给新概念。全局最短不作不可实现的前置条件。 | **Use existing tools adequately before comparing.** Match background, lemmas, search, and verification feedback while recording search cost. Do not attribute format repair, extra attempts, naming, or ordinary cleanup to new concepts. Global shortestness is not an implementable prerequisite. |
| **提前确定停止和无结论规则。** 满分、混杂、成本取舍、未见压缩收益都允许停止。不能不断加题直到指南获胜，也不把旧开发题重新称为预留集。 | **Fix stop and inconclusive rules.** Ceiling scores, confounds, cost tradeoffs, and absent compression gains can end a trial. Do not keep adding tasks until guidance wins or relabel old development tasks as reserved. |

## Astra 应交付什么 / Requested Astra deliverable

| 中文 | English |
| --- | --- |
| 提交一份可审阅、可工程化的短方案：一个主假设；最小对照；任务语义与防平凡化约束；可计算指标；最强替代解释；小范围验收与停止规则；代码需要改变的最小范围。允许结论是暂不做新调用。 | Produce a short, reviewable, implementable design: one primary hypothesis, minimal controls, task semantics and anti-triviality constraints, computable measurements, strongest alternatives, small acceptance and stop rules, and the minimum code scope. A recommendation to make no new calls is allowed. |
| 不要求统一理解难度公式、新的大理论、全库实验、通用方法语言或立即自动抽取。先审查再冻结新协议；没有方案前不继续加样本。建议模型是下一轮任务选择，不自动切换当前模型。 | Do not require a unified comprehension formula, major new theory, library-wide trial, general method language, or immediate automatic extraction. Review before freezing another protocol; do not add samples without a design. The model recommendation is a next-task choice, not an automatic switch. |
