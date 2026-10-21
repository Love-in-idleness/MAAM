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

## 现场结果 / Live results

| 中文 | English |
| --- | --- |
| 2026-10-22 已完成两次真实调用，均报告 deepseek-flash，两个候选均通过隔离 Lean 4.24.0 核验并严格缩短。协议与控制器先提交为 c3fc1c0，再准备和调用。 | Two live calls completed on 2026-10-22, both reporting deepseek-flash. Both candidates passed isolated Lean 4.24.0 verification and strictly shortened their incumbents. Protocol and controller commit c3fc1c0 preceded preparation and generation. |
| [提交摘要](../results/model-baseline-v1.json)可从本地原始记录重新计算。原证、两次输入、原始响应、用量收据、候选及核验结果均保留。 | The [committed summary](../results/model-baseline-v1.json) replays from local raw evidence. Original proofs, both inputs, raw responses, usage receipts, candidates and verification results are retained. |

| 目标 / Goal | 原证完整源码 token / Incumbent full-source tokens | 新证完整源码 token / New full-source tokens | 核验及采用 / Verification and selection |
| --- | ---: | ---: | --- |
| d01 | 150 | 42 | Lean verified; adopted |
| d03 | 217 | 144 | Lean verified; adopted |
| 合计 / Total | 367 | 186 | 181 tokens saved |

| 中文 | English |
| --- | --- |
| 供应商报告输入 3260、输出 12805、合计 16065 个 token；输出已含推理，未重复计数。按固定高峰价格加 25% 余量，估算为 $0.02043，完整预约 $0.110592，上限 $0.12。无重试或修复调用。 | Provider-reported usage is 3260 input and 12805 output tokens, totaling 16065. Reasoning is included once. Fixed peak-price accounting plus a 25% margin estimates $0.02043, against $0.110592 reserved and a $0.12 ceiling. No retry or repair calls occurred. |
| 两题仅使用原有源码。181 token 的改善属于旧工具搜索，不能归给新理论。此前两种确定性改写的有限确认仍然成立，但不代表所有原有工具已充分利用。 | Both goals used existing sources only. The 181-token gain belongs to old-tool search, not new theory. Earlier bounded confirmation of two deterministic rewrites remains valid within its scope and does not establish sufficient use of all existing tools. |
| 历史 367→229 的整包对照继续作为旧版本记录保留；它没有使用本次 186 token 基线，也不是本轮重新测量的结果。下一步先将新证书接入新版整包对照，再讨论方法复用。 | The historical 367→229 package comparison remains an older-version record. It does not use this 186-token baseline and was not remeasured in this trial. Next, connect these certificates to a new package comparison before examining method reuse. |
| 全部 343 项测试通过；历史结果、M1 压缩和原证保留压缩报告均通过离线回放。测试中的 Lean 夹具与本次两份真实 Lean 证书明确区分。 | All 343 tests passed; archived results, M1 compression and retained-portfolio compression replayed offline. Lean fixtures in tests remain distinct from the two fresh live Lean certificates. |

```bash
python scripts/control_model_baseline.py status \
  --root data/model-baseline-pilot-20261021-v1/run
```

| 中文 | English |
| --- | --- |
| 本地 selected-inventory.json 已导出本次最短证书，可直接作为后续有限搜索的输入；原始目录为 data/model-baseline-pilot-20261021-v1/。 | The local selected-inventory.json exports the selected certificates for later bounded searches; raw evidence lives under data/model-baseline-pilot-20261021-v1/. |
| 两题仍不足以证明基线已充分优化；本次没有预留集实验、定义改写、认知难度测量或新理论收益归因。下一轮继续当前 GPT-6.1 Sol 做对照工具工程，真实候选仍用 DeepSeek。 | Two goals do not establish sufficient baseline optimization. No held-out experiment, definition rewrite, cognitive-difficulty measurement or new-theory attribution occurred. Continue with GPT-6.1 Sol for comparison tooling and DeepSeek for actual candidate generation. |
