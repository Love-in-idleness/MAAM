# 理论包参考实验 / Theory-package reference experiments

本接口实现研究计划 M1 的参考迁移：在隔离的背景库中，检查加入候选包前后的两份给定证明，并计算可追溯的成本。
This interface implements the M1 reference migration: check two supplied proofs before and after adding a candidate to an isolated base library and compute auditable costs.

## 使用 / Usage

需要 Python 3.11+ 和 Lean 4.24.0；求证源码与候选清单位于 experiments/hom_kernel。
Requires Python 3.11+ and Lean 4.24.0; proof sources and candidate manifests are in experiments/hom_kernel.

~~~bash
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json
~~~

写入新报告并运行实际 Lean 错误输入检查：
Write a new report and run the actual Lean rejection checks:

~~~bash
mkdir -p data/theory-package
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json \
  --output data/theory-package/theory-package-reference.json
python scripts/check_theory_package.py \
  --report data/theory-package/theory-package-reference.json \
  --negative-output data/theory-package/theory-package-negative.json
~~~

输出文件须不存在；可以使用新的路径重新运行。
Output files must not already exist; use a new path for another run.

CLI 在成功比较时返回 0，验证预算耗尽时返回 2，证明或依赖审计拒绝时返回 3，输入及运行配置错误时返回 1。
The CLI returns 0 for a completed comparison, 2 for an exhausted verification budget, 3 for rejected proofs or dependency audits, and 1 for input or runtime-configuration errors.

## 输入格式 / Input format

experiment.json 固定基础模块、两种条件、原始目标、源码 SHA-256、Lean 版本及验证资源；package.json 描述核心思想和包中的定义、定理及对象。
experiment.json fixes base modules, both conditions, original goals, source SHA-256 values, Lean version and verification resources; package.json describes the idea and the package's definitions, theorems and objects.

首版仅接受 reference_migration 阶段和 development 任务；这是给定证明的参考实验，不能标记为预留集上的独立发现或求证性能评估。
Version 1 accepts only reference_migration and development tasks; supplied proof witnesses are reference evidence and cannot be labelled independent discovery or held-out proving performance.

所有输入源码必须位于实验目录内并匹配冻结指纹；基础、候选与两份证明模块不能重叠，也不能遮蔽 Lean 核心模块。
All source inputs must stay within the experiment directory and match frozen fingerprints; base, candidate and proof modules must be disjoint and cannot shadow Lean core modules.

冻结清单是可重放输入记录；改动候选或源码后应创建新的实验版本，并重新计算指纹。
The frozen manifest records replayable inputs; candidate or source changes require a new experiment version and recomputed fingerprints.

## 检查流程 / Verification

程序把两种条件的源码分别复制到新的临时目录，覆盖 LEAN_PATH，按固定顺序重新编译；既有 .olean 文件不会进入实验。
The runner copies each condition's sources into a fresh directory, replaces LEAN_PATH and recompiles in a fixed order; existing .olean files do not enter the experiment.

基线只得到背景和原证明；实验条件得到同一背景、候选包与迁移后的证明。
The baseline receives the base and original proof; the treatment receives the same base, candidate package and migrated proof.

审计器检查导入模块的传递闭包，逐个检查自有模块的声明及其依赖，并核实目标确实是原始目标的定理。
The auditor checks transitive imports, each experiment-module declaration and its dependencies, and verifies that targets are theorems of the original propositions.

新旧表述通过 Lean 的定义相等和最终原目标证明连接；首例中的同态构造及核成员关系在迁移证明中直接体现。
Lean's definitional equality and the final proof of the original goal connect representations; the reference witness explicitly constructs the homomorphism and uses kernel membership.

逻辑基础固定允许 propext、Quot.sound 和 Classical.choice；这些是 Lean 标准核心公理，生成的结构定理可能引用它们，报告会列出实际使用集合。
The foundation permits the fixed standard Lean axioms propext, Quot.sound and Classical.choice; generated structure theorems may use them, and the report lists the actual set used.

其他公理、sorryAx 和 unsafe 依赖会被拒绝；检查包括候选中未被目标使用的声明。
Other axioms, sorryAx and unsafe dependencies are rejected, including unused declarations in the candidate package.

本程序运行用户提供的 Lean 源码；模块和依赖检查是实验有效性约束，不构成操作系统安全沙箱。
The runner executes supplied Lean source; module and dependency checks enforce experimental validity and do not constitute an operating-system sandbox.

## 成本口径 / Cost conventions

源码 token 由 Lean 命令解析器统计带原始位置的 atom 和 identifier 叶节点；去重并排除普通、嵌套及文档注释，字符串按解析器叶节点计数。
Source tokens are original-position atom and identifier leaves from Lean's command parser, deduplicated with ordinary, nested and documentation comments excluded; strings follow parser leaves.

对使用 := 的目标声明，按真实语法节点的位置将声明头、分隔符和证明体分开；声明头包括 theorem、名称及参数，分隔符单列为一个 token。
For := target declarations, actual syntax positions partition the header, separator and proof body; the header includes theorem, name and parameters, with one separate separator token.

内部证明大小统计表达式构造器的出现次数，包括绑定变量的类型，排除元数据包装；这是当前证明体的大小，引用的引理不会在这个局部数值中自动展开。
Internal proof size counts expression-constructor occurrences, including binder types but excluding metadata wrappers; this is the current proof body, without automatically expanding referenced lemmas.

因此局部证明缩短只作描述；净源码账本比较全部非共享模块的 token，并在实验条件中把候选的定义、引理证明、辅助对象和迁移代码各计一次。
Local proof shortening is therefore descriptive; the net source ledger compares every nonshared module and charges candidate definitions, lemma proofs, auxiliary objects and migration code once.

共同基础库在两边相同，从差额中消去；源码成本与内部证明大小分别输出，不混成一个总分。
The common base is identical and cancels from the difference; source cost and internal proof size remain separate rather than forming a composite score.

时间轨迹仅记录编译与验证开销；这些给定证明没有经过自动搜索，不可把验证时间差当成新概念提高求证效率的证据。
Timing traces record compilation and verification overhead only; supplied proofs underwent no automatic search, so verification-time differences are not evidence of improved proof-search efficiency.

## 报告与解释 / Reports and interpretation

报告保存输入与审计器指纹、固定工具链、两边的导入与声明审计、目标身份、源码拆分、证明依赖、成本账本和执行轨迹。
Reports retain input and auditor fingerprints, pinned toolchain, import and declaration audits, goal identity, source splits, proof dependencies, the cost ledger and execution trace.

结果为 verified_reference_comparison 只表示这些源码实际编译、通过审计且完成了这次比较。
verified_reference_comparison means these sources actually compiled, passed the audit and completed this comparison.

包成本使本轮净源码增加仍是有效结果；一条开发任务既不能决定该思想的一般数学价值，也不能直接充当强化学习偏好标签。
An increase in net source cost after charging the package is a valid result; one development task determines neither general mathematical value nor a reinforcement-learning preference label.

源码解析、缺少声明范围等证据问题会使本轮被拒绝；它们与证明不成立是不同的诊断原因，失败信息与阶段保留在报告中。
Source parsing and missing declaration-range evidence can reject a run; these differ from invalid proofs, and reports retain the diagnostic and stage.

程序目前提供输入格式、实际 Lean 验证与成本比较；自动生成候选、LLM 迁移 skill、约 20 个任务及预留评价属于下一阶段。
The current interface provides manifests, actual Lean verification and cost comparison; candidate generation, an LLM migration skill, approximately 20 tasks and held-out evaluation are the next stage.

参见 [研究计划](RESEARCH_PLAN.md)、[实验源码](../experiments/hom_kernel/) 与 [验证工作流](../.github/workflows/theory-package.yml)。
See the [research plan](RESEARCH_PLAN.md), [experiment sources](../experiments/hom_kernel/) and [verification workflow](../.github/workflows/theory-package.yml).
