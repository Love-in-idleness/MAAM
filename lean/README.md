Lean 4.24.0 adapter / Lean 4.24.0 适配器
======================================

`maam/Export.lean` exports multiplicities from elaborated signatures and bodies,
including every `const` and `Sort` occurrence, with primitives explicitly recorded.
`maam/Export.lean` 从展开后的命题类型及证明体中提取每个 `const` 和 `Sort` 的出现次数，并显式记录原始节点。

This adapter passes the `Lean adapter` workflow on **Lean 4.24.0**, including
compilation, export of the demo declarations, metric checks, and `sorry`-taint
exclusion. The evidence is in [remote_validation.json](../results/remote_validation.json).
本适配器已在 **Lean 4.24.0** 上通过 `Lean adapter` 工作流，包括编译、演示命题导出、指标检查和 `sorry` 污染排除；证据见 [remote_validation.json](../results/remote_validation.json)。

The checks run in GitHub Actions on the pinned toolchain. For the separate full
Mathlib pipeline, source tokens, and SCC treatment, see the
[fixed-snapshot reproduction guide](../docs/REPRODUCTION.md).
检查使用固定工具链在 GitHub Actions 上执行；全库管线、源码 token 和 SCC 处理见独立的[固定快照复现说明](../docs/REPRODUCTION.md)。

Standalone smoke check (after installing the pinned Lean toolchain):
安装指定 Lean 版本后，可执行以下独立检查：

```bash
(cd lean && lean -o Demo.olean Demo.lean)
python -m maam export-lean --runner lean --project lean --module Demo \
  --target Demo.andRight --target Demo.modusPonens --target Demo.andSwap \
  --target Demo.admittedExample --output results/lean-demo.json
python -m maam rank --corpus results/lean-demo.json --format text
python -m maam score --corpus results/lean-demo.json --name Demo.admittedExample
```

In an existing Mathlib checkout, use its own Lean version and Lake environment:
在现有 Mathlib 仓库中，应使用该仓库自己的 Lean 版本及 Lake 环境：

```bash
# Run from the MAAM repository after building/importing the required Mathlib module.
python -m maam export-lean --project /absolute/path/to/mathlib4 \
  --module Mathlib.Analysis.Real.Hyperreal --target Hyperreal.infinitesimal_zero \
  --expand-prefix Mathlib.Analysis.Real.Hyperreal --output data/hyperreal-local.json
python -m maam score --corpus data/hyperreal-local.json --name Hyperreal.infinitesimal_zero
```

This is a limited dependency-closure example with an explicit module boundary; its score is not the full-corpus index score. Use the fixed-snapshot workflow for the complete Mathlib experiment.
这是有明确模块边界的局部依赖闭包示例，其评分不同于全语料索引；完整 Mathlib 实验应使用固定快照工作流。

The paper's snapshot is `d167cc6dc962ab340507362ea2f4bcfcff44f01b`, whose
`lean-toolchain` specifies Lean 4.24.0. Changing the snapshot changes the scores.
原论文使用的 Mathlib 提交为 `d167cc6dc962ab340507362ea2f4bcfcff44f01b`，其工具链为 Lean 4.24.0；更换版本会改变评分。

This small-corpus adapter treats unsafe declarations as admitted primitive
boundaries, and the JSON calculator rejects remaining cycles. The independent
`maam/PaperExport.lean` pipeline instead retains unsafe declarations and condenses
SCCs for the paper experiment. These boundary policies define distinct corpora.
小语料适配器将 unsafe 声明标成带 admission 的原始边界，JSON 计算器拒绝其余循环；独立的 `maam/PaperExport.lean` 管线则为论文实验保留 unsafe 声明并收缩 SCC；这些边界政策定义了不同的语料。

Source token lengths are not inferred from elaborated proof sizes: `simp` and
other tactics make them different. This export uses the reference-count alternative
discussed in §3.2. Source-token figures are produced only by the separate
fixed-snapshot pipeline, which explicitly reports missing source ranges.
由于 `simp` 等策略会展开，证明内部引用数不能冒充源代码词法单元数；此导出采用 §3.2 提到的引用计数替代口径；源码 token 图表仅由独立的固定快照管线生成，并显式报告缺少的源码范围。
