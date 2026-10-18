# 独立上下文求解实验 / Independent-context solving experiment

本轮完成了 20 个新冻结目标、40 个独立求解上下文的配对实验：两边均有 20/20 个 Lean 核验的见证，观察到的源码与表达式成本存在权衡。
This round completes a paired experiment with 20 newly frozen goals and 40 fresh solving contexts: both conditions have 20/20 Lean-verified witnesses, with a trade-off between observed source and expression costs.

这是 MAAM 对动态重述、重证接口的实测；它不把局部压缩等同于数学兴趣，也没有完成预算公平的模型效果实验或强化学习。
This is an empirical check of MAAM's dynamic reformulation/reproving interface; it neither equates local compression with mathematical interest nor completes a generation-budget-controlled model experiment or reinforcement learning.

## 固定了什么 / What was frozen

候选包仍是 M1 的 `hom-kernel-core-v1`，源码逐字节不变；没有根据本轮结果加入单位元、逆元或共轭引理。
The candidate remains M1's byte-identical `hom-kernel-core-v1`; no identity, inverse or conjugation lemmas were added in response to these results.

[任务与协议冻结提交](https://github.com/Love-in-idleness/MAAM/commit/2e44eac5b724f9e1303a37da6ca0e3139ed96e3b) 先于所有求解上下文；其中一次类型标注预检查修复也发生在任何求解器启动前。
The [task/protocol freeze commit](https://github.com/Love-in-idleness/MAAM/commit/2e44eac5b724f9e1303a37da6ca0e3139ed96e3b) predates all solving contexts; its type-annotation preflight correction also occurred before any worker was launched.

| 项目 / Item | 约定 / Convention |
| --- | --- |
| 基础与验证 / Foundation and verifier | 与 M1 相同的最小群基础、Init、公理策略，Lean 4.24.0 / Same minimal group base, Init and axiom policy as M1; Lean 4.24.0 |
| 目标 / Goals | 12 个开发、8 个预留，按推理模式分组；全部在求解前固定 / 12 development and 8 reserved goals grouped by reasoning family; all fixed before solving |
| 题目性质 / Task population | 构造的、彼此相关的已知群论练习，包含先前校准模式的扩展；没有提供参考证明 / Constructed, correlated exercises in known group theory, including extensions of earlier calibration patterns; no reference proofs supplied |
| 求解上下文 / Solving contexts | 每个目标、每个条件单独 `fork_turns=none`；只给当前请求和同一个 skill / A separate `fork_turns=none` context for each goal/condition, supplied only its request and the identical skill |
| 顺序 / Order | 种子 20261018 打乱任务，同题条件交替先后；启动顺序已冻结 / Tasks shuffled with seed 20261018; condition order alternates by pair; launch order frozen |
| 停止规则 / Stopping | 每边每题最多 3 次提交，首次 verified 即停止；不在成功后继续压缩 / Up to 3 submissions per goal/condition, stopping at first verified witness; no post-success compression |
| 验证预算 / Verification budget | 32,768 字节证明项、200,000 心跳、单命令 60 秒、单次 180 秒 / 32,768 proof bytes, 200,000 heartbeats, 60 seconds per command, 180 seconds per attempt |
| 未取得的条件 / Unavailable controls | 精确模型修订、采样设置、生成 token 和隐含推理用量 / Exact model revision, sampling settings, generation tokens and hidden reasoning usage |

最后一项始终记为未知；相同 solver-id、提交上限和 Lean 预算不能替代相同且可计量的生成预算。
The last row remains unknown: matching solver IDs, submission caps and Lean budgets cannot substitute for equal, metered generation budgets.

上下文边界由控制器实际以新上下文调用和明确指令建立，未实施操作系统文件访问隔离，也不是签名的模型生成证明。
The controller established context boundaries through actual fresh-context calls and explicit instructions; it did not enforce OS file-access isolation or create signed attestations of model generation.

## 测得的结果 / Observed results

| 指标 / Measure | baseline | treatment |
| --- | ---: | ---: |
| 已核验目标 / Verified goals | 20/20 | 20/20 |
| 完整证明模块源码 token / Full proof-module source tokens | 2632 | 2939 |
| 候选包源码，计一次 / Candidate source, charged once | 0 | 312 |
| 源码总成本 / Total source cost | 2632 | 3251 |
| 证明模块完整表达式节点 / Complete proof-module expression nodes | 29006 | 18795 |
| 候选包完整表达式，计一次 / Complete candidate expressions, charged once | 0 | 4341 |
| 表达式总成本 / Total expression cost | 29006 | 23136 |

完整表达式计入所有收费声明的类型和值，包括生成辅助声明；共享基础与目标抵消，常量不展开内联。
Complete expression cost includes the types and values of every charged declaration, including generated auxiliaries; shared foundations/goals cancel, and constants are not inlined.

观察到的见证在这两个成本维度上不可比：候选侧源码多 619 token，表达式少 5870 节点；这不是全局最短证明，也不是候选包必然带来同样改变的因果估计。
The observed witnesses are incomparable on these two costs: treatment uses 619 more source tokens and 5,870 fewer expression nodes; these are neither globally shortest proofs nor a causal estimate that the package necessarily produces the same change.

候选侧 12/20 份证明的声明依赖实际到达包内声明，其中 9 份到达核乘法引理；其余 8 份直接证明。声明依赖会包含表示桥接中用到的结构与类型。
In treatment, declaration dependencies reach package declarations in 12/20 proofs, including the kernel multiplication lemma in nine; the remaining eight prove directly. These dependencies include structures and types used in representation bridges.

每题的下表只列证明模块成本，整包在上方合计中统一计一次；不能把每题引用引理看成引理免费。
The per-task table below lists proof-module costs only; the package is charged once in the totals above, so a per-task lemma reference does not make that lemma free.

| 任务 / Task | baseline 源码 / Source | treatment 源码 / Source | baseline 表达式 / Expr | treatment 表达式 / Expr | 使用候选 / Uses package |
| --- | ---: | ---: | ---: | ---: | --- |
| d01 | 45 | 79 | 884 | 209 | 是 / yes |
| d02 | 50 | 68 | 1898 | 529 | 是 / yes |
| d03 | 106 | 117 | 423 | 479 | 是 / yes |
| d04 | 38 | 40 | 922 | 922 | 否 / no |
| d05 | 178 | 158 | 907 | 706 | 否 / no |
| d06 | 362 | 363 | 2418 | 2176 | 否 / no |
| d07 | 56 | 58 | 2908 | 495 | 是 / yes |
| d08 | 150 | 148 | 1574 | 1570 | 否 / no |
| d09 | 61 | 99 | 916 | 849 | 是 / yes |
| d10 | 53 | 142 | 760 | 465 | 是 / yes |
| d11 | 66 | 57 | 474 | 237 | 是 / yes |
| d12 | 141 | 78 | 2653 | 2001 | 是 / yes |
| r01 | 42 | 129 | 842 | 465 | 是 / yes |
| r02 | 450 | 463 | 2337 | 1987 | 否 / no |
| r03 | 58 | 58 | 2882 | 629 | 是 / yes |
| r04 | 84 | 86 | 1122 | 1122 | 否 / no |
| r05 | 74 | 53 | 750 | 144 | 是 / yes |
| r06 | 97 | 101 | 764 | 247 | 是 / yes |
| r07 | 488 | 607 | 2658 | 2649 | 否 / no |
| r08 | 33 | 35 | 914 | 914 | 否 / no |

## 保留失败与重放 / Retained failures and replay

[干净 Lean CI 回放](https://github.com/Love-in-idleness/MAAM/actions/runs/39121421850) 已通过全部 46 次提交记录匹配及 40 份已核验见证的完整声明计量；110 项 Python 测试也通过，下载产物的 SHA-256 与 GitHub 收据一致。
The [clean Lean CI replay](https://github.com/Love-in-idleness/MAAM/actions/runs/39121421850) passed all 46 submission-record matches and complete inventories for the 40 verified witnesses; all 110 Python tests also passed, and the downloaded artifact's SHA-256 matches GitHub's receipt.

原始记录共 46 次提交：40 次完成核验，另有 6 次在审计阶段因控制器 PATH 缺少 lean 子进程而失败；这些六次的证明编译已经成功，修复 PATH 后，原求解上下文以相同证明重新提交并通过。六次失败仍然占用预算，没有删除或改写。
The original run has 46 submissions: 40 completed verification and six failed during audit because the controller PATH lacked the lean child executable. Those six proofs had compiled; after fixing PATH, their original contexts resubmitted unchanged proofs successfully. All six failures still consume budget and remain unaltered.

预先冻结的是输入、提示词与实验流程；Python 控制器的记录与导出功能在本轮实施过程中完善。原始会话的 `code_commit` 由控制器手动设为输入冻结提交，用于标记该冻结，而非声称全部控制器实现已在该提交中；核验器文件指纹与最终实现/重放提交另列保留。
Inputs, prompts and the experimental procedure were frozen beforehand; Python controller recording/export features were developed during this round. The controller manually set the original sessions' code_commit to the input-freeze commit to identify that freeze, not to attest that the entire controller implementation existed there; verifier file fingerprints and the final implementation/replay commit are retained separately.

本地主机另需将 `/proc/<own-pid>/exe` 的 readlink 调用兼容为 `/proc/self/exe`；Lean 内核与库未改动，兼容源码及官方工具链归档指纹保存在运行记录中。干净 CI 重放不使用这项兼容。
The local host additionally needed readlink compatibility from `/proc/<own-pid>/exe` to `/proc/self/exe`; Lean's kernel and libraries were unchanged, and the compatibility source and official toolchain archive fingerprint are retained in the run record. Clean CI replay uses no compatibility shim.

[results/independent](../results/independent/) 持久保存两边完整会话、逐字节的原始提交、请求、实际提示词、上下文标识、反馈、证明源码、审计与计量的完整命令日志，不依赖临时 CI 产物才能重建原始记录。
[results/independent](../results/independent/) durably stores both complete sessions, byte-exact original submissions, requests, actual prompts, context identifiers, feedback, proof sources and complete audit/inventory command logs; reconstructing the original record does not depend on temporary CI artifacts.

```bash
# 不需要 Lean：从完整原始记录重算账本与比较。
# No Lean needed: recompute accounting/comparison from complete original records.
python scripts/verify_independent_results.py
python scripts/verify_results.py

# 先安装并预热 Lean 4.24.0；重查输出，不重新调用 LLM。
# Install and warm Lean 4.24.0 first; recheck outputs without rerunning LLM generation.
python scripts/check_independent.py --output data/independent-replay
```

在健康环境重放时，六个基础设施失败对应的同字节证明应通过审计；不要求人为重现 PATH 配置故障，原始故障仍保留在档案中。
In a healthy replay environment, the byte-identical proofs behind the six infrastructure failures must pass audit; replay does not artificially recreate the PATH fault, and the original failures remain archived.

本轮独立生成的控制器入口是 `scripts/control_independent.py` 的 prepare/register/verify/measure/export；它不自动调用供应商模型，也不假装计量外部生成成本。新的任务或候选必须有新协议、冻结提交和会话。
Controller entry points for this study are prepare/register/verify/measure/export in `scripts/control_independent.py`; they neither call a model provider automatically nor pretend to meter external generation costs. New goals or candidates require a new protocol, freeze commit and sessions.

## 下一步与验收边界 / Next steps and acceptance boundary

本轮为 M2 增加了完整的独立上下文求解证据，但预算公平的模型效果验收仍未完成；`held_out_evaluation`、`generation_budget_verified`、`training_eligible` 和 `fair_model_performance_claim` 均为 false。
This round adds complete fresh-context solving evidence to M2, while generation-budget-controlled model-effectiveness acceptance remains unfinished; held_out_evaluation, generation_budget_verified, training_eligible and fair_model_performance_claim all remain false.

同态单位元、逆元和核群结构是下一版理论包的开发候选。本轮 20 题公开后都应作为开发/校准材料；最终版本比较需另起新的冻结任务集，不能依据这些结果修补 v1 后继续称为同一预留评价。
Identity preservation, inverse preservation and a group structure on the kernel are development candidates for the next package version. After publication, all 20 tasks here are development/calibration material; final version comparisons require a fresh frozen task set, rather than patching v1 from these results and retaining the same held-out claim.

随后按 M3 增加有父版本和资源账本的多轮探索，最后再接入 M4 的训练与另一套任务上的训练前后比较；当前数据不直接生成强化学习偏好标签。
Next, M3 adds multi-round exploration with parent versions and resource ledgers, followed by M4 training and pre/post-training comparison on another task set; current data does not directly produce RL preference labels.
