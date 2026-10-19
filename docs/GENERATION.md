# 有计量的模型生成 / Metered model generation

`maam/generation.py` 为现有迁移检查器增加真实 OpenAI Responses 调用、逐任务修复和生成用量记录，不改动已归档证据所绑定的评估器。
`maam/generation.py` adds actual OpenAI Responses calls, task-local repair and generation records around the existing migration checker without changing the evaluators bound to archived evidence.

本轮只开放已公开的开发任务校准；它不构成严格预留评价、公平模型性能结论或训练数据验收。
This round supports public development-task calibration only; it does not establish held-out effectiveness, fair model-performance claims or training-data acceptance.

## 准备与运行 / Prepare and run

先激活项目 Python 环境并预热固定的 Lean 4.24.0；驱动器仅使用 Python 标准库，不增加依赖。
Activate the project's Python environment and warm the pinned Lean 4.24.0 toolchain first; the driver uses only the Python standard library and adds no dependencies.

将以下不含凭据的配置保存为 `data/generation-config.json`；模型与推理设置必须显式配置，当前聊天的 GPT-6.1-sol ultra 不会配置 API 调用。
Save the following credential-free configuration as `data/generation-config.json`; configure the model and reasoning explicitly, because the current chat's GPT-6.1-sol ultra setting does not configure API calls.

```json
{
  "model": "gpt-6.1-sol",
  "sampling": {
    "reasoning_effort": "high"
  },
  "budget": {
    "max_calls_per_task": 3,
    "max_output_tokens_per_call": 4096,
    "max_output_tokens_per_task": 8192,
    "request_timeout_seconds": 180
  }
}
```

在仓库根目录执行下面的准备命令，为同一开发任务 `d01` 建立 baseline 和 treatment 两个独立条件；输出目录必须尚不存在。
From the repository root, prepare separate baseline and treatment conditions for the same development task `d01`; the output directory must not already exist.

```bash
python scripts/control_generation.py prepare \
  --suite experiments/hom_kernel_migration/suite.json \
  --config data/generation-config.json \
  --task d01 --root data/generation-d01
python scripts/control_generation.py status --root data/generation-d01
```

真实调用前，先为生成的 Lean 安排独立账户或容器隔离及文件、网络限制，再仅通过控制器进程环境提供 `OPENAI_API_KEY`；不要把密钥粘贴到聊天、命令历史或仓库文件中。
Before live calls, isolate generated Lean in a separate account or container with appropriate file and network restrictions, then provide `OPENAI_API_KEY` only through the controller process environment; never paste the key into chat, shell history or repository files.

当前 Lean 子进程的环境允许列表会移除 API 密钥，但这不是操作系统的文件系统或网络沙箱，不能阻止同一账户下的其他凭据访问。
The Lean subprocess environment allowlist removes the API key, but it is not an OS filesystem or network sandbox and cannot prevent other credential access under the same account.

配置好隔离与进程环境后，以下命令才会实际调用供应商；本轮没有配置密钥，也没有执行真实模型调用。
After configuring isolation and the process environment, the following command makes actual provider calls; no key was configured and no live model call was made in this work round.

```bash
python scripts/control_generation.py run --root data/generation-d01
python scripts/control_generation.py status --root data/generation-d01
```

HTTP 地址固定为 `https://api.openai.com/v1/responses`，请求使用 `store=false`，不自动重试，也不跟随重定向。
HTTP calls use the fixed `https://api.openai.com/v1/responses` endpoint with `store=false`, no automatic retries and no redirects.

每个任务和条件只接收自己的冻结目标、可用源码、先前输出及 Lean 反馈，成功后停止该条件，失败时在剩余预算内修复。
Each task and condition receives only its frozen goal, permitted sources, previous outputs and Lean feedback; it stops after success and repairs failures within the remaining budget.

## 用量与记录 / Usage and records

预算按每个任务、每个条件分别限制调用次数和输出 token，最后一次调用的输出上限会缩减到剩余预算。
Budgets separately limit calls and output tokens for each task and condition, clipping each call's output allowance to the remaining task budget.

供应商的 `output_tokens` 已包含推理 token，账本只计一次；输入 token 单列记录，这不是费用预算或输入加输出的总 token 上限。
Provider `output_tokens` already includes reasoning tokens and is charged once; input tokens are recorded separately, so this is neither a monetary budget nor a cap on combined input and output tokens.

每次调用先写独立预约，再保存原始响应、供应商用量收据和后续 Lean 结果；用量在 Lean 开始前落盘，因此验证中断也保留已经观察到的生成用量。
Each call writes an independent reservation before saving the raw response, provider-usage receipt and subsequent Lean result; usage is saved before Lean starts, preserving observed generation usage even if verification is interrupted.

格式错误、拒绝、不完整输出、证明失败和中断都保留，已经消耗的调用不会免费重试；未知用量保持未知，报告另列已知下界与保守预约额度。
Malformed output, refusal, incomplete output, proof failure and interruption remain recorded, and consumed calls are not retried for free; unknown usage stays unknown, with a known lower bound and conservative reserved allowance reported separately.

用量未知或调用、验证中断时，驱动器停止后续生成且不会自动重发；先审计记录，再为明确的新协议建立新运行，不要删除尝试或重置预算来继续旧实验。
When usage is unknown or a call or verification is interrupted, the driver stops further generation without automatically resending; audit the records before preparing a new run under an explicit new protocol, and do not delete attempts or reset budgets to continue an old experiment.

`generation.json` 冻结配置、顺序、驱动器和输入指纹，`reservations/` 保留调用名额，`calls/` 保留原始响应、`receipt.json` 和结果，`stop.json` 保留停止事件。
`generation.json` freezes configuration, order, driver and input fingerprints; `reservations/` preserves consumed call slots, `calls/` retains raw responses, `receipt.json` and results, and `stop.json` records the stop event.

收据明确区分 `openai_responses` 与 `injected_test_transport`；旧迁移会话的 `interactive_agent` 值仅为兼容既有枚举，不表示实际通过聊天代理生成。
Receipts distinguish `openai_responses` from `injected_test_transport`; the legacy migration session's `interactive_agent` value preserves enum compatibility and does not assert that generation used a chat agent.

模型请求名称、响应报告的模型标识和精确修订证明分开记录；当前不把响应名称或本地校验和当成精确修订、供应商签名或公平性证明。
The requested model name, response-reported model identifier and proof of exact revision remain distinct; a response name or local checksum does not certify exact revision, provider attestation or fairness.

## 离线与 Lean 检查 / Offline and Lean checks

下面的冒烟检查注入确定性测试响应，并实际调用 Lean 检查证明与失败后修复；结果明确标为测试夹具，不消耗供应商用量。
The following smoke check injects deterministic test responses and invokes real Lean to check proofs and repair after failure; results are explicitly labelled as a fixture and consume no provider usage.

```bash
python scripts/check_generation.py --output data/generation-smoke
```

Python 单元测试还覆盖请求隔离、预算裁剪、未知用量停止、中断恢复、过长证明和记录篡改；这些检查不等于已经完成真实模型或新预留任务的实验。
Python unit tests additionally cover request isolation, allowance clipping, stopping on unknown usage, interrupted runs, oversized proofs and record tampering; these checks do not constitute a live-model experiment or evaluation on fresh held-out tasks.

下一步是在隔离环境中完成小规模真实调用校准，确认供应商用量和停止记录，再冻结未使用过的迁移模式开展资源匹配的版本比较。
Next, run a small live calibration in an isolated environment, check provider usage and stop records, then freeze unused migration patterns for a resource-matched version comparison.

API 字段与输出计数口径依据 [OpenAI 推理文档](https://developers.openai.com/api/docs/guides/reasoning)、[token 计数文档](https://developers.openai.com/api/docs/guides/token-counting) 和[结构化输出文档](https://developers.openai.com/api/docs/guides/structured-outputs)。
API fields and output accounting follow the linked official OpenAI documentation; model availability and account access still require live verification.
