# 模型基线与整包对照 / Model baseline and complete-package comparison

| 中文 | English |
| --- | --- |
| 2026-10-22 的阶段成果：从真实 DeepSeek 收据、所选证书、有限确认到整包压缩，已经能连续回放。现有评估器和历史结果保持冻结，只增加来源衔接。 | Milestone on 2026-10-22: the chain from actual DeepSeek receipts through selected certificates and bounded confirmation to complete-package compression now replays end to end. Existing evaluators and historical results stay frozen; the addition connects provenance. |
| 这次没有新模型调用或密钥读取。此前两次 DeepSeek 调用和真实 Lean 核验属于上一个阶段；本轮复用其证据。 | This round made no model calls and read no credentials. The two DeepSeek calls and fresh Lean checks belong to the preceding stage; this round reuses their evidence. |

## 来源链 / Provenance chain

| 中文 | English |
| --- | --- |
| 先重放模型控制器，再从它的原始会话池与准确的内部会话清单重新计算最短证书；不能接受另一份碰巧有效的基线。 | Replay the model controller, then reconstruct the shortest certificates from its original session pool and exact child-session list. An unrelated valid baseline cannot substitute for that inventory. |
| 外部导出的清单、有限确认的起始清单，都必须与重建结果逐项一致。Proof、submission、result 的原始字节也与模型所选证书一致；保留原证时允许目录不同的同字节副本。 | The exported inventory and confirmation seed must exactly match the reconstruction. Proof, submission and result bytes must match model-selected artifacts; byte-identical copies in other directories are valid when originals are retained. |
| 186-token 基线又完成两轮固定改写确认，共八次扫描、零候选、零额外 Lean 核验，仍为 186。它只满足这两种确定性规则的停止条件。 | The 186-token baseline completed two further fixed-rewrite rounds: eight scans, no candidates and no additional Lean checks. It remained at 186 tokens, satisfying only these two deterministic rules' stopping condition. |
| 原有整包工具负责相同目标、基础源码、工具链、公理与包声明检查，并只采用严格更短的有效替代证明。完整 Candidate、Extension 各计一次。 | The existing package tool checks matching goals, base sources, toolchain, axioms and package declarations, adopting only verified, strictly shorter alternatives. The complete Candidate and Extension modules are each charged once. |
| 最新两次调用的用量已知，继承证书更早的生成用量及作者辅助历史参考的用量仍未知。不能将它们拼成公平模型比较或完整训练成本。 | Usage is known for the latest two calls. Earlier inherited-proof generation and the author-assisted historical reference remain unmetered. Their combination is neither a fair model comparison nor a complete training-cost ledger. |

## 同一包在不同基线下 / Same package under different baselines

| 项目 / Item | 历史基线 / Historical baseline | 新模型基线 / New model baseline |
| --- | ---: | ---: |
| 原证合计 / Original proofs | 367 | 186 |
| 保留原证并择优后的证明 / Selected proofs with originals retained | 229 | 121 |
| 证明源码毛节省 / Gross proof-source saving | 138 | 65 |
| 完整包，计一次 / Complete package, charged once | 1100 | 1100 |
| 所选证明加包 / Selected proofs plus package | 1329 | 1221 |
| 净节省 / Net saving | −962 | −1035 |

| 中文 | English |
| --- | --- |
| 新版保留 d01 的 42-token 原证，d03 从 144 采用历史 79-token 替代证明。因此新包仍可局部缩短，但在这两题上，完整包的成本超过节省。 | The new version retains d01's 42-token original and replaces d03's 144-token proof with the archived 79-token alternative. The package still shortens one proof, but its full cost exceeds the saving on these two goals. |
| 旧工具搜索把包的表面毛收益从 138 降到 65。这正是引入新概念前需要准备基线的原因：不能把原来就能做的整理算成新理论的贡献。 | Old-tool search reduced the package's apparent gross benefit from 138 to 65. This illustrates why baseline preparation matters before introducing concepts: ordinary existing-tool improvements cannot be credited to new theory. |

| 压缩口径 / Compression scope | 新基线 / New baseline | 所选证明加完整包 / Selected proofs plus full package |
| --- | ---: | ---: |
| 不含共同背景，zlib-9 / Nonshared, zlib-9 | 313 B | 1293 B |
| 包含共同源码，zlib-9 / Joint local sources, zlib-9 | 647 B | 1557 B |
| 不含共同背景，bzip2-9 / Nonshared, bzip2-9 | 367 B | 1317 B |
| 包含共同源码，bzip2-9 / Joint local sources, bzip2-9 | 710 B | 1579 B |

| 中文 | English |
| --- | --- |
| 压缩算法、规范 JSON、源代码字节和解压核对沿用原协议；没有修改计量方式来使结果更好。task_id/Proof 标签仍代表独立证明环境，不是可以合编的一套 Lean 模块。 | Codecs, canonical JSON, exact source bytes and round-trip checks retain the existing protocol. The metric was not changed to improve the result. task_id/Proof labels still identify independent proof contexts rather than jointly importable Lean modules. |
| 负收益只描述这个包在这两题与所选证书下的结果，不能推出它对其他任务没有价值，也不能推出一般压缩方法无效。 | Negative savings describe this package on these two goals with these witnesses. They do not establish that the package lacks value elsewhere or that compression is generally ineffective. |
| 全部 355 项测试通过，包括新增的 12 项来源链和原证保留测试；新版结果、旧版结果、M1 压缩及既有研究报告均通过回放。 | All 355 tests passed, including 12 new provenance-chain and incumbent-retention tests. The new and old comparisons, M1 compression and existing research reports all replayed successfully. |

## 复现 / Reproduce

```bash
python scripts/measure_model_portfolio.py \
  --model-root data/model-baseline-pilot-20261021-v1/run \
  --inventory data/model-baseline-pilot-20261021-v1/selected-inventory.json \
  --baseline-root data/model-portfolio-pilot-20261022-v1/confirmation \
  --treatment-session data/transfer-package-reuse-diagnostic-20261020/reference-treatment \
  --check results/model-retained-compression-v1.json
```

| 中文 | English |
| --- | --- |
| 去掉 --check 并指定尚不存在的 --output 路径可以另存结果。回放同时检查来源指纹、已知用量、原始证书及实际压缩字节；输出拒绝覆盖。 | Replace --check with --output and a new path to save another report. Replay checks provenance fingerprints, known usage, original certificates and actual compressed bytes; existing outputs are never overwritten. |
| [新版结果](../results/model-retained-compression-v1.json)与[旧版结果](../results/retained-compression-v1.json)分开保存。本机 data/ 保留完整来源；提交摘要不能替代这些原始记录。 | The [new result](../results/model-retained-compression-v1.json) is saved separately from the [old result](../results/retained-compression-v1.json). Full sources remain in local data/; summaries do not replace raw evidence. |
| 接下来适合做小范围方法复用：固定少数开发目标，检查清晰的方法入口和证明义务是否帮助生成有效调用，并继续计入完整方法源码成本。 | Next, test method reuse on a few fixed development goals: check whether explicit entry conditions and proof obligations help produce valid invocations, while continuing to charge complete method-source costs. |
| 当前阶段不需要切换 Astra。充分基线优化、公平模型比较、预留集效果、一般理解难度及自动新理论发现仍未验收。 | This milestone does not require switching to Astra. Sufficient baseline optimization, fair model comparison, held-out effects, general comprehension difficulty and automatic theory discovery remain unaccepted. |
