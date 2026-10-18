# 冻结任务与证明迁移 / Frozen tasks and proof migration

M2 的第一步是让 LLM 提交真正回到原目标的证明，并留下可核查的尝试记录。
The first M2 step lets an LLM submit proofs of the original goals and leaves inspectable attempt records.

`maam/migration.py` 在不改动 M1 审计器的前提下提供这一协议；它不绑定模型供应商，也不预设标量奖励。
`maam/migration.py` supplies this protocol without changing the M1 auditor; it assumes neither a model provider nor a scalar reward.

## 任务集 / Task suite

`experiments/hom_kernel_migration/suite.json` 冻结了基础库、候选包、每个目标和验证预算的 SHA-256。
`experiments/hom_kernel_migration/suite.json` freezes SHA-256 fingerprints for the foundation, candidate package, individual goals and verification budgets.

候选与 M1 中的同态／核包逐字节相同，先于本轮任务集冻结；没有为了预留任务补充引理。
The candidate is byte-identical to M1's homomorphism/kernel package and predates this suite; no lemmas were added to fit reserved tasks.

| 划分 / Split | 任务 / Tasks | 推理模式 / Reasoning families |
| --- | --- | --- |
| 开发 / Development | d01–d12 | 有限乘积的恒等元纤维闭合、中性像、输入输出搬运、交集 / Finite identity-fibre products, neutral images, input/output transport and intersections |
| 预留 / Reserved | r01–r08 | 后复合、谓词拉回、等化子、递归乘积 / Postcomposition, predicate pullbacks, equalizers and recursive products |

这些是构造的校准任务，具有相关性，不是 20 个独立的数学发现样本。
These are constructed, correlated calibration tasks, not 20 independent samples of mathematical discovery.

任务与参考证明都公开，当前报告始终设置 `held_out_evaluation=false` 和 `training_eligible=false`。
Tasks and reference proofs are public; current reports always set `held_out_evaluation=false` and `training_eligible=false`.

## 运行一次迁移 / Run a migration

先安装并预热 Lean 4.24.0，再为两边建立不同的目录；验证计时不应被首次工具链下载消耗。
Install and warm Lean 4.24.0 first, then create separate directories for the two conditions; initial toolchain downloads should not consume verification time.

```bash
python -m maam migration-start \
  --suite experiments/hom_kernel_migration/suite.json \
  --session data/baseline --condition baseline --solver-id model-version
python -m maam migration-start \
  --suite experiments/hom_kernel_migration/suite.json \
  --session data/treatment --condition treatment --solver-id model-version
python -m maam migration-request --session data/treatment \
  --task d02 --output request.json
```

请求只包含当前目标、该条件可用的源代码和固定预算，不包含另一条件的证明或其他任务的目标。
A request contains only the current goal, sources available in that condition and the fixed budget; it contains neither opposite-condition proofs nor other task goals.

把请求和 `skills/evaluate-theory-package` 交给新的求解上下文；控制器应保管完整会话目录。
Give the request and `skills/evaluate-theory-package` to a fresh solving context; keep the complete session directory with the controller.

求解器产出证明项和表示桥接说明，再用 skill 的打包脚本生成提交。
The solver produces a proof term and a representation-bridge explanation, then uses the skill's packager to create a submission.

```bash
python skills/evaluate-theory-package/scripts/pack_submission.py \
  --request request.json --proof proof.lean --bridge bridge.txt \
  --output submission.json
python -m maam migration-submit --session data/treatment \
  --submission submission.json --output attempt-01.json
python -m maam migration-report --session data/treatment --output treatment-report.json
python -m maam migration-compare --baseline data/baseline \
  --treatment data/treatment --output comparison.json
```

`proof.lean` 只包含 `:=` 后的项；声明、目标和 imports 由控制器生成，额外提交字段不能更改它们。
`proof.lean` contains only the term after `:=`; the controller generates the declaration, goal and imports, and extra submission fields cannot change them.

需要辅助结果时，在证明项内引入局部引理，并让完整源码计费。
When auxiliary results are needed, introduce local lemmas inside the proof term and charge their complete source.

## 实际约束与证据 / Enforced constraints and evidence

- 两边每个任务最多 3 次提交，每次证明项最多 32,768 UTF-8 字节；每个 Lean 命令最多 60 秒，每次验证最多 180 秒，心跳上限为 200,000。
  Both conditions allow at most 3 submissions per task and 32,768 UTF-8 bytes per proof term; each Lean command has a 60-second limit, each verification a 180-second limit, and the heartbeat limit is 200,000.
- 每次验证都从冻结源码重新编译；baseline 没有候选模块，treatment 增加整个候选包；两边使用同一 Init 与标准核心公理策略。
  Each verification recompiles frozen sources; baseline lacks candidate modules, treatment adds the whole candidate, and both use the same Init and standard-core axiom policy.
- 审计原目标的定义相等、所有本地声明的依赖、禁用公理和实际导入模块；`sorry`、额外公理、目标变化和 baseline 中的候选调用不能成为有效证据。
  Audit definitional equality with the original goal, dependencies of all local declarations, forbidden axioms and actual imported modules; `sorry`, extra axioms, changed goals and candidate calls in baseline cannot become valid evidence.
- 先写独立预约记录，再启动验证；失败、中断以及丢失的尝试目录仍然消耗名额，不能通过删除目录恢复预算。
  Write a separate reservation before verification; failures, interruptions and missing attempt directories still consume slots, so deleting a directory cannot restore the budget.
- 保留原始提交、生成的证明源码、审计结果、每个命令完整的 stdout/stderr 及其指纹；结果为 `verified`、`rejected` 或 `inconclusive`，未完成的预约为 `incomplete`。
  Retain original submissions, generated proof source, audits, full command stdout/stderr and their fingerprints; outcomes are `verified`, `rejected` or `inconclusive`, with unfinished reservations marked `incomplete`.

预算目前约束提交与 Lean 验证，不能独立计量外部模型的生成 token、模型版本、采样设置和隐含推理成本。
Budgets currently constrain submissions and Lean verification; they do not independently meter an external model's generation tokens, version, sampling settings or hidden reasoning costs.

控制器需要额外记录这些条件并控制求解上下文；相同的 `solver-id` 本身不是公平模型实验的证明。
The controller must record those conditions and control solver contexts; an identical `solver-id` alone does not establish a fair model experiment.

记录是带校验和的本地文件，不是签名证明；请求隔离也不是操作系统的访问控制，Lean 元程序仍可执行代码。
Records are checksummed local files rather than signed attestations; request isolation is not OS access control, and Lean metaprograms can execute code.

## 如何解释结果 / Interpret results

覆盖范围按已证明目标的集合比较，允许相同、包含和不可比；未求解表示预算内尚未观察到证明。
Compare coverage as sets of verified goals, allowing equality, inclusion and incomparability; unsolved means no proof was observed within the budget.

源码成本只在两边都求解的目标上比较，采用预算内观察到的最小完整证明模块，加上整个候选包一次；共享基础库和目标声明抵消。
Compare source costs only on commonly solved goals, using the smallest observed complete proof module within budget plus the whole candidate once; shared foundation and goal statements cancel.

如果没有共同已解任务，成本改善为 `null`，不把缺失结果当作零成本成功。
If no task is solved in both conditions, cost improvement is `null`; missing results are not treated as zero-cost successes.

局部证明体和表达式大小另行报告；引用引理并不意味着引理本身免费，也不表示找到了最短证明。
Report local proof-body and expression sizes separately; referencing a lemma neither makes the lemma free nor establishes a shortest proof.

## 当前验收与后续工作 / Validation and next work

2026-10-18 的 [Lean 工作流](https://github.com/Love-in-idleness/MAAM/actions/runs/39099496688) 已通过 40/40 份参考证明、2/2 份独立 skill 工作上下文的提交和 6/6 项错误输入检查；本地 80 项 Python 测试也通过。
The 2026-10-18 [Lean workflow](https://github.com/Love-in-idleness/MAAM/actions/runs/39099496688) passed 40/40 reference proofs, 2/2 submissions from fresh skill-worker contexts and 6/6 invalid-input checks; all 80 local Python tests also passed.

| 已验证轨迹 / Verified traces | baseline 源码 token / Baseline source tokens | treatment 含整包 / Treatment including package | 净节省 / Net saving |
| --- | ---: | ---: | ---: |
| 20 个参考任务 / 20 reference tasks | 904 | 1426 | −522 |
| d02 的独立 skill 求解 / Fresh skill workers on d02 | 34 | 353 | −319 |

两行都将固定候选包的 312 个源码 token 计费一次；第二行只是一对开发任务提交，不能据此估计模型的整体表现。
Both rows charge the fixed candidate's 312 source tokens once; the second row is only one paired development-task submission and cannot estimate overall model performance.

这些轨迹尚未显示净源码压缩收益；报告同时保留局部证明体与表达式大小，以免把不同成本口径强行合成一个排序。
These traces have not shown a net source-compression gain; reports also retain local proof-body and expression sizes rather than forcing different cost conventions into one ranking.

校验过的报告与工作流收据见 [results/migration](../results/migration/)；`python scripts/verify_results.py` 可重算账本并检查所有归档指纹，真实 Lean 重放由独立工作流完成。
Verified reports and the workflow receipt are in [results/migration](../results/migration/); `python scripts/verify_results.py` replays accounting and checks archived fingerprints, while a separate workflow performs actual Lean replay.

完整命令日志与各次尝试保存在保留 30 天的 CI 产物中，之后可用下述命令从已提交的证明源码重新生成。
Complete command logs and attempts are retained in CI artifacts for 30 days and can subsequently be regenerated from committed proof sources with the command below.

`python scripts/check_migration.py --output data/migration` 运行 40 份公开参考证明、实际错误输入检查，以及两个独立 skill 求解器输出的重放；详细结果以 CI 产物为准。
`python scripts/check_migration.py --output data/migration` runs 40 public reference proofs, actual invalid-input checks and replays of two fresh skill-worker outputs; CI artifacts provide the detailed results.

独立求解器各自只看到了 d02 的单任务请求与 skill，原始输入输出保存在 `skill_forward.json`；CI 用相同证明项重新绑定请求并检查，不能将它扩展解释为 20 个任务的自动求解表现。
Each fresh worker saw only a task-local d02 request and the skill, with original inputs/outputs retained in `skill_forward.json`; CI rebinds and checks the same proof terms, which does not establish autonomous performance on all 20 tasks.

新的 [独立上下文实验](INDEPENDENT_EXPERIMENT.md) 已在另一组 20 个冻结目标上运行 40 个全新求解上下文，两边均通过全部目标；40 份见证和 6 次基础设施失败的完整记录已保存，候选始终不变。
The new [independent-context experiment](INDEPENDENT_EXPERIMENT.md) ran 40 fresh solving contexts on another 20 frozen goals, with both conditions passing every goal; complete records of 40 verified witnesses and six infrastructure failures are retained, with the candidate unchanged throughout.

该轮记录了冻结顺序、实际提示词和上下文标识，但精确模型版本、采样参数和生成 token 未取得；因此 M2 的生成预算公平性验收仍未完成，不能直接导出训练偏好。整包校准消融见 [包消融](PACKAGE_ABLATIONS.md)，下一步是 M3 多轮版本与新的冻结评价任务。
That round records frozen order, actual prompts and context identifiers, but exact model revision, sampling and generation tokens were unavailable; M2 generation-budget fairness therefore remains unaccepted and no training preferences are exported directly. See [package ablations](PACKAGE_ABLATIONS.md) for calibration controls; next are M3 multi-round versions and fresh frozen evaluation tasks.

引入新命题或对象时，应把定义、表示桥接、性质和推论一起放入候选清单，先在开发集修改，再冻结新版本；不能依据预留集反馈修改同一版本。
When introducing a new proposition or object, include its definitions, representation bridges, properties and corollaries in the candidate manifest, revise on development tasks, then freeze a new version; reserved feedback must not alter that version.
