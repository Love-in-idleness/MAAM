# 理论包版本与后续复用 / Package versions and later reuse

本轮把不变的 `hom-kernel-core-v1` 作为父版本，在新模块 `Extension` 中构造 `hom-kernel-group-v2`。
This round preserves `hom-kernel-core-v1` as the parent and constructs `hom-kernel-group-v2` in a new `Extension` module.

v2 包括左消去、右逆元、单位元的逆、同态保持单位元与逆元、核包含单位元且对逆运算封闭，以及核上的完整群结构。
V2 includes left cancellation, right inverses, the inverse of the identity, homomorphism preservation of identity and inverses, kernel closure under identity/inversion, and a complete group structure on the kernel.

这些都是同一个最小群基础上的已证扩展；基础只给左逆元公理，新增结果没有成为额外公理。
These are proved extensions of the same minimal group foundation, which assumes only left inverses; the new results are not additional axioms.

## 本轮协议 / Protocol

`experiments/hom_kernel_evolution/study.json` 冻结三个阶段：已有 v1、由控制器构造 v2、在后续任务中比较基础库/v1/v2。
`experiments/hom_kernel_evolution/study.json` freezes three stages: the existing v1, controller-authored construction of v2, and downstream comparison of the base library, v1 and v2.

四个预先选定的校准任务分别要求：核上的群结构、映射到核的构造、两个核交集上的群结构，以及带单位元/乘法/逆元的递归表达式闭包。
Four preselected calibration goals require a group structure on the kernel, a map into the kernel, a group structure on an intersection of kernels, and closure of recursive expressions with identity, multiplication and inverses.

每个目标与条件各用一个全新求解上下文，共 12 个；只提供单任务请求和同一 skill，每题最多三次提交，首次核验成功即停止。
Each goal/condition gets a fresh solving context, twelve in total, supplied only its request and the same skill; each allows at most three submissions and stops at the first verified witness.

候选源码、目标、验证器实现和提示词在启动求解前一同提交冻结；请求隔离是控制器流程约束，未实施操作系统文件隔离。
Candidate source, goals, verifier implementation and prompts are committed together before solving starts; request isolation is a controller procedure, not OS file isolation.

这是一轮人为选择扩展方向与应用任务的复用校准，并未证明自动发现新思想或严格预留集上的一般效果。
This is reuse calibration with a deliberately selected extension and application tasks; it does not establish autonomous discovery or general effectiveness on a strict held-out set.

## 版本与成本 / Versions and costs

子版本必须保留父版本的模块字节与声明，并在更晚的阶段引入；版本环、父模块替换和条件间任务变化均被拒绝。
A child must preserve its parent's module bytes and declarations and be introduced in a later stage; cycles, parent-module replacement and task changes across conditions are rejected.

每项比较给完整候选包计费一次；v2 的完整成本包括 `Candidate` 与 `Extension`，增量成本只计算新模块，不能重复收取已继承模块。
Each comparison charges the whole candidate once; v2 includes both `Candidate` and `Extension`, while incremental cost charges only new modules without double-counting inheritance.

源码 token 与完整声明表达式节点分开报告，构造编译、所有成功和失败的验证及计量时间另列；未取得的模型版本、采样和生成 token 保留为 null。
Source tokens and complete declaration-expression nodes are reported separately, with construction compilation and all successful/failed verification and inventory times reported separately; unavailable model revision, sampling and generation tokens remain null.

后续复用记录从 `Submission.solve` 出发的实际依赖路径，并连接到声明所在模块及其引入版本；路径可能经过类型和桥接声明，表示可核查的使用关系，不能单独证明因果收益。
Later-use records follow actual dependency paths from `Submission.solve` to each declaration's module and introducing version; paths may pass through types and bridges, demonstrating auditable use without independently establishing causal benefit.

## 运行 / Running

```bash
python scripts/control_evolution.py prepare --root /tmp/maam-evolution-run \
  --workers /tmp/maam-evolution-workers --freeze-commit FULL_COMMIT_SHA
# Give each frozen prompt to a fresh task-local worker and register its context.
python scripts/control_evolution.py register --root /tmp/maam-evolution-run \
  --worker e01 --agent-id ACTUAL_CONTEXT_ID
python scripts/control_evolution.py verify --root /tmp/maam-evolution-run --worker e01 --attempt 1
python scripts/control_evolution.py measure --root /tmp/maam-evolution-run
python scripts/control_evolution.py export --root /tmp/maam-evolution-run --output results/evolution

# Once the complete archive exists:
python scripts/verify_evolution_results.py
python scripts/check_evolution.py --output /tmp/maam-evolution-replay
```

控制器不自动调用供应商模型，生成计量和自动多轮候选搜索仍待实现；CI 重新检查归档证明，不重新进行 LLM 生成。
The controller does not call a model provider automatically; generation metering and automatic multi-round candidate search remain unimplemented, and CI rechecks archived proofs without rerunning LLM generation.

中断后的预约仍占用预算，未完成的提交不会导出为完整实验；应保留现场并诊断，不能删除记录后重试。
Reservations still consume budget after interruptions, and unfinished submissions cannot be exported as a completed experiment; preserve and diagnose the records rather than deleting them to retry.

## 首次运行中断与替代实验 / Interrupted run and replacement cohort

首次协议与实现已在 `22b8e9b` 冻结；恢复会话时，临时控制器和工作目录已不存在，原始证明字节与核验结果不可恢复，现存工具记录汇总在 `interrupted-run-01.json`。
The first protocol and implementation were frozen at `22b8e9b`; on session resumption the temporary controller and worker directories were absent, leaving original proof bytes and verification results unrecoverable; surviving tool records are summarised in `interrupted-run-01.json`.

这些结果保持未知，不计为成功或零成本，也不恢复原运行的尝试名额；`study-recovery-01.json` 明确标识一次独立的替代运行，两次运行合计的模型搜索成本仍未知。
Those outcomes remain unknown, count as neither successes nor zero costs, and do not restore the original run's attempt slots; `study-recovery-01.json` explicitly identifies a separate replacement cohort, with aggregate model-search cost across both runs still unknown.

替代运行将工作者输出放在工作区，并为控制器操作增加 `--checkpoints data/evolution-checkpoints`，在每次操作前后保存完整且不可覆盖的检查点；检查点恢复保留会话身份、提交预约与失败记录。
The replacement keeps worker outputs in the workspace and adds `--checkpoints data/evolution-checkpoints` to controller operations, saving complete, non-overwriting checkpoints before and after each operation; recovery preserves session identities, reservations and failures.

操作进行中若再次丢失临时目录，只能恢复已实际保存的检查点；不能把未观察到完成的操作假定为从未发生。
If temporary storage is lost during an operation, only checkpoints actually saved can be recovered; an operation whose completion was unobserved cannot be assumed never to have happened.

## 替代实验的实测结果 / Measured replacement cohort

替代实验以 `39e3048` 冻结输入和核验器；12 个全新任务上下文共提交 13 次，其中 12 份证明通过原目标与依赖审计，基础库的核交集任务首次因表达式遍历上限被拒，第二次修订通过。
The replacement froze its inputs and verifier at `39e3048`; twelve fresh task contexts made thirteen submissions, twelve proofs passed the original-goal and dependency audit, and the baseline intersection task's first attempt hit the expression-traversal limit before its second attempt passed.

每个条件均覆盖四个预选开发任务；下表将完整候选包只计入一次，随后加上四份核验成功的证明，比较的是本轮观察到的证明组合，而不是全局最短证明。
Each condition covers all four preselected development tasks; the table charges its complete candidate package once and adds the four verified proofs, comparing observed proof portfolios rather than globally shortest proofs.

| 条件 / Condition | 成功任务 / Solved | 提交 / Attempts | 整包源码 token / Package source tokens | 整包表达式节点 / Package expression nodes | 合计源码 token / Total source tokens | 合计表达式节点 / Total expression nodes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 基础库 / Baseline | 4/4 | 5 | 0 | 0 | 1985 | 24568 |
| v1 | 4/4 | 4 | 312 | 4341 | 2220 | 59118 |
| v2 | 4/4 | 4 | 1100 | 9157 | 1574 | 55487 |

v2 比 v1 的整包大：继承模块保持 312 个源码 token 与 4341 个表达式节点，新模块另有 788 个 token 与 4816 个节点；但本轮四份证明的合计成本仍在两个口径上低于 v1。
V2 is a larger package than v1: the inherited module remains 312 source tokens and 4,341 expression nodes, while the new module adds 788 tokens and 4,816 nodes; the four observed proofs nevertheless give v2 a lower total in both cost units than v1.

在这组证明与成本口径下，基础库支配 v1；基础库与 v2 不可比，后者节省 411 个源码 token，却增加 30919 个表达式节点。
Under these observed proofs and cost conventions, baseline dominates v1; baseline and v2 are incomparable, as v2 saves 411 source tokens but adds 30,919 expression nodes.

v2 的依赖图在四类任务中都触及新模块的声明；其中核群结构用于核群与映射限制任务，交集与递归词任务使用单位元或逆元的闭包路径。
V2's dependency graphs reach declarations in the new module in all four task families; the kernel-group structure appears in the kernel-group and restriction tasks, while intersection and recursive-word tasks use identity or inverse closure paths.

这些路径包括声明类型和编译器产生的内部证明节点，因此只是可核查的后续使用记录，不能把路径数量当成独立用途、因果收益或数学兴趣分数。
These paths include declaration types and compiler-generated proof nodes, so they record auditable later use, not a count of independent applications, a causal gain, or a mathematical-interest score.

首次中断实验的证明和生成成本未知；替代实验也没有供应商记录的模型修订、采样与生成 token，因而不能验收公平模型比较、严格预留效果、自动发现或强化学习训练标签。
Proofs and generation costs from the interrupted first run remain unknown; the replacement also lacks provider-recorded model revision, sampling and generation tokens, so it cannot certify a fair model comparison, strict held-out effect, autonomous discovery, or reinforcement-learning labels.

完整请求、提示词、13 次提交、反馈、原始命令日志、成本清单、依赖路径及中断说明均保存在 [结果档案](../results/evolution/)；`receipt.json` 区分本地核验与独立 CI 重放状态。
The [result archive](../results/evolution/) preserves requests, prompts, all thirteen submissions and feedback, original command logs, cost inventories, dependency paths and the interruption record; `receipt.json` distinguishes local verification from independent CI replay.

下一步是由统一供应商接口实际调用求解模型并记录版本、采样、生成 token 和预算截止事件，然后冻结未用过的迁移模式，比较同等资源下的新旧理论包；自动构造候选和 M4 学习仍是后续阶段。
Next, a unified provider interface should actually call the solver and record model revision, sampling, generation tokens and budget-stop events, then freeze unused migration patterns to compare packages under matched resources; automatic candidate construction and M4 learning remain later stages.
