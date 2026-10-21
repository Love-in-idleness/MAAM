# 有限旧工具确认 / Bounded old-tool confirmation

日期：2026-10-21；工具组合已有单轮搜索与执行器，保持冻结源码、历史记录和原证明不变。
Date: 2026-10-21; the controller composes existing one-sweep searches without modifying their implementations or prior evidence.

## 固定范围 / Fixed scope

一次仅接收一到两道已核验开发题，固定运行已有的两种 `simpa` 源码模式改写，最多三轮，总扫描名额最多十二个。
Each round uses the frozen one-sweep policy, so existing per-search limits remain unchanged and no new theory or model transport is introduced.

原证从指定会话池按既有源码规则选取，下一轮追加此前完整轮次的内部会话，再核对继承证明的 SHA 和 token 数，不允许换题、插入额外会话或改用更长原证重新计算收益。
Replay checks the exact incumbent chain, task order, method schedule, knowledge and metric identities before admitting another round.

完整且无拒绝、未知或替换的轮次才算一次“无改善确认”；改善或拒绝重置连续计数，中断或未知立即停止。
A round counts as clean only when both the execution and underlying search reports confirm its complete no-improvement outcome.

连续两轮确认后停止，不继续消耗第三轮；三轮用尽仍不足两轮确认则返回预算耗尽，不能标记准备完成。
Repeated deterministic scans implement a stopping rule, not independent statistical evidence or a proof that every existing tool was used.

每轮先向不可重用名额日志写入并同步预约，再创建子搜索；缺少记录、未完成执行或删除已预约目录都不能恢复名额，输出文件拒绝覆盖。
The local guards detect inconsistent or interrupted records; they are not signed attestations against an operator rewriting the complete history.

## 运行与回放 / Run and replay

先用已有清单工具准备一到两题的当前最好证书，包含已经发现的有效缩短，而不从更长历史证明重新开始。
Use `scripts/prepare_baseline.py` with the original baseline sessions and any relevant previously verified rewrite sessions.

```bash
python scripts/control_baseline_stability.py prepare \
  --inventory /path/to/current-two-goal-inventory.json \
  --root data/baseline-stability-NEW
python scripts/control_baseline_stability.py run \
  --root data/baseline-stability-NEW --output /path/to/new-report.json
python scripts/control_baseline_stability.py status \
  --root data/baseline-stability-NEW
```

`status` 从原始子记录重新计算结果，不重新调用 Lean；终止后的 `run` 不增加尝试，中断后的目录也不能自动恢复执行。
Budget exhaustion and interrupted or inconclusive evidence return a nonzero exit code; a successful preparation command alone is not completed confirmation.

## 2026-10-21 现场结果 / Local observed result

本次从四个历史基础库会话加上上次改写的两个内部会话开始，d01 为 150、d03 为 217 个源码 token，共 367；不把已经记录的 370→367 再算作本次收益。
The raw local records are in `data/baseline-stability-pilot-20261021-v1/`, with a committed [result summary](../results/baseline-stability-v1.json); the raw historical session pool is not included in Git.

| 轮次 / Round | 扫描 / Scans | 新 Lean 核验 / Fresh Lean checks | 拒绝或未知 / Rejected or unknown | 替换 / Replacements | 所选源码 token / Selected source tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 4 | 1 | 0 | 0 | 367 |
| 2 | 4 | 1 | 0 | 0 | 367 |

两次 d01 候选均由隔离 Lean 4.24.0 核验通过，但完整模块为 152 token，比原证的 150 更长，因而都保留原证；其余六次扫描没有匹配支持的模式。
Both rounds are clean under the declared rule, so confirmation finishes after eight scans with no third round and no additional shortening.

本轮没有供应商调用或密钥读取；历史模型生成用量继续为未知，实际核验资源仍保存在各次尝试的原始轨迹中。
The original one-sweep pilot and untouched four-goal preparation replay separately without relabeling their results.

## 状态含义 / Meaning of completion

`declared_method_preparation_complete: true` 仅确认这两种固定改写在这两题上的预定停止规则已经满足。
The broader `baseline_search_complete`, `package_attribution_ready`, `globally_shortest`, `model_search_verified` and `definition_optimization_performed` flags remain false.

定义、原目标、imports 与背景源码在本流程中保持相同，所以本次不需要新的表示转换；这不表示已经执行定义优化或实现一般定义兼容性判定。
This unchanged-environment check cannot establish general semantic compatibility, AI comprehension or the value of adding a new package.

下一步可把这组证书作为明确版本的输入，搭建更广旧工具搜索或方法复用对照；不能仅凭两种文本改写就宣布所有已有条件已充分利用。
Keep old-tool search, method usability and complete-package compression as separate recorded observations before attributing any benefit to new theory.
