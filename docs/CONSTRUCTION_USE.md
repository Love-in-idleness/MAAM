# 受约束构造的指南试验 / Guidance for constrained constructions

| 中文 | English |
| --- | --- |
| **2026-10-27 · 冻结前工程。** [协议](../experiments/closure_use_v1/README.md)接续[离线构造材料](CLOSURE_TRANSPORT.md)，复用六个任务、全部数学源码、人工参考与 288 词指南的原版本，通过哈希绑定。旧实验与核验器保持冻结。此处先记录设计和运行接口，实际结果另列。 | **2026-10-27 · Pre-freeze engineering.** The [protocol](../experiments/closure_use_v1/README.md) follows the [offline construction material](CLOSURE_TRANSPORT.md), binding its six tasks, mathematical sources, author references, and 288-word guide by hash. Earlier experiments and checkers remain frozen. Design and execution interfaces are recorded here; actual results appear separately. |
| 核心问题是：相同数学库下，AI 能否完成“构造同态并运输封闭性”的证明义务，指南是否改变可靠性或使用成本？两组均能看到一般运输引理；只有 B 组收到指南。人工参考、任务角色和已有目标证明不进入模型请求。 | The question is whether AI can complete map-construction and closure-transport obligations, and whether guidance changes reliability or use costs with the same mathematical library. Both arms see the transport lemma; only B sees the guide. Author references, task roles, and existing target proofs stay outside model requests. |
| c01–c04 的目标已指定映射类型及逐点行为。核验通过说明模型生成了满足保持性质、一致性和封闭性的存在性证书；不说明它发现了未知映射、自动选定了策略或生成了可执行见证。c05–c06 的有限反例单独计数，允许 `decide`。 | Goals c01–c04 specify map types and pointwise behavior. Verification establishes model-generated existential certificates satisfying preservation, agreement, and closure, without establishing map discovery, strategy selection, or executable witness extraction. Finite counterexamples c05–c06 are counted separately and permit `decide`. |
| 六题、两组、两次重复，共 24 个独立会话。每题顺序为 A1、B1、B2、A2。每会话最多一次初始调用和一次模型自修复，成功即停止；全轮最多 48 次 DeepSeek Flash 调用，低推理配置，费用上限 $5。不因失败换目录重置额度。 | Six tasks, two arms, and two repetitions produce 24 independent sessions, ordered A1, B1, B2, A2 for each task. Each allows an initial call and one model repair, stopping on success. The round permits at most 48 DeepSeek Flash calls at low reasoning effort and a $5 ceiling. A new directory cannot reset the allowance. |
| 每次调用预约输入 16,384、输出 32,768 token，硬截止 180 秒。按输入 $0.30/M、输出 $1.20/M 的峰时价加 25% 余量，全轮最坏预约 $2.654208。价格核对日期 2026-10-27；该数是保守估算，账户账单另验。 | Each call reserves 16,384 input and 32,768 output tokens, with a hard 180-second deadline. Peak rates of $0.30/M input and $1.20/M output plus 25% margin reserve $2.654208 for the whole round. Prices were checked on 2026-10-27. This is a conservative estimate; account billing is separate. |
| 调用前落盘预约；未知用量、模型不匹配、超限和不完整事件停止整轮，不自动重发。格式或 Lean 拒绝可在会话额度内修复；修复仅含自己的输出和清理后的核验反馈。密钥仅在本地执行时读取，不进入模型请求正文、账本或提交。 | Persist reservations before calls. Unknown usage, model mismatch, overruns, and incomplete events stop the round without automatic resends. Format or Lean rejection may receive a repair within the session allowance, using only its own output and sanitized verification feedback. Read credentials only during local execution; exclude them from model payloads, ledgers, and commits. |
| 内层离线套件的一次人工提交额度仍冻结不变，供给每次核验的源码、心跳和超时限制；新外层协议单独管理每会话两次模型调用。完整 `Proof.lean` 通过现有沙箱与目标/公理审计，不能把完整源码当作证明项再次包裹。 | The inner offline suite retains its one-author-attempt allowance and supplies source, heartbeat, and timeout limits per verification. The new outer protocol separately permits two model calls per session. Complete `Proof.lean` sources go directly through existing sandbox and goal/axiom audits, without being wrapped again as proof terms. |
| 分别记录首轮成功、预算内成功、直接命名引理依赖、生成用量、耗时和整包压缩。直接依赖缺失也可能表示间接或内联使用；不据此推断没用方法。指南效果包含注意、检索和 Lean 语法帮助。小型开发题不支持普遍能力、新理论价值或预留迁移结论。 | Record initial and within-budget success, direct named-lemma dependencies, generation usage, time, and complete-package compression separately. Missing direct dependencies can reflect indirect or inline use and do not establish non-use. Guide effects include attention, retrieval, and Lean syntax help. Small development tasks do not establish general ability, theory value, or held-out transfer. |
| 共同数学源码计一次，B 组指南计一次；每题保留同一份已核验人工参考作为后备，仅用完整 Proof 源码 token 数严格更少的候选替换。失败、等长和更长的输出仍保留研究记录。原始收据与日志保存在忽略目录，提交摘要本身不能代替它们。 | Count common mathematical sources once and the B guide once. Retain the same verified author fallback for every goal, adopting only candidates with strictly fewer complete Proof source tokens. Preserve failed, equal-length, and longer outputs as research records. Raw receipts and logs remain ignored; committed summaries cannot replace them. |

```bash
# Commit protocol, controller, and tests before preparing the live ledger.
python3 scripts/control_construct_use.py prepare data/closure-use-v1
python3 scripts/control_construct_use.py preflight data/closure-use-v1
# Supply the authorized local key-file path; never paste a key value.
python3 scripts/control_construct_use.py next data/closure-use-v1 --key-file /path/to/private-key-file
python3 scripts/control_construct_use.py report data/closure-use-v1
```

| 中文 | English |
| --- | --- |
| 官方接口与价格：[DeepSeek Responses](https://api-docs.deepseek.com/api/create-response/)、[价格表](https://api-docs.deepseek.com/quick_start/pricing/)。请求与响应模型标识保留；别名不证明不可变的精确权重版本。下一步继续用 6.1 Sol 完成冻结、验收和有界运行，实验调用只使用 DeepSeek。 | Official interface and prices: [DeepSeek Responses](https://api-docs.deepseek.com/api/create-response/) and [pricing](https://api-docs.deepseek.com/quick_start/pricing/). Preserve requested and reported model identities; an alias does not prove an immutable exact weight revision. Continue with 6.1 Sol for freezing, acceptance, and bounded execution, using DeepSeek alone for experiment calls. |

| 中文 | English |
| --- | --- |
| 冻结前验收：新增 16 项测试及全量 **431 项测试通过**，六份参考通过真实沙箱，历史静态报告与前两轮摘要回放一致。模拟收据只验证控制器，不计为供应商调用。 | Pre-freeze acceptance: all **431 tests pass**, including 16 new tests; six references pass the real sandbox. Historical static reports and both preceding summaries replay unchanged. Synthetic receipts test controller behavior and do not count as provider calls. |

## 本地运行结果 / Local run results

| 中文 | English |
| --- | --- |
| 实现与输入先冻结为 `5d082082e7de1af413980815a7aeff4030f92cba`，再生成 `data/closure-use-v1/`。**39 次真实 DeepSeek 调用完成 24 个会话，全部预算内核验通过，保留 15 次首次拒绝和模型自修复。**未追加调用、改题或手工修正模型答案。 | Freeze code and inputs at `5d082082e7de1af413980815a7aeff4030f92cba` before creating `data/closure-use-v1/`. **39 live DeepSeek calls complete all 24 sessions within budget, preserving 15 initial rejections and model repairs.** No extra calls, revised tasks, or manual model-answer repairs were added. |
| **主要接口混杂：15 次拒绝中，14 次仅因 `Submission.solve` 用 `def` 声明，而核验器要求 theorem；另一次因未知的 `congrArg₂` 编译失败。**现有共享提示只写“define Submission.solve”，没有明确要求 Lean 的 `theorem` 声明。14 次中 8 次修复只改了 `def` 为 `theorem`。这是我们输出合约说明不足，不能归因为数学构造失败。回查上一轮方法指南试验的两次拒绝，也均为同一声明问题，已在[原说明](METHOD_USE.md)补充审查结论。 | **Primary interface confound: 14 of 15 rejections solely use `def` for `Submission.solve`, while the checker requires a theorem; one compilation fails on unknown `congrArg₂`.** The shared prompt says “define Submission.solve” without explicitly requiring Lean's `theorem` declaration. Eight of these fourteen repairs change only `def` to `theorem`. This is an underspecified output contract, not evidence of mathematical construction failure. Both rejections in the previous guidance trial share this cause; the [earlier documentation](METHOD_USE.md) now records that review. |
| 以下首轮分数保留冻结规则的原计分，不事后改判。两组首次拒绝数的差异主要受声明格式影响，**不能据此推断指南损害数学推理**，也未证实指南带来可靠性收益。本版本作为研究档案保留，暂不把指南加入默认提示。 | Initial scores below retain the frozen scoring rules without retrospective rescoring. Declaration format dominates rejection differences, so they **cannot establish that guidance harms mathematical reasoning**. A reliability gain is also unestablished. Archive this version and keep the guide out of default prompts for now. |

| 指标 / Metric | A：无指南 / No guide | B：有指南 / Guide |
| --- | --- | --- |
| 首轮核验 / Initial verification | 6/12 | 3/12 |
| 预算内核验 / Within-budget verification | 12/12 | 12/12 |
| 正向首轮 / Positive initial | 3/8 | 1/8 |
| 正向预算内 / Positive within budget | 8/8 | 8/8 |
| 边界首轮 / Boundary initial | 3/4 | 2/4 |
| 边界预算内 / Boundary within budget | 4/4 | 4/4 |
| 真实调用 / Live calls | 18 | 21 |
| 自修复 / Model repairs | 6 | 9 |
| 输入 token / Input tokens | 31,194 | 45,266 |
| 输出 token / Output tokens | 45,587 | 45,476 |
| 最终正向证明直接运输引理依赖 / Final positive direct transport dependencies | 0/8 | 0/8 |
| 择优完整 Proof 源码 token / Selected complete Proof source tokens | 519 | 506 |
| 非共享 zlib 字节 / Nonshared zlib bytes | 629 | 1530 |
| 共同数学源码加择优材料 zlib 字节 / Joint mathematical source and selected material zlib bytes | 1883 | 2812 |

| 中文 | English |
| --- | --- |
| 16 份成功正向证明的类型、保持性质、逐点一致性与封闭性均通过核验。它们打包 `Hom` 后内联证明封闭性；源码未出现 `preimage_mul_closed`，没有额外顶层辅助声明。没有观察到命名运输引理调用，但仍可能体现同一概念方法；不能声称模型没有使用方法，也不能声称已验证方法卡的独立复用。 | All sixteen successful positive proofs verify types, preservation, pointwise agreement, and closure. They bundle `Hom` and prove closure inline, without a `preimage_mul_closed` mention or extra top-level helper declaration. No named transport-lemma reuse is observed. Conceptual use remains possible; neither absence of method use nor independent method-card reuse is established. |
| 同一组人工后备证明共 556 源码 token。两组都只在 c03/c04 采用严格更短的模型证书，其余保留原证。B 组所选证明少 13 token，但指南计一次后，完整压缩材料比 A 更大。此项是事后证书组合比较，不改写模型成功率，也不等同于新增理论收益。 | The same author fallbacks total 556 source tokens. Both arms adopt shorter model certificates only for c03/c04 and retain other originals. B's selected proofs use 13 fewer tokens, while its complete compressed material is larger after charging the guide once. This post-hoc certificate selection does not change model success rates or establish new-theory gains. |
| 全轮输入 76,460、输出 91,063、总计 167,523 token，用量全部已知；峰时价加 25% 余量估算 **$0.165267**，账户账单未核对。39 个响应 ID 唯一且非空，均报告 `deepseek-flash` 和 completed；请求头 request ID 均未提供，保持 null。模型别名不是精确权重版本证据。 | The round uses 76,460 input and 91,063 output tokens, totaling 167,523, with complete usage. Peak rates plus 25% margin estimate **$0.165267**; account billing is unchecked. All 39 nonempty response IDs are unique and report `deepseek-flash` and completed; header request IDs are unavailable and remain null. The model alias does not prove an exact weight revision. |
| [结果摘要](../results/closure-use-v1.json)与原始记录离线重算完全一致；独立只读审查另核对收据、用量、目标契约和严格缩短选择。原始记录保留在 Git 忽略目录，摘要不能代替收据和日志。导出检查未发现私有路径或凭据标记；真实调用仅用 DeepSeek。 | The [summary](../results/closure-use-v1.json) exactly matches offline replay from raw evidence. Independent read-only review checks receipts, usage, goal contracts, and strict-shorter selection. Raw evidence remains ignored; summaries cannot replace receipts and logs. Export checks find no private-path or credential markers; all live calls use DeepSeek. |
| **下一步先修输出契约，不扩题重跑。**后续版本应显式要求 `theorem Submission.solve`（可用 namespace 形式），在输入中声明 theorem 种类，并用测试检查提示与核验器一致。本轮源码、协议、原分数和失败保持冻结。继续用当前 6.1 Sol 完成这项接口修订与离线验收；这是工程契约问题，尚不需要转 Astra。新一轮真实调用需要另行冻结独立协议和预算。 | **Next clarify the output contract before expanding or rerunning tasks.** A subsequent version should explicitly require `theorem Submission.solve` (namespace syntax allowed), declare the theorem kind in the input, and test prompt/checker agreement. Preserve this run's code, protocol, original scores, and failures. Continue with the current 6.1 Sol for that interface revision and offline acceptance; this engineering contract issue does not yet require Astra. Any new live round needs a separately frozen protocol and budget. |
