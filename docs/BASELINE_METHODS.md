# 旧工具局部改写的实际执行 / Executing local existing-tool rewrites

本工具在[已有搜索记录流程](BASELINE_SEARCH.md)之上，实际运行两种固定的源码模式改写，再由原有隔离 Lean 检查器判断候选是否有效、完整证明模块是否严格更短。
It adds no theory package, changes no definitions and uses no model API; matching a source pattern is only candidate generation, not a correctness certificate.

## 方法与记录 / Methods and records

第一种方法把连续的 `have h := expression`、`rw [rules] at h`、`exact h` 尝试合并为 `simpa only [rules] using (expression)`。
The second tries to replace consecutive `rw [← expression]` and `exact value` with `simpa only [expression] using (value)`.

每次只处理第一个受支持的匹配，存在注释、字符串或不支持的语法时保守保留，不匹配不能解释成已经穷尽旧工具。
These are conservative physical-line scans, not a Lean parser or exhaustive simplifier; exact method instructions and the runtime sources are frozen before execution.

执行器在生成前写入并同步名额日志，记录请求、原证与生成前后的指纹、匹配行号和响应，再绑定检查器的实际提交及结果。
Replay regenerates the exact response and checks its link to the authoritative search record; incomplete generation, submission or outcome evidence stops progress without an automatic retry.

扫描前后的字节数只描述文本变化，最终选择仍使用既有的完整 `Proof` 模块源码 token 指标，等长、更长、拒绝或未知结果都保留已核验原证。
All originals and attempts remain available, including a valid candidate that loses under the declared source metric; expression size is reported separately.

## 使用与状态 / Use and status

先用 `scripts/prepare_baseline.py` 从已有会话整理一到两个开发目标的独立清单，再准备新搜索目录；[首版策略](../experiments/baseline_methods_v1/policy.json)固定两种方法、一轮，至多四次扫描。
The execution adapter rejects an already used search, a changed method description, more than four slots or a policy with more than one sweep.

```bash
.venv/bin/python scripts/control_baseline_search.py prepare \
  --inventory /path/to/two-goal-inventory.json \
  --policy experiments/baseline_methods_v1/policy.json \
  --root data/baseline-method-search-NEW

.venv/bin/python scripts/control_baseline_execution.py prepare \
  --search-root data/baseline-method-search-NEW \
  --root data/baseline-method-execution-NEW

.venv/bin/python scripts/control_baseline_execution.py run \
  --root data/baseline-method-execution-NEW \
  --output data/baseline-method-report-NEW.json

.venv/bin/python scripts/control_baseline_execution.py status \
  --root data/baseline-method-execution-NEW
```

`declared_methods_executed` 只表示预定扫描全部完成，退出码为零并不表示基线充分优化；中断或未知结果返回非零状态。
The underlying search can simultaneously report `sweep_budget_exhausted`, because an improvement requires a later clean confirmation sweep that this one-sweep pilot does not provide.

执行报告的五个准备、归因、全局最短、模型搜索及定义优化标志继续为假，供应商调用为零；沿用的本地响应生成用量字段仍保留为空，不把历史模型用量改成零。
Local seals detect inconsistencies and interruptions, but do not provide signed attestation against rewriting the complete history.

## 2026-10-20 小范围实测 / Small local pilot

实际记录位于 `data/baseline-method-pilot-20261020-v1/`，从四个历史基础库会话中选择 d01、d03 的最短已有证书，每个开发推理组取一题，不代表整体效果。
Four fixed scans produced two candidates and two no-match retentions, and both candidates passed real isolated Lean 4.24.0 verification without manual repair.

| 项目 / Item | 原证 / Original | 候选 / Candidate | 选择 / Selection |
| --- | ---: | ---: | --- |
| d03 完整模块源码 token / Full-module source tokens | 220 | 217 | 采用候选 / Candidate |
| d01 完整模块源码 token / Full-module source tokens | 150 | 152 | 保留原证 / Original |
| 两题所选源码合计 / Selected source total | 370 | 367 | 减少 3 / Saves 3 |

d03 的完整证明表达式由 2833 降为 2790 个节点，d01 候选则由 1562 降为 1484 个节点但源码更长，仍按事先固定的源码规则保留 d01 原证。
These costs remain separate; the pilot does not retroactively switch metrics to accept the second candidate.

本轮通过全部 299 项测试，旧报告及本轮执行记录均可重放；没有供应商调用、凭据读取、新包引入或定义改动，原有四题准备目录仍保留未提交状态。
The observed three-token saving belongs entirely to old-tool cleanup, with no evidence of concept contribution, sufficient baseline preparation or globally shortest proofs.

下一步完善定义兼容性和有限搜索验收约定，再考虑必要的小范围 DeepSeek 检查，不因这次有限改写完成就引入新包或扩大实验。
Reuse the configured DeepSeek Flash/low route only when model generation is needed, keeping model changes separate from tool validation and preserving complete usage and failure records.
