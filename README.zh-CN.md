# MAAM · 形式化数学组织与评估工具集

[English](README.md)

MAAM 是一套用于测量 Lean 形式化数学组织方式的研究工具。它一方面计算 Lean 声明的静态压缩与依赖指标，另一方面在固定基础库与隔离核验环境中，评估引入可复用理论包（定义、引理与桥接）前后的完整成本变化。

## 快速开始

在仓库根目录使用 Python 3.11+ 运行（核心命令仅依赖 Python 标准库）：

```bash
python -m maam score --corpus examples/paper_simple_lemma.json --name simple_lemma --format text
python -m maam rank --corpus examples/toy_corpus.json --format text
```

第一条命令测量 `A ∧ B → B` 的给定证明，返回约化压缩指标 `T0 = 1` 与证明/命题长度比 `I0 = 4/3`；第二条对小型示例语料进行排序。所有结果均依赖选定的语料、表示方式与原始边界。

## 文档导航

### 研究目标与计划
- [工具复用与整包压缩目标](docs/REUSE_COMPRESSION_OBJECTIVE.zh-CN.md) — 当前阶段主问题、完整成本口径、选证规则与停止条件。
- [研究计划与进度](docs/RESEARCH_PLAN.zh-CN.md) — 里程碑（M0–M4）、已观测实验证据与未完成的研究问题。

### 使用与技术指南
- [指标与操作定义](docs/METRICS.zh-CN.md) — `T0`、`I0`、PageRank `I1`、`E_finite` 及解释边界。
- [数据输入格式](docs/DATA.zh-CN.md) — 引用语料 JSON 结构、大数精度处理与有限证明超图。
- [Lean 接口说明](lean/README.zh-CN.md) — 从 Lean 4.24.0 工程导出声明与依赖。
- [理论包评估指南](docs/THEORY_PACKAGES.zh-CN.md) — 隔离 Lean 核验与整包成本账本。
- [证明预压缩与整包分账](docs/PROOF_PRECOMPRESSION.md) — 完整路线计量入口（`maam precompression --study ...`），共享模块计一次，区分可选采用、完整建库与已建库复用。
- [固定快照复现指南](docs/REPRODUCTION.zh-CN.md) — Mathlib 固定快照（`d167cc6dc962ab340507362ea2f4bcfcff44f01b`）与单子覆盖实验（[实验摘要](reports/mathlib/summary.json)、[复现状态](results/reproduction_status.json)）。

## 当前进展

- **已实现**：静态指标 CLI、Lean 4.24.0 导出与隔离核验、群同态/核参考迁移（[experiments/hom_kernel/README.md](experiments/hom_kernel/README.md)）、DeepSeek 计量迁移/指南/构造控制器、v2 显式 `theorem` 声明契约、包消融对照、证明预压缩与完整路线计量（`maam precompression`）及离线整包压缩计量（`zlib`/`bzip2`）。
- **已观测**：在 M1 同态/核参考迁移中，局部证明体从 `77` 缩至 `29` 个源码 token，但计入候选包后非共享源码从 `89` 增至 `353` token；在后续 DeepSeek 计量对照与原证保留压缩中，证明节省均尚未抵消整包引入成本。
- **未完成**：旧工具基线充分优化、严格因果概念归因、大范围预留任务迁移、自动多轮候选搜索与学习闭环验收仍待完成。

## 参考文献

指标实现参考了 [*Compression is all you need: Modeling Mathematics*](https://arxiv.org/abs/2603.20396v1)（ABFM）与 [*Artificial Intelligence and the Structure of Mathematics*](https://arxiv.org/abs/2604.06107v1)（BDF）。
