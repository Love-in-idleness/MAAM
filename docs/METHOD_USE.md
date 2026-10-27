# 方法指南使用试验 / Method guidance use trial

| 中文 | English |
| --- | --- |
| 2026-10-27：用户已审阅[设计方案](METHOD_RESEARCH_DESIGN.md)并启动工程。六份人工参考已通过 Lean 4.24.0；新沙箱和调用控制器已实现。真实模型结果另列，离线测试不计为模型表现。 | 2026-10-27: the user reviewed the [design](METHOD_RESEARCH_DESIGN.md) and started implementation. Six author references pass Lean 4.24.0; the new sandbox and call controller are implemented. Live results are reported separately from offline tests. |
| [固定输入](../experiments/method_use_v1/README.md)包括六个开发任务、共同引理、255 词指南及人工参考。A/B 两组使用完全相同的数学源码，B 只多一份指南。两次重复各按 A→B、B→A 排序，共 24 个新模型上下文，最多 48 次调用。 | [Frozen inputs](../experiments/method_use_v1/README.md) include six development tasks, a common lemma, a 255-word guide, and author references. Both conditions share the mathematics; B additionally receives guidance. Counterbalanced repetitions yield 24 fresh model contexts and at most 48 calls. |
| 只向 DeepSeek 发送公共数学源码、目标、输出契约及可选指南。参考证明、旧证、角色标签、其他会话及私有文件路径不发送。输出必须是包含完整 Proof.lean 的单字段 JSON，由原有核验器独立检查。 | Send DeepSeek only public mathematical source, the goal, output contract, and optional guide. Exclude references, incumbents, role labels, other sessions, and private paths. Require one-field JSON containing complete Proof.lean source, checked by the existing verifier. |
| 调用前持久化预算预约；原始响应、用量、模型标识、时间、候选、Lean 日志和结果均可对应。成功立即结束会话，失败最多一次模型修复；费用不明、模型不符或中断会停止整批，已预约请求不重发。模拟与真实记录分开冻结，不能续接混用。 | Persist reservations before calls and bind raw responses, usage, identifiers, timing, candidates, Lean logs, and outcomes. Stop sessions on success and allow one repair otherwise. Unknown cost, model mismatch, or interruption stops the batch without resending reservations. Fixture and provider modes cannot be mixed. |
| 2026-10-27 已重查[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)：按峰时未缓存价格及 25% 余量，48 次最大预约 $2.654208，控制上限 $5。用量含推理，不重复相加；这是本地保守估计，不是账户账单。 | [Official prices](https://api-docs.deepseek.com/quick_start/pricing/) were rechecked on 2026-10-27. Peak uncached rates with 25% headroom reserve $2.654208 for all 48 calls, below the $5 ceiling. Output usage already includes reasoning. This is a conservative local estimate, not an invoice. |
| 新 `bwrap` 执行边界隐藏主目录与私有环境、禁用网络，只读挂载工具链、核验器和输入，单独提供输出目录。真实 Lean 元程序执行的无敏感哨兵检查已经通过。它不提供 cgroup 配额，也不声称能抵御任意 Lean 运行时或审计器被攻破。 | The new `bwrap` boundary hides home/private environment, disables networking, mounts trusted tools and inputs read-only, and provides separate scratch outputs. Harmless sentinel checks executed from actual Lean metaprograms passed. This is neither a cgroup quota nor a guarantee against arbitrary Lean runtime/auditor compromise. |

先提交输入与控制器，再创建一次运行记录；原始记录保存在 Git 忽略的 `data/` 中。下面的变量仅指向用户选定的密钥文件，密钥内容不进入命令行或记录。
Commit inputs and controllers before preparing a run. Raw records live in Git-ignored `data/`. The variable below points to the user-selected credential file; its contents never enter arguments or records.

```bash
python3 scripts/control_method_use.py prepare data/method-use-v1
python3 scripts/control_method_use.py preflight data/method-use-v1
python3 scripts/control_method_use.py next data/method-use-v1 --key-file "$MAAM_DEEPSEEK_KEY_FILE"
python3 scripts/control_method_use.py report data/method-use-v1
```

| 中文 | English |
| --- | --- |
| `next` 只执行一个尝试；每次从完整记录恢复状态，最多 48 次，不会自动重跑失败版本。报告中正向四题与边界两题分开列出；模型自述不能作为方法应用证据，只保守记录核验后证明的直接引理依赖。 | `next` executes one attempt, deriving state from complete records each time, with no more than 48 calls or automatic reruns. Report the four positive tasks separately from the two boundary tasks. Use checked direct lemma dependencies as conservative evidence rather than model self-report. |
| 整包计量包含同样的六个目标、严格更短才采用的候选和共同参考回退。指南只在 B 计一次；本地整体源码还包含基础、引理和目标定义。原始日志与共同研究基础设施另列，不以删除失败改善压缩。 | Package measurement preserves six-goal coverage using verified references and strictly shorter candidate adoption. Charge the guide once in B; joint local source also includes the base, lemma, and goal definitions. Logs and common research infrastructure are separate; failures are preserved. |
| 本次只检验作者提供的指南是否帮助模型使用同一数学库；不检验自动发现、自动检索、跨领域迁移或新理论价值。相同表现也是完成试验，不继续调题求胜。 | This tests author-supplied guidance over the same mathematical library, not discovery, retrieval, cross-domain transfer, or new-theory value. Equal performance still completes the trial without retuning tasks to force a win. |

**现场结果 · 2026-10-27 / Live results · 2026-10-27**

| 中文 | English |
| --- | --- |
| 输入、控制器和测试先提交为 `42a49e4`，再创建唯一真实账本 `data/method-use-v1/`。24 个模型会话完成，共 26 次真实 DeepSeek 调用；没有调用 OpenAI，也没有人工修复评分中的证明。 | Inputs, controllers, and tests were committed as `42a49e4` before preparing the sole live ledger at `data/method-use-v1/`. All 24 model sessions completed in 26 DeepSeek calls, without OpenAI calls or human proof repairs during scoring. |
| [提交摘要](../results/method-use-v1.json)与本地原始记录重新计算的报告完全一致。完整请求、原始响应、两次失败、模型修复、用量及 Lean 日志都保留在忽略目录中；摘要不能单独替代原始证据回放。 | The [committed summary](../results/method-use-v1.json) exactly matches replay from local raw records. Requests, responses, both failures, model repairs, usage, and Lean logs remain in the ignored directory. The summary alone cannot replace raw-evidence replay. |

| 指标 / Measure | A · 无额外指南 / No extra guide | B · 有指南 / With guide |
| --- | ---: | ---: |
| 正向四题首轮核验 / Positive first-attempt verification | 8/8 | 8/8 |
| 边界两题首轮核验 / Boundary first-attempt verification | 3/4 | 3/4 |
| 全部预算内核验 / All within-budget verification | 12/12 | 12/12 |
| 真实调用 / Live calls | 13 | 13 |
| 输入 token / Input tokens | 8905 | 13859 |
| 输出 token（含推理）/ Output tokens including reasoning | 22690 | 10125 |
| 保守费用估算 / Conservative estimated cost | $0.037374375 | $0.020384625 |
| 调用等待秒数 / Provider-call elapsed seconds | 133.307 | 62.193 |
| Lean 命令秒数 / Lean-command elapsed seconds | 33.728 | 33.493 |
| 正向证明直接依赖共享引理 / Positive proofs directly depending on the common lemma | 8/8 | 7/8 |
| 六目标非共享 zlib 字节 / Six-goal nonshared zlib bytes | 414 | 1296 |
| 含共同数学源码的 zlib 字节 / Joint local mathematical-source zlib bytes | 989 | 1798 |

| 中文 | English |
| --- | --- |
| 总用量为输入 22764、输出 32815、合计 55579 token；按冻结价格和余量估算 $0.057759。A 在 U05、B 在 U06 各有一份编译拒绝，均由同一会话中的下一次模型调用修复。失败也计入表中全部成本。 | Total usage is 22764 input and 32815 output tokens, or 55579 overall, estimated at $0.057759 under frozen rates and margin. A had one compiler rejection on U05 and B one on U06; both passed after their session's next model call. All failure costs are included. |
| **完成的工程证据：**模型没有拿到目标答案或人工绑定，也能在这些任务中形成核验证明；15 份正向证明有共享引理的直接依赖证据。剩余一份只记为方法使用未分类，可能内联、间接，也可能采用其他论证。 | **Engineering evidence established:** without target answers or author bindings, the model produced verified proofs on these tasks. Fifteen positive proofs have direct dependencies on the common lemma. The remaining proof is unclassified and may use an inline, indirect, or different argument. |
| **观察到的取舍：**两组成功率相同，正向任务存在满分上限。本次 B 的输出、等待与费用更低，输入与存储更高。这是这批作者设计近邻任务的观察；两个重复不能建立稳定的一般效应、跨领域迁移或内部理解难度函数。 | **Observed tradeoff:** success rates match, with a ceiling on the positive tasks. B used less output, waiting, and estimated cost but more input and storage. These observations concern author-designed nearby tasks; two repetitions establish neither a stable general effect, cross-domain transfer, nor an internal comprehension function. |
| 最终全量 **403 项测试通过**；历史结果回放通过。新摘要与原始记录回放一致，另经独立只读复核核对全部 26 份原始响应、用量、模型标识和哈希。提交前检查未发现密钥内容或私有凭据路径。 | The final full suite passed **403 tests**, and historical-result replay passed. The new summary matches raw replay; an independent read-only review also checked all 26 raw responses, usage records, model identifiers, and hashes. Pre-commit screening found no credential contents or private credential paths. |
| 不再修改此版本求胜。下一步的[构造映射与封闭性运输](CLOSURE_TRANSPORT.md)已进入离线准备，优先复用同态/核材料；新增真实试验须另行冻结协议和额度。工程继续使用 6.1 Sol，实验模型仍为 DeepSeek。 | Do not retune this version to force a win. [Map construction and closure transport](CLOSURE_TRANSPORT.md) is now in offline preparation, reusing homomorphism/kernel material. A further live trial needs its own frozen protocol and allowance. Continue scoped engineering with 6.1 Sol and use DeepSeek for experiments. |
