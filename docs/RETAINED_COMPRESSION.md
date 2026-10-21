# 保留原证的整包压缩 / Retained-proof package compression

| 中文 | English |
| --- | --- |
| 日期：2026-10-21。本工具把已经完成有限确认的基线、历史替代证明、严格选证规则和整包压缩接在一起。 | Date: 2026-10-21. This tool connects a baseline whose bounded confirmation is complete, archived alternative proofs, strict proof retention, and whole-package compression. |
| 复用已有 `_replay`、迁移会话检查、`retained_portfolio` 与 `measure_sources`，不修改冻结的评估器或过去的证明。 | It reuses the existing confirmation replay, migration-session checks, portfolio selector, and compressor without changing frozen evaluators or prior proofs. |

## 接口与核验 / Interface and checks

| 中文 | English |
| --- | --- |
| 输入限于一到两道已完成声明方法确认的开发目标，以及一个历史 treatment 会话；基础库、原目标源码、任务身份、工具链必须一致。不同历史模型或预算原样记录，不解释成公平求证对照。 | Inputs are one or two confirmed development goals and an archived treatment session. Shared sources, task identities, goals, and toolchain must match. Historical solvers and budgets remain descriptive, not a fair search comparison. |
| 工具重建每份 `Proof.lean`，核对原请求、原目标、标准公理、包声明、源码字节及 token 账本，并重放已有预约、结果和日志记录。 | The tool reconstructs each proof source and checks requests, goals, standard axioms, package declarations, byte counts, and token ledgers, reusing reservation, result, and log replay. |
| 某题缺少已核验替代证明、或替代证明等长、更长时，保留原证及其原始 imports；至少需要一份已核验替代证明提供完整包计量，未知成本不能补零。 | Missing, equal-length, or longer alternatives retain the original proof and imports. At least one verified alternative must supply complete package accounting; unknown costs cannot become zero. |
| `Candidate`、`Extension` 各计一次，即使某题保留原证或没有任何替换。共同背景为 `Base` 加本次目标的声明模块。 | Charge each candidate module once, including when originals are retained or no replacement is adopted. Shared background consists of `Base` and the selected goal modules. |
| 每题使用固定的 `task_id/Proof` 文档标签，避免同名 `Proof` 和 `Submission.solve` 覆盖。原始源码和导入环境不变；这些是独立上下文的证据组合，不能作为一个 Lean 库直接合编。 | Fixed `task_id/Proof` document labels prevent collisions between independent contexts. Sources and imports remain unchanged; the resulting evidence portfolio is not a jointly importable Lean library. |
| 压缩复用首版的规范 JSON、zlib-9 和 bzip2-9 及实际解压检查；同时报告排除共同背景和包含共同背景的结果，不按加法抵消压缩后的基础库。 | Compression reuses canonical JSON, both codecs, and round-trip checks. It reports payloads both excluding and including shared background, without assuming compressed sizes are additive. |

## 使用 / Usage

| 中文 | English |
| --- | --- |
| 在仓库根目录执行，输出路径必须尚不存在；`--check` 从原始证据重新计算，比较运行时、来源指纹与实际字节结果。 | Run from the repository root with a new output path. Strict replay recomputes runtime, provenance fingerprints, and measured bytes from the original evidence. |

```bash
python scripts/measure_retained_portfolio.py \
  --baseline-root data/baseline-stability-pilot-20261021-v1/run \
  --treatment-session data/transfer-package-reuse-diagnostic-20261020/reference-treatment \
  --output /tmp/retained-compression-NEW.json

python scripts/measure_retained_portfolio.py \
  --baseline-root data/baseline-stability-pilot-20261021-v1/run \
  --treatment-session data/transfer-package-reuse-diagnostic-20261020/reference-treatment \
  --check /tmp/retained-compression-NEW.json
```

## 本次结果 / Observed result

| 中文 | English |
| --- | --- |
| [已保存结果](../results/retained-compression-v1.json)组合当前 367 token 基线与作者辅助的历史参考会话，没有新模型调用或新 Lean 核验；d01 没有该会话中的替代证明而保留原证，d03 采用已有的 79 token 证明。 | The [saved result](../results/retained-compression-v1.json) combines the current 367-token baseline with an author-assisted historical reference session, without new model calls or Lean checks. d01 retains its original; d03 uses an existing 79-token proof. |

| 项目 / Item | 数值 / Value |
| --- | ---: |
| 原证 d01 / Original d01 | 150 token |
| 原证 d03 → 所选参考 / Original d03 → selected reference | 217→79 token |
| 所选证明合计 / Selected proofs | 367→229 token |
| 完整理论包，计一次 / Full package, charged once | 1100 token |
| 所选证明加包 / Selected proofs plus package | 1329 token |
| 扣包后的净节省 / Net saving after package cost | −962 token |
| 不含共同背景的 zlib 字节 / Nonshared zlib bytes | 425→1360 |
| 包含共同源码的 zlib 字节 / Joint local-source zlib bytes | 740→1615 |
| 不含共同背景的 bzip2 字节 / Nonshared bzip2 bytes | 473→1399 |
| 包含共同源码的 bzip2 字节 / Joint local-source bzip2 bytes | 817→1615 |

| 中文 | English |
| --- | --- |
| d03 的历史证书直接引用 `Theory.Hom.map_one`，说明这条已核验引用可以接入账本；它不是新的 AI 工具发现，也不是原核封闭性方法说明卡的迁移实验。 | The historical d03 certificate directly references `Theory.Hom.map_one`, demonstrating that this checked reference can enter the ledger. It is neither a new AI discovery nor a transfer experiment for the kernel-closure method card. |
| 两种成本均显示局部证明缩短而完整包更大。本次只验证接线与计量，全面基线优化、公平模型比较、方法卡可用性、留出评价和新理论因果归因均未完成。 | Both measurements show shorter selected proofs but a larger complete package. This validates integration and accounting; broader optimization, fair model comparison, method-card usability, held-out evaluation, and causal attribution remain unestablished. |
| 原始会话保留在本机 `data/`，未纳入 Git；完整回放需要这些记录。单元测试使用明确标注的审计 fixture，不替代真实历史证据。 | Raw sessions remain in local `data/` and are not committed. Full replay requires those records; unit-test audit fixtures do not replace historical evidence. |
| 下一步适合对少量目标接入有记录的 DeepSeek 旧工具搜索，再研究方法复用；不能用此历史参考组合宣布基线已充分优化。 | The next useful step is a small, recorded DeepSeek search using existing tools before studying further method reuse; this historical composition does not certify sufficient baseline optimization. |
