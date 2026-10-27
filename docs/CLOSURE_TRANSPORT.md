# 构造映射与封闭性运输 / Map construction and closure transport

| 中文 | English |
| --- | --- |
| **2026-10-27 · 离线工程。** 延续[已选定的方向](METHOD_RESEARCH_DESIGN.md)，把“构造映射—证明保持性质—运输封闭性”做成[可核验材料](../experiments/closure_transport_v1/README.md)。本轮新增模型调用为零，没有读取密钥。 | **2026-10-27 · Offline engineering.** Following the [chosen direction](METHOD_RESEARCH_DESIGN.md), prepare [checkable material](../experiments/closure_transport_v1/README.md) for constructing maps, proving preservation, and transporting closure. This round makes zero model calls and reads no credentials. |
| 例子：要证明 `P(f(x)) ∧ Q(q(x))` 的乘法封闭性，构造 `F(x) = (f(x), q(x))`。分别证明两个坐标保持乘法、目标条件 `P × Q` 封闭，再把封闭性沿 F 拉回。这是组织已有论证的方法，不是新数学发现。 | Example: for multiplication closure of `P(f(x)) ∧ Q(q(x))`, construct `F(x) = (f(x), q(x))`. Prove coordinatewise preservation and closure of `P × Q`, then pull closure back along F. This organizes known reasoning rather than claiming a mathematical discovery. |
| 四个正向目标要求证明 `∃ F : Hom, 逐点一致性 ∧ 原像封闭性`，Hom 的字段同时要求乘法保持证明。这样不能用一个无关映射满足任务；不过这是存在性证书，不是可执行见证提取。人工参考源码明确给出构造，模型是否能自行完成尚未检验。 | The four positive goals require `∃ F : Hom, pointwise agreement ∧ preimage closure`, while Hom itself requires preservation evidence. An unrelated map cannot satisfy the contract. These are existential certificates, not executable witness extraction. Author source provides explicit constructions; model construction remains untested. |
| 保留原有群与同态源码，新增通用乘积群、Bool XOR 群，以及一个乘法封闭性定义和原像运输引理。这里只核验乘法封闭性，没有把它称为子群；群假设强于运输所必需的假设，当前保留它以复用已有工具。 | Retain existing group/homomorphism sources, adding generic product and Bool XOR groups, one multiplication-closure definition, and one preimage lemma. Multiplication closure is not subgroup structure. Group assumptions are stronger than necessary and are retained to reuse existing tools. |

| 任务 / Task | 核验内容 / What is checked |
| --- | --- |
| c01 · 原像 / Preimage | 从原始函数及保持等式打包同态，再拉回封闭性。 / Bundle a raw function and its preservation equation, then pull back closure. |
| c02 · 复合 / Composition | 构造复合映射，用两个保持等式证明它保持乘法。 / Construct a composite and combine the two preservation equations. |
| c03 · 同时约束 / Simultaneous constraints | 构造配对映射，证明目标乘积谓词封闭，再拉回。 / Construct a paired map, prove product-predicate closure, then pull back. |
| c04 · 等化约束 / Equalizer | 构造配对映射，以对角谓词表达两坐标相等；不假设交换性。 / Use a paired map and diagonal predicate, without assuming commutativity. |
| c05 · 缺少保持性质 / Missing preservation | Bool XOR 群的单位单点集封闭，但经 `not` 的原像不封闭。 / The neutral singleton is closed under Bool XOR, but its preimage under `not` is not. |
| c06 · 缺少目标封闭性 / Missing target closure | 恒等映射保持运算，但单点集 `{true}` 在 Bool XOR 下不封闭。 / Identity preserves the operation, but `{true}` is not XOR-closed. |

| 中文 | English |
| --- | --- |
| 新检查器复用原有冻结、预约、目标/公理审计、日志回放及操作系统沙箱。每题只提交一份冻结的人工参考；中断或失败保留，不自动修复。不修改上次真实试验的控制器或结果。 | The checker reuses freezing, reservations, goal/axiom auditing, log replay, and OS isolation. Submit one frozen author reference per task; preserve interruptions and failures without automatic repair. Previous live controllers and results stay unchanged. |
| 可以预览有指南和无指南的输入；两者数学材料完全相同，只允许指南这一差异。参考答案、人工说明和任务角色标签不进入预览。本轮没有模型 API 接口、密钥参数或新调用额度。 | Preview solver inputs with or without guidance; mathematics matches and only guidance differs. References, author explanations, and task-role labels stay out. There is no model API interface, credential argument, or new call allowance in this round. |
| 绝对压缩量只描述本版本。`package_guide_and_proofs` 只含 Method、指南与完整证明，排除已声明的基础；`joint_local_sources` 另计所有基础、**新 Products 辅助模块**和任务规格。共同检查器源码单列一次。没有旧工具基线或同预算生成对照，因此不报告压缩改善。 | Absolute compression describes this version only. `package_guide_and_proofs` contains Method, guidance, and complete proofs, excluding the declared base. `joint_local_sources` also includes all base material, **new Products helpers**, and task specifications. Count shared checker source separately once. Without an old-tool baseline or matched generation, report no compression improvement. |
| 全部任务都是作者设计的开发任务，不是预留测试。显式目标已指定映射的类型和逐点行为；将来的模型试验首先检验能否完成这种受约束的构造，不宣称发现未知映射或自动选择数学策略。 | All tasks are author-designed development cases. Goals already specify map types and pointwise behavior. A future model trial would first test constrained construction, not discovery of unknown maps or automatic strategic selection. |

```bash
# Commit the fixture and checker first.
python3 scripts/check_closure_transport.py prepare data/closure-transport-v1
python3 scripts/check_closure_transport.py run data/closure-transport-v1
python3 scripts/check_closure_transport.py report data/closure-transport-v1
python3 scripts/check_closure_transport.py input data/closure-transport-v1 --task c03 --guide
```

| 中文 | English |
| --- | --- |
| 下一步继续用 6.1 Sol 准备独立构造试验的冻结输入与小额调用协议；实验模型优先 DeepSeek。保持数学内容相同、人工参考隔离和明确调用上限，再测量指南的使用效果。本次不扩大实验。 | Next use 6.1 Sol to prepare frozen inputs and a small-budget protocol for independent construction, prioritizing DeepSeek for experiments. Match mathematical content, isolate references, and fix call limits before measuring guidance effects. This round does not expand experimentation. |

**本地验收记录 / Local acceptance record**

| 中文 | English |
| --- | --- |
| 先提交实现与输入为 `ea04ac9`，再用该版本生成 `data/closure-transport-v1/`。正式记录中六题各检查一次，**6/6 通过 Lean 4.24.0**；四个正向证明都直接依赖一般运输引理，映射类型、保持性质、逐点一致性和封闭性均由内核检查。 | Commit implementation and inputs as `ea04ac9` before generating `data/closure-transport-v1/`. All **6/6 author references pass Lean 4.24.0**, one attempt each. All four positive proofs directly depend on the transport lemma, with types, preservation, pointwise agreement, and closure kernel-checked. |
| [结果摘要](../results/closure-transport-v1.json)可从本地记录重新计算，无须再次运行 Lean。完整数学源码加指南的 zlib 长度为 2828 字节，是单个版本的绝对计量，不代表压缩改善。新增模型调用为零，人工准备时间未知，不填零。 | The [summary](../results/closure-transport-v1.json) replays locally without rerunning Lean. Joint mathematical source and guidance compress to 2828 zlib bytes: an absolute measurement, not an improvement claim. New model calls are zero; unknown author-preparation time remains unknown. |
| **415 项全量测试通过**；历史结果与上一轮 26 次真实调用的报告回放保持一致。开发期的一次人工参考编译失败及后续修正检查保留在 `data/closure-transport-v1-development/`，不算模型失败。所有真实记录均保留在 Git 忽略目录；提交摘要不能单独代替原始日志。 | **All 415 tests pass**; historical reports and the previous 26-call live trial replay unchanged. An initial author-reference compile rejection and corrected development checks remain in `data/closure-transport-v1-development/`, without being counted as model failures. Raw evidence stays in Git-ignored directories; committed summaries do not replace it. |
