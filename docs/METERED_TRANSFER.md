# 冻结的 DeepSeek 对照实验 / Frozen DeepSeek comparison

本协议比较固定基础库与基础库加 `hom-kernel-group-v2`，候选包逐字节沿用早于任务集的版本；四个开发目标与四个预留目标按推理家族划分。
The protocol compares the fixed foundation against that foundation plus `hom-kernel-group-v2`, using four development and four reserved goals split by reasoning family and a candidate that predates them.

任务与来源见 [任务说明](../experiments/metered_transfer_v1/README.md)，机器可读规则见 [protocol.json](../experiments/metered_transfer_v1/protocol.json)。
See the task notes for author exposure, correlated elementary group theory and the limits of judging new reasoning patterns.

## 供应商与限额 / Provider and limits

按用户要求，本轮仅向 `https://api.deepseek.com/responses` 发请求，使用 `deepseek-flash` 与 `reasoning.effort=low`，不读取 OpenAI 密钥，也不在失败时回退供应商。
This round uses only DeepSeek; the [official Responses API](https://api-docs.deepseek.com/api/create-response/) supports the required JSON format, reasoning setting and usage fields.

| 冻结规则 / Frozen rule | 数值 / Value |
| --- | ---: |
| 每题每条件最多调用 / Calls per task and condition | 2 |
| 每次输出上限，含推理 / Output per call, including reasoning | 2,048 tokens |
| 每题每条件累计输出 / Output per task and condition | 4,096 tokens |
| 每次输入预约 / Input reservation per call | 16,384 tokens |
| 整轮生成调用 / Whole-run generation calls | 32 |
| 整轮输入 / Whole-run input | 524,288 tokens |
| 整轮输出 / Whole-run output | 65,536 tokens |
| 整轮含余量的费用估算上限 / Whole-run guarded cost estimate | US$0.10 |

费用按 2026-10-20 核对的 [DeepSeek 高峰未命中缓存价格](https://api-docs.deepseek.com/quick_start/pricing/)保守计：输入每百万 token US$0.30、输出 US$1.20，再乘 1.25 倍余量；缓存优惠和低谷折扣均不用于提高调用名额。
These frozen rates are conservative estimates, not account-wide limits or invoice confirmation; account balances and final charges are not queried by this controller.

DeepSeek 本轮没有接入官方输入计数端点，因此每次预先预约完整输入上限，并对序列化请求字节数留出 2048 字节的模板余量；这不是精确 tokenizer 计数，也不构成对服务器输入 token 数的数学保证。
After each response the controller replays provider usage, stops on an input overrun, and keeps unknown usage charged at its full reservation rather than treating it as zero.

每次发请求前，先检查此前实际已知费用加本次最大预约；整轮费用可能先于其他限额耗尽，未完成的任务对必须报告为不完整。
The global cost ceiling does not guarantee completion of every worst-case call; equal per-task allowances are distinct from equal observed input, output or dollar spending.

## 阶段与记录 / Phases and records

开发阶段完成或耗尽其逐题预算后才能进入预留阶段；候选、目标、配置、实现和隔离器指纹始终不变，查看开发反馈后不能修改同一协议的候选。
The reserved phase is a separate explicit invocation, while the complete schedule and both phases' shared spending pool are frozen before either phase starts.

首次核验成功即停止该题条件；失败、截断和格式错误都保留并计费，未知用量、调用或核验中断、模型不匹配及预算越界会停止整轮，禁止自动重试或删除现场重置名额。
Repairs see only their own task/condition history and diagnostics, with a fresh local reservation bound to the exact current payload.

`snapshot/` 保存原始协议和任务；`budget-reservations/` 保存整轮预约；`input-counts/` 虽保留兼容目录名，但其真实调用记录明确标识为完整输入预算预约；`stages/` 保存两阶段的原始响应、证明和核验记录。
Raw responses are preserved before Lean, and replay recomputes accounting from those bytes; keys, authorization headers and provider HTTP error bodies are never archived.

旧生成器和核验器保持不变，底层 `openai-responses` 求解器前缀及 endpoint 字段只是兼容元数据，底层 scope 仍为 calibration；真实目的地由外层 `plan.json` 与 `deepseek_responses` 收据确定。
The outer report identifies DeepSeek explicitly and never promotes the legacy calibration flags into held-out, exact-revision, model-performance or training claims.

源码成本只比较两边共同成功的目标，并给完整候选包计费一次；局部表达式大小、生成 token 和费用分别报告，不把不同单位相加。
Coverage and costs describe observed attempts, with no claim of globally shortest proofs, representative mathematical performance, autonomous discovery or established effectiveness.

Lean 在既有 Bubblewrap 隔离器内运行，无法读取宿主密钥或联网；它仍可写自身临时证明目录，因此不能将此称为全面防御恶意核验工件篡改。
Local hash seals are integrity checks rather than signed provider attestations, and a model alias does not verify an exact model revision.

## 复现与执行 / Reproduce and run

以下离线命令不读取密钥、不调用供应商，分别核验声明与开发参考证明、以及拒绝后修复的完整控制器流程。
Use a fresh output directory for each check, preserving any previous failures.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_transfer_tasks.py --output data/transfer-tasks-NEW
.venv/bin/python scripts/check_transfer.py --output data/transfer-controller-NEW
.venv/bin/python scripts/verify_results.py
```

源码提交冻结后，下面的 prepare 与 status 命令只在本机创建和读取记录；prepare 要求协议、全部任务和运行实现与所记录 Git 提交逐字节一致。
Preparation makes no paid call and does not include public development reference proofs in the solver snapshots.

```bash
.venv/bin/python scripts/control_transfer.py prepare --root data/transfer-deepseek-NEW
.venv/bin/python scripts/control_transfer.py status --root data/transfer-deepseek-NEW
```

下面两条 run 命令会实际调用 DeepSeek，并共享上述整轮额度；`--key-file` 应指向已授权的、归本人所有且权限为 600 的本地凭据文件。
Run development first, inspect its complete ledger, then invoke reserved without changing the frozen inputs.

```bash
.venv/bin/python scripts/control_transfer.py run --root data/transfer-deepseek-NEW \
  --phase development --key-file /path/to/private-deepseek-key.txt
.venv/bin/python scripts/control_transfer.py run --root data/transfer-deepseek-NEW \
  --phase reserved --key-file /path/to/private-deepseek-key.txt
```

## 开发轮反馈与独立校准 / Development feedback and separate calibration

2026-10-20 首次开发轮完成 16 次真实 DeepSeek 调用，供应商报告 31674 输入与 32768 输出 token，后者全部是推理 token；每次均以输出上限截断，没有产出可提交的证明，四个预留任务尚未调用。
This is evidence that the 2048-token output allowance was inadequate for this configuration, not evidence that the mathematical goals are unsolvable or that the package lacks value.

按冻结高峰价格、不计缓存优惠，费用估算为 US$0.0488238，加入 25% 余量后为 US$0.06102975；16 次失败全部保存在本机 `data/transfer-deepseek-20261020-v1/`，不恢复其调用名额。
The local ledger is complete, but no proof-success or source-cost gain can be claimed from that run, and the account invoice remains unchecked.

另冻结 [开发输出校准 v2](../experiments/metered_transfer_v1/protocol-development-output-v2.json)：仅允许两次调用，因此只会触及首个开发目标的两个条件；每次输出上限改为 8192 token，仍使用 DeepSeek Flash/low，候选与原目标保持不变。
This is a separate, deliberately incomplete development calibration, not a rerun of the reserved evaluation or a continuation with reset allowances.

新校准估算额度最多 US$0.035，加上旧轮已计费用为 US$0.09602975，低于本轮最初 US$0.10 的合计额度；旧失败和两轮合计费用必须一起报告。
The new run's whole-schedule status will stop at its two-call limit; only actual retained witnesses may establish whether this larger allowance produces verifiable output.

独立校准已完成两次真实调用，首个开发目标的基础库与 v2 条件均通过隔离 Lean；供应商报告 3925 输入、5359 输出 token，其中推理占 4717 token，随后按两次调用上限停止，未触及其他目标。
Both actual proofs and their original-goal/dependency audits are retained locally in `data/transfer-deepseek-output-v2-20261020/`; this verifies one development pair, not the complete stage or a reserved evaluation.

两轮合计 18 次调用、35599 输入、38127 输出 token，保守高峰价估算为 US$0.0564321，含 25% 余量为 US$0.070540125；所有失败均计入，低于最初 US$0.10 的合计额度，账户账单未核对。
The combined input/output total is 73726 tokens, with reasoning already included in output and never added a second time.

该单题的完整证明模块源码成本为基础库 150 token、v2 含完整候选包 1267 token，其中整包为 1100 token；本例没有显示净源码收益，不能从证明成功推断候选更有价值。
Next, calibrate the remaining development goals with an explicitly frozen adequate output allowance and a new total budget before admitting the untouched reserved families.

## 剩余开发目标校准 v3 / Remaining development calibration v3

新冻结的 [v3 协议](../experiments/metered_transfer_v1/protocol-development-remaining-v3.json) 只允许六次调用：按 d02、d03、d04 的顺序各运行两个条件，开发顺序末尾的 d01 不会在本轮重新调用；预留任务也不会运行。
It preserves DeepSeek Flash/low, one call per task and condition, an 8192-token output cap, the fixed candidate and the original goal bytes.

本轮新增费用估算上限为含余量的 US$0.12，六次最大预约为 US$0.110592；此前已计 US$0.070540125 继续保留，合计估算上界 US$0.190540125 低于此次 US$0.20 的累计额度。
The previous US$0.10 envelope remains the limit for the earlier round, while this newly authorized work uses its own frozen small-run ceiling and reports all cohorts together.

新顺序交替两条件的先后，但与先前 d01 的单题上下文属于不同协议；合并覆盖只能称为跨校准轮观察，不能标为一次完整公平比较。
An aggregate source ledger charges the same full candidate once across commonly solved development goals, retains each original ledger separately, and never treats failed or unknown generation as free.

### 用户调整后的 v4 / V4 after the user's update

v3 仅完成协议冻结，尚未调用供应商时，用户说明 DeepSeek API 不需要考虑 token；因此实际执行改用新增的 [v4 协议](../experiments/metered_transfer_v1/protocol-development-remaining-v4.json)，不修改 v3 或早先记录。
The active run no longer compresses its generation allowance for token savings; token usage remains part of the research evidence.

v4 保持六次调用、每题每条件一次与原任务顺序，每次给出 32768 token 的宽松输出上限以防异常无限生成；不以 token 消耗多少作为数学收益或选题依据。
Its separate spending guard is US$0.35 including margin, covering all six maximum reservations of US$0.331776; prior guarded costs remain US$0.070540125, so the cumulative upper estimate is US$0.420540125.

两个预留阶段仍不会执行，候选与基础库及目标字节不变；跨轮汇总会保留每轮不同的生成设置，而不声称统一预算的公平比较。
The generous output limit is a reproducible execution setting rather than a tokenizer-based efficiency target or an account-wide spending limit.

## 跨轮离线汇总 / Offline cross-run summary

新增的汇总命令只重放本地记录，不调用模型或 Lean，并保留每轮配置、原始报告、计划指纹和证明来源；同一候选在共同成功目标的源码账本中只计一次。
Unknown usage remains unknown with its full reservation charged, and a missing successful proof never becomes a zero-cost success.

```bash
.venv/bin/python scripts/summarize_transfer.py \
  --run data/transfer-deepseek-20261020-v1 \
  --run data/transfer-deepseek-output-v2-20261020 \
  --run data/transfer-deepseek-remaining-v4-20261020 \
  --ceiling-usd 0.50 --output data/transfer-development-summary-NEW.json
```

每次输出必须使用新文件名，超过合计估算额度时仍保存报告并返回非零状态，不隐藏超支、预留调用或中断。
The summary is explicitly an adaptive development calibration across distinct protocols, with fairness, held-out, exact-revision and training claims kept false.
