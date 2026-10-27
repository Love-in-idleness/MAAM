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
