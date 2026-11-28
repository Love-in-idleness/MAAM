# Lean 4.24.0 适配器

[English](README.md)

`maam/Export.lean` 从展开后的 Lean 命题类型与证明体中提取每个 `const` 和 `Sort` 的出现次数，并显式记录原始边界节点。

本适配器已在 **Lean 4.24.0** 上通过 GitHub Actions `Lean adapter` 工作流（含编译、演示命题导出、指标核对与 `sorry` 污染排除，证据见 [results/remote_validation.json](../results/remote_validation.json)）。全库 Mathlib 管线、源码 token 统计与 SCC 收缩见 [docs/REPRODUCTION.zh-CN.md](../docs/REPRODUCTION.zh-CN.md)。

## 独立冒烟检查

安装 Lean `4.24.0` 后执行：

```bash
(cd lean && lean -o Demo.olean Demo.lean)
python -m maam export-lean --runner lean --project lean --module Demo \
  --target Demo.andRight --target Demo.modusPonens --target Demo.andSwap \
  --target Demo.admittedExample --output results/lean-demo.json
python -m maam rank --corpus results/lean-demo.json --format text
python -m maam score --corpus results/lean-demo.json --name Demo.admittedExample
```

## 从本地 Mathlib 导出局部模块

在 MAAM 根目录针对已编译的 Mathlib 仓库运行（使用该仓库自带的 Lean 版本与 Lake 环境）：

```bash
python -m maam export-lean --project /absolute/path/to/mathlib4 \
  --module Mathlib.Analysis.Real.Hyperreal --target Hyperreal.infinitesimal_zero \
  --expand-prefix Mathlib.Analysis.Real.Hyperreal --output data/hyperreal-local.json
python -m maam score --corpus data/hyperreal-local.json --name Hyperreal.infinitesimal_zero
```

此例仅构建带显式模块边界的局部依赖闭包，其评分不同于全库索引。原论文固定 Mathlib 快照为 `d167cc6dc962ab340507362ea2f4bcfcff44f01b`（Lean `4.24.0`），更换版本会改变评分。

## 边界与长度口径

- **`unsafe` 与循环**：本小语料适配器将 `unsafe` 声明标为带 admission 的原始边界，JSON 计算器拒绝其余循环；而全库实验的 `maam/PaperExport.lean` 保留 `unsafe` 声明并收缩 SCC。二者构成不同的语料定义。
- **引用计数 vs. 源码 token**：`simp` 等策略会展开出更大的内核项，内部引用数不能冒充源码 token 数。本适配器使用引用计数口径，源码 token 仅由独立的固定快照管线生成。
