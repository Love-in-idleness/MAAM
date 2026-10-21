# 旧工具的模型搜索 / Model search with existing tools

| 中文 | English |
| --- | --- |
| 本工具从已有的最短核验证书继续搜索，在两道开发题 d01、d03 上各调用一次 DeepSeek。模型可以提交候选，也可以明确保留原证；完整 Proof 模块严格更短且通过隔离 Lean 核验，才替换原证。 | This pilot continues from the shortest existing verified certificates, with one DeepSeek call on each of development goals d01 and d03. The model may propose a candidate or retain the incumbent; replacement requires isolated Lean verification and a strictly shorter complete Proof module. |
| 不引入新理论包，不触碰预留题。每次请求只含当前题的基础源码、目标和原证。原有搜索器保持冻结，真实供应商来源与用量单独保存在外层记录中。 | No new theory package or reserved goal is used. Each request contains only the current goal's base sources, target and incumbent. The inner search remains frozen; actual provider provenance and usage are recorded in an outer ledger. |

| 固定协议 / Fixed protocol | 值 / Value |
| --- | --- |
| 模型与接口 / Model and endpoint | `deepseek-flash`, `https://api.deepseek.com/responses` |
| 推理与保存 / Reasoning and storage | `low`, `store: false`, no tools |
| 调用 / Calls | At most 2; one per goal; no automatic retries or repairs |
| 每次输入预约 / Input reservation per call | 16384 tokens; full reservation plus a local byte screen, not a tokenizer estimate |
| 每次输出上限 / Output cap per call | 32768 tokens, including reasoning |
| 时间 / Timeout | 180 seconds per provider request |
| 价格估计 / Cost estimate | $0.30/M input, $1.20/M output, multiplied by 1.25 |
| 完整预约 / Full reservation | $0.110592, below the $0.12 ceiling |

| 中文 | English |
| --- | --- |
| 价格于 2026-10-21 根据[供应商价格页](https://api-docs.deepseek.com/quick_start/pricing/)核对；按高峰、输入未命中缓存的价格保守估计，不等同账单。模型别名也不证明精确修订。 | Prices were checked on 2026-10-21 against the [provider pricing page](https://api-docs.deepseek.com/quick_start/pricing/). The estimate uses peak, uncached input prices and a margin; it is not an invoice. The model alias does not verify an exact revision. |
| [Responses 文档](https://api-docs.deepseek.com/api/create-response/)规定输出上限包括推理。原始用量中的 output_tokens 已含 reasoning_tokens，计费时不重复相加。 | The [Responses documentation](https://api-docs.deepseek.com/api/create-response/) defines the output cap as including reasoning. Reported output_tokens already includes reasoning_tokens and is counted once. |
| 实际输入仍由供应商计量；预约不是供应商硬上限。若已发生调用超限，保留真实用量并停止后续调用。 | Actual input is metered by the provider; the reservation is not a provider-enforced input cap. Any observed overrun is retained and stops subsequent calls. |
| 调用前将预约写入并同步；收到响应后先保存原始字节和用量收据，再交给 Lean。用量未知、供应商失败、模型不符、输出截断或格式错误立即停止，不自动重试。 | Reservations are written and synced before calls. Raw response bytes and usage receipts are saved before Lean runs. Unknown usage, provider failure, model mismatch, truncation or malformed output stops the pilot without automatic retries. |
| 被拒绝或更长的候选也保留。中断名额不可重用。status 从保存的响应重新计算用量、绑定和选择结果，不重新请求模型或 Lean。 | Rejected and longer candidates remain archived. Interrupted slots cannot be reused. Status replays saved responses, usage, bindings and selections without calling the model or Lean. |
| 密钥只从明确指定的用户私有文件读取，仅交给固定 DeepSeek 接口的认证头。记录不含密钥及其路径；HTTP 错误正文不保存。没有 OpenAI 回退路径。 | Credentials are read only from the explicitly selected owner-only file and sent only in the fixed DeepSeek endpoint's authentication header. Records contain neither the key nor its path; HTTP error bodies are discarded. There is no OpenAI fallback. |

```bash
# Commit the controller before preparing a live run.
python scripts/control_model_baseline.py prepare \
  --inventory /path/to/current-two-goal-inventory.json \
  --root data/model-baseline-NEW
python scripts/control_model_baseline.py next \
  --root data/model-baseline-NEW --key-file /path/to/private-deepseek-key
# Repeat next only if status is still in_progress.
python scripts/control_model_baseline.py status --root data/model-baseline-NEW
```

| 中文 | English |
| --- | --- |
| 完成两次尝试只表示本协议已执行，不能宣称旧工具已充分使用、证明全局最短或新概念有收益。内层 supplied_local 标签保持原义；模型调用证据以外层收据为准。 | Completing two attempts establishes execution of this protocol, not sufficient use of existing tools, global minimality or concept value. The inner supplied_local labels retain their original meaning; provider evidence comes from the outer receipts. |
| 测试中的供应商响应和 Lean 证书是明确的模拟夹具；现场运行结果另行记录。完整原始记录保存在 Git 忽略的 data/ 中，提交摘要不能单独替代原始回放。 | Provider responses and Lean certificates in tests are explicit fixtures. Live results are recorded separately. Full raw evidence stays in Git-ignored data/; committed summaries alone do not replace raw replay. |
