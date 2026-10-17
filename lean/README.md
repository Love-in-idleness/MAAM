Lean 4.24.0 adapter / Lean 4.24.0 适配器
======================================

`maam/Export.lean` exports multiplicities from elaborated signatures and bodies,
including every `const` and `Sort` occurrence, with primitives explicitly recorded.
`maam/Export.lean` 从展开后的命题类型及证明体中提取每个 `const` 和 `Sort` 的出现次数，并显式记录原始节点。

This adapter passes the `Lean adapter` workflow on **Lean 4.24.0**, including
compilation, export of the demo declarations, metric checks, and `sorry`-taint
exclusion. The evidence is in [remote_validation.json](../results/remote_validation.json).
本适配器已在 **Lean 4.24.0** 上通过 `Lean adapter` 工作流，包括编译、演示命题导出、指标检查和 `sorry` 污染排除；证据见 [remote_validation.json](../results/remote_validation.json)。

The authoring container still has no local Lean toolchain; the successful check
ran in GitHub Actions. Full Mathlib extraction remains unverified.
编写容器仍没有本地 Lean 工具链，成功检查运行于 GitHub Actions；全量 Mathlib 提取仍未验证。

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
  --module Mathlib --expand-prefix Mathlib --output data/mathlib.json
python -m maam rank --corpus data/mathlib.json --limit 30 --format text
```

The paper's snapshot is `d167cc6dc962ab340507362ea2f4bcfcff44f01b`, whose
`lean-toolchain` specifies Lean 4.24.0. Changing the snapshot changes the scores.
原论文使用的 Mathlib 提交为 `d167cc6dc962ab340507362ea2f4bcfcff44f01b`，其工具链为 Lean 4.24.0；更换版本会改变评分。

Full Mathlib exports may contain recursive cycles. MAAM fails explicitly instead
of claiming a finite expansion. The paper condenses SCCs; this adapter does not
reproduce that convention. An explicit primitive boundary changes the metric and
must be recorded as a distinct corpus.
全量 Mathlib 可能含递归环；MAAM 会明确报错，不会将其冒充有限展开；论文使用 SCC 收缩，本实现尚未复现该约定；显式设置原始节点边界会改变指标，必须记录为不同语料库。

Source token lengths are not inferred from elaborated proof sizes: `simp` and
other tactics make them different. This export uses the reference-count alternative
discussed in §3.2, **not** a numerical reproduction of the paper's token figures.
由于 `simp` 等策略会展开，证明内部引用数不能冒充源代码词法单元数；导出采用 §3.2 提到的引用计数替代口径，**并未数值复现论文中的 token 图表**。
