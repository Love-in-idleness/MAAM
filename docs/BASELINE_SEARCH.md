# 小范围旧工具搜索流程 / Bounded old-tool search workflow

本工具把上一轮的基线清单接成可执行的记录流程：冻结策略，逐项给出原证和旧工具，接收候选或保留决定，调用既有检查器，再从记录重建结果。
The workflow records supplied local responses; it makes no model calls, changes no existing definitions and introduces no new theory package.

## 范围与规则 / Scope and rules

输入限于一到四个已有开发目标、最多三个声明的方法和最多四轮完整检查，策略、目标顺序、知识与计量规则在开始时固定。
Requests follow a fixed sweep/method/task schedule and bind the policy, current incumbent certificate and inner baseline request; stale or cross-task responses are rejected.

每份请求只提供当前目标、其基础库源码和当前原证，不提供其他目标的证明或候选理论包；同一原证可以直接保留，无须重新证明。
A response either supplies a candidate proof or records a reason to retain the incumbent, preserving the original certificate and import context.

候选经过隔离 Lean 核验，只有完整证明模块源码严格更短才更新选择，等长、更长或被拒绝的候选都不覆盖原证；失败、中断和全部资源状态继续保留。
Each candidate is reserved before verification, and each sweep/method has its own baseline session so the frozen inner attempt limits remain unchanged.

任何改善都会重置连续无改善轮数，只有之后覆盖全部声明方法与目标的完整、无异常轮次才能满足停止规则，缺少响应或发生拒绝的轮次不能充当干净的无改善确认。
An interrupted reservation or inconclusive verification stops progress without automatic retry; finishing a policy's request budget can still leave the no-improvement requirement unmet.

流程另有先于检查写入的名额日志，删除一次保留决定的预约与响应也不能恢复名额；日志缺失或写入后中断时保守停止，而不自动重试。
This is a local integrity and interruption guard, not a signed attestation against an operator rewriting the complete history.

## 本地使用 / Local use

策略是固定 JSON，例如一项旧工具缩短方法、最多三轮、改善后需要两轮完整无改善记录。
Method names and instructions describe the intended search; they do not independently certify that a model exhausted all available tools.

仓库提供同口径的[首版小范围策略](../experiments/baseline_search_v1/policy.json)，仅规定本地旧工具缩短，未授权或执行任何供应商调用。
The versioned policy fixes three sweeps and two clean confirmations after improvement; all solver-generation evidence remains outside this supplied-local controller.

```json
{
  "schema_version": 1,
  "evidence_mode": "supplied_local",
  "max_sweeps": 3,
  "stable_sweeps": 2,
  "methods": [
    {
      "name": "existing_tool_shortening",
      "instructions": "Search for a shorter proof using only the supplied existing sources; retain the checked incumbent when no improvement is found."
    }
  ]
}
```

将策略保存为新文件后，用已重放的基线清单准备新目录，请求和提交文件也应保留为新文件。
Preparation verifies the inventory against its original certificates and freezes source, policy and controller fingerprints before accepting responses.

```bash
.venv/bin/python scripts/control_baseline_search.py prepare \
  --inventory data/baseline-inventory-20261020.json \
  --policy /path/to/policy.json --root data/baseline-search-NEW

.venv/bin/python scripts/control_baseline_search.py request \
  --root data/baseline-search-NEW --output data/baseline-request-NEW.json

.venv/bin/python scripts/control_baseline_search.py submit \
  --root data/baseline-search-NEW --submission /path/to/response.json

.venv/bin/python scripts/control_baseline_search.py status \
  --root data/baseline-search-NEW
```

保留原证的响应格式如下，指纹应复制当前请求的 `request_sha256`。
A candidate response instead uses `action: "candidate"` with `proof` and `bridge`; it does not choose its own task, imports or budget.

```json
{
  "action": "retain",
  "request_sha256": "CURRENT_REQUEST_HASH",
  "reason": "No shorter proof found in this declared local attempt."
}
```

## 状态与证据边界 / Status and evidence limits

| 状态 / Status | 含义 / Meaning |
| --- | --- |
| `in_progress` | 声明流程尚未完成 / Requests remain |
| `declared_search_finished` | 声明流程满足完整无改善轮数 / Declared clean-sweep rule met |
| `sweep_budget_exhausted` | 轮次用尽但未满足停止条件 / Sweep limit reached without clean-sweep completion |
| `interrupted_or_inconclusive` | 有未完成预约或未知核验结果 / Interrupted or inconclusive evidence |

命令对中断、未知核验或轮次耗尽但未完成确认返回非零状态，正常读取尚在进行的流程不表示已通过基线验收。
An operationally successful status read is not a certificate of sufficient baseline optimization or completed method execution.

完成有限的响应流程，不等于原工具已充分利用；当前 `baseline_search_complete`、`package_attribution_ready`、`model_search_verified` 与 `globally_shortest` 均保持为假，定义优化也没有在这个版本执行。
Supplied local generation usage remains unknown, and the controller's provider-call count is zero because it has no API transport; existing historical costs stay in their original ledgers.

新增[确定性局部改写执行器](BASELINE_METHODS.md)已接入两种声明方法的实际执行记录，计量求解器、定义优化与语义兼容性验收仍待完善。
Even that evidence would establish only a bounded search result, without proving a globally shortest Lean proof or a general causal contribution from a new concept.

## 工具验收 / Workflow check

下列检查使用一个极小人工目标和事先提供的证明，实际调用隔离 Lean，覆盖接受更短候选、拒绝更长替换、直接保留以及保留被拒绝候选的现场。
The synthetic padding fixture tests control behavior; its shortening is not evidence of model performance or mathematical package value.

```bash
.venv/bin/python scripts/check_baseline_search.py \
  --output data/baseline-search-smoke-NEW
```

相关理论与分账原则见[基线准备](BASELINE_PREPARATION.md)，该流程不会修改旧实验、原证、理论包或既有检查器。
Existing archived experiments remain separately replayable, with no relabeling of their historical outcomes.

2026-10-20 的最终本地验收保存在 `data/baseline-search-smoke-20261020-v2/`：四次真实隔离 Lean 检查中三次有效证明通过、一次 `sorry` 候选按设计被拒绝，流程完成三轮且改善后有两轮完整无改善记录。
All 281 unit tests pass, the final reports replay identically, and CLI requests preserve terminal success or failure status; earlier verification records and their runtime sources are retained separately.

四个实际开发目标另准备于 `data/baseline-search-development-prepared-20261020-v2/`，沿用已知原证 990 个源码 token，当前响应数和供应商调用均为零，尚未开始实际缩短搜索。
Its frozen policy is the versioned local-only policy above; preparing and exporting the first request does not establish baseline sufficiency, execute a search method or introduce another theory package.

随后在独立的两题目录 `data/baseline-method-pilot-20261020-v1/` 实际执行四次确定性扫描，两份候选通过 Lean，其中一份更短、另一份更长，按原策略得到 370→367 token，原四题目录保持不变。
This executes the finite declared methods without certifying sufficient preparation; the one-sweep limit leaves the underlying search at `sweep_budget_exhausted`, with all readiness flags false.

后续[有限确认工具](BASELINE_STABILITY.md)通过组合独立单轮执行、严格继承所选证书并记录外层轮次预算，完成两次无改善确认；旧单轮记录的状态不改写，全面基线与包归因标志仍为假。
The outer controller adds a narrowly scoped completion flag instead of changing the original search protocol or claiming all existing tools have been exhausted.
