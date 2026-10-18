# 包消融与有限证明组合 / Package ablations and finite proof portfolios

本轮实现 M3 的受控消融部分：在相同任务上比较已有证明和采用不同理论包的迁移证明，并保留成本之间的权衡。
This implements the controlled ablation part of M3: compare existing proofs with migrations using different theory packages on identical tasks, retaining cost trade-offs.

独立模型评价、多轮概念发展和延迟价值实验仍待完成。
Independent model evaluation, multi-round concept development and delayed-value experiments remain pending.

## 固定配置 / Frozen configurations

| 配置 / Configuration | 可用知识 / Available knowledge | 给定证明数 / Supplied proofs |
| --- | --- | ---: |
| baseline | 原始函数、群运算和保持乘法的假设 / Raw functions, group operations and multiplication-preservation hypotheses | 20 |
| naming | 给原有保持乘法条件和恒等元纤维起缩写名 / Abbreviations for existing preservation predicates and identity fibres | 40 |
| definitions | 同态结构、核谓词和核载体；没有核乘法定理 / Homomorphism structures, kernel predicates and carriers, without the kernel multiplication theorem | 40 |
| full | M1/M2 的完整同态／核包，包括核乘法定理与运算 / The unchanged M1/M2 package, including the kernel multiplication theorem and operation | 40 |

20 个目标逐字节复用 M2 的公开校准集；12 个开发目标和 8 个预留目标的标签不变，本轮不构成独立预留评价。
The 20 goals reuse M2's public calibration set byte for byte; its 12 development and 8 reserved labels are unchanged, and this is not an independent held-out evaluation.

每个候选配置都保留 baseline 的原证明，并提供一份采用该包的参考证明；程序检查原证明确实保留，允许选择不使用新对象。
Every candidate configuration retains the baseline proof and supplies a package-based reference proof; software checks that the original proof is retained and permits choosing not to use the new object.

这是 140 份给定证明的有限集合，不是 140 次独立 LLM 搜索；基线与候选池的大小不同，不能据此估计模型求解表现。
This is a finite collection of 140 supplied proofs, not 140 independent LLM searches; pool sizes differ between baseline and candidates and do not estimate model-solving performance.

`study.json` 冻结各套清单和证明池；清单进一步冻结 Lean 源码，驱动器强制相同基础、目标、划分、工具链和提交预算。
`study.json` freezes manifests and proof pools; those manifests freeze Lean sources, and the runner enforces identical foundations, goals, splits, toolchains and submission budgets.

## 完整成本 / Complete costs

源码成本采用 M1 的解析 token 口径，计入每个已选证明的完整模块，以及整个候选包一次。
Source cost uses M1's parsed-token convention, charging each selected complete proof module and the whole candidate package once.

新的 `Inventory.lean` 计量所有收费模块中每个声明的类型与可读取值，包含编译器生成声明、局部辅助声明和未使用声明。
The new `Inventory.lean` measures the type and available value of every declaration in charged modules, including compiler-generated, auxiliary and unused declarations.

表达式按构造器出现次数计数，忽略元数据包装，不展开常量引用；定义、证明、构造子与递归子等都登记，整个候选包只计一次。
Expressions count constructor occurrences, omit metadata wrappers and do not inline constant references; definitions, proofs, constructors and recursors are inventoried, with the whole candidate charged once.

这一口径计量有限模块声明的表示成本，不声称等于二进制大小、全局最短证明长度或数学价值。
This measures representation cost across finite module declarations, without equating it with binary size, globally shortest proofs or mathematical value.

M2 报告的 11186→6120 是局部证明表达式成本，未计整个包；本轮的完整表达式账本应单独读取，不能把两者混用。
M2's 11,186→6,120 counts local proof expressions and omits the whole package; read this experiment's complete expression ledger separately rather than mixing the two measures.

每份有效证明先经原目标与依赖审计，再从相同字节重新编译并计量；计量器检查目标表达式大小与第一次审计一致。
Each valid proof first passes original-goal and dependency audits, then is recompiled from identical bytes for measurement; the inventory checks target expression sizes against the first audit.

两个编译阶段的日志与预算分别保留，验证耗时不当作模型搜索速度。
Both compilation stages retain separate logs and budgets; verification time is not interpreted as model-search speed.

## 有限组合与比较关系 / Finite portfolios and comparison relations

每个任务可以有多个经检查的证明；报告保留源码与完整表达式成本构成的 Pareto 前沿。
Each task may have multiple checked proofs; reports retain the Pareto frontier of source and complete expression costs.

动态规划遍历给定证明的组合，每个任务选一份证明，并将候选包成本加一次；在当前上限内，前沿对这个有限集合是精确的。
Dynamic programming combines supplied proofs, selecting one per task and adding the candidate package once; within the configured limit, its frontier is exact for that finite collection.

每个前沿点附带逐任务的尝试编号，可以定位相应证明；超过前沿状态预算时返回未确定，不截断后声称最优。
Each frontier point carries task/attempt choices identifying its proofs; exceeding the frontier-state budget returns undetermined rather than truncating and claiming optimality.

在相同目标集上，如果左侧前沿能逐点弱支配右侧，而反向不成立，则报告 `left_dominates`；双方成立为 `equivalent`，双方都不成立为 `incomparable`。
On an identical goal set, report `left_dominates` when the left frontier weakly covers every right-frontier point and the reverse does not hold; mutual coverage gives `equivalent`, and neither gives `incomparable`.

这在同一比较上下文中给出允许等价与不可比的成本关系，无需选择源码和表达式之间的权重。
Within one comparison context, this gives a cost relation allowing equivalence and incomparability without choosing weights between source and expressions.

证明覆盖和可计量覆盖分别报告；成本只比较共同可计量目标，没有共同任务时返回未确定。
Proof coverage and measurable coverage are reported separately; cost comparisons use common measured goals, returning undetermined when none exist.

顶层 `frontiers` 使用所有配置共同的目标集，`pairs` 还保留每对配置自己的交集；不同目标集上的局部关系不能拼成同一个全局排序。
Top-level `frontiers` use the goal set common to all configurations, while `pairs` also retain each pair's own intersection; local relations on different goal sets must not be combined into one global order.

## 运行与回放 / Run and replay

使用已安装并预热的 Lean 4.24.0，在新的工作目录中执行：
Use an installed and warmed Lean 4.24.0 toolchain with a new working directory:

```bash
python -m maam ablation \
  --study experiments/hom_kernel_ablation/study.json \
  --workdir data/my-ablation --workers 2
```

运行完整校准与边界检查：
Run the complete calibration and boundary checks:

```bash
python scripts/check_ablation.py --output data/ablation --workers 2
```

边界检查包括：收费未使用辅助声明、拒绝计量已被改动的证明，以及在定义配置中拒绝调用已移除的引理。
Boundary checks charge unused auxiliary declarations, reject measuring changed proof bytes, and reject calls to removed lemmas in the definitions configuration.

输出包括四份配置证据、共同目标的组合前沿、逐对比较、证明使用的候选声明，以及每次验证和计量的原始轨迹。
Outputs include four configuration evidence files, common-goal portfolio frontiers, pairwise comparisons, candidate declarations used by proofs, and raw verification/measurement traces.

既有 M1/M2 审计器和归档指纹保持不变；新计量器、消融驱动器和证明池有各自的冻结指纹。
Existing M1/M2 auditors and archived fingerprints remain unchanged; the new inventory, ablation runner and proof pools have their own frozen fingerprints.

CLI 在工具链缺失时返回 1，在没有共同可计量目标或前沿计算超出预算时返回 2；有效的有限比较返回 0，覆盖情况仍需读取报告。
The CLI returns 1 for a missing toolchain, 2 for no common measured goals or exhausted frontier computation, and 0 for a valid finite comparison; read the report for coverage.

## 2026-10-18 校准结果 / Calibration results

[实际 Lean 工作流](https://github.com/Love-in-idleness/MAAM/actions/runs/39116120183) 已通过 140/140 份给定证明及完整声明计量，三个边界检查也通过；本地 Python 测试为 96 项。
The [actual Lean workflow](https://github.com/Love-in-idleness/MAAM/actions/runs/39116120183) passed all 140 supplied proofs and complete declaration inventories, plus all three boundary checks; 96 local Python tests pass.

下表的坐标顺序是“源码 token，完整表达式节点”；完整包的两个端点对应不同的证明组合。
Coordinates below are “source tokens, complete expression nodes”; the full package's endpoints use different proof combinations.

| 配置 / Configuration | 前沿点数 / Points | 低源码端 / Minimum-source endpoint | 低表达式端 / Minimum-expression endpoint |
| --- | ---: | ---: | ---: |
| baseline | 1 | (904, 11206) | (904, 11206) |
| naming | 1 | (1034, 11314) | (1034, 11314) |
| definitions | 1 | (1077, 14547) | (1077, 14547) |
| full | 38 | (1256, 15547) | (1426, 10481) |

baseline 在这组成本维度上支配 naming 和 definitions，naming 支配 definitions；full 与其余三个配置都不可比。
Baseline dominates naming and definitions on these cost dimensions, and naming dominates definitions; full is incomparable with each of the other three configurations.

完整包本身的成本为 312 个源码 token 和 4341 个表达式节点，都已计入一次；保留原证明让系统能够选择部分迁移，而非强迫所有目标采用新对象。
The full package costs 312 source tokens and 4,341 expression nodes, both charged once; retaining original proofs lets the system select partial migrations instead of forcing every goal to use new objects.

这些结果只约束当前冻结任务与给定证明集合，不推出定义无一般数学价值，也不估计独立模型的搜索收益。
These results apply only to the frozen tasks and supplied proof collection; they establish neither that definitions lack general mathematical value nor a search benefit for an independent model.

完整证据与收据见 [results/ablation](../results/ablation/)，`python scripts/verify_results.py` 会检查指纹，并从四份配置证据精确重算组合前沿及比较关系。
See [results/ablation](../results/ablation/) for evidence and the receipt; `python scripts/verify_results.py` checks fingerprints and exactly recomputes portfolio frontiers and comparison relations from the four configuration evidence files.

CI 产物中的逐次证明、审计、计量和命令日志保留 30 天；冻结源码和证明池可用于重新生成它们。
Per-attempt proofs, audits, inventories and command logs remain in CI artifacts for 30 days and can be regenerated from the frozen sources and proof pools.

本轮报告继续标记 `search_performed=false`、`held_out_evaluation=false` 和 `training_eligible=false`，供后续独立实验设计反馈，而不是直接充当强化学习偏好标签。
Reports retain `search_performed=false`, `held_out_evaluation=false` and `training_eligible=false`, informing feedback design for later independent experiments rather than directly serving as reinforcement-learning preference labels.
