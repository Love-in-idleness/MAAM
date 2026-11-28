# 固定快照复现指南

[English](REPRODUCTION.md)

工作流 `Fixed Mathlib reproduction` 固定使用 [ABFM §3](https://arxiv.org/html/2603.20396v1#S3) 给出的 Mathlib 提交 `d167cc6dc962ab340507362ea2f4bcfcff44f01b` 与 Lean `4.24.0`，避免将新版 Mathlib 的结果混充原论文数据。

## 运行 Mathlib 全库复现管线

```bash
python -m pip install '.[reproduction]'
bash scripts/build_paper_exporter.sh
cd /absolute/path/to/the/fixed/mathlib4
lake exe cache get
LEAN_SYSROOT="$(lean --print-prefix)" lake env /absolute/path/to/MAAM/build/maam-paper-export \
  Mathlib Mathlib . /absolute/path/to/MAAM/data/mathlib.jsonl \
  d167cc6dc962ab340507362ea2f4bcfcff44f01b
cd /absolute/path/to/MAAM
python scripts/analyze_mathlib.py --input data/mathlib.jsonl \
  --output reports/mathlib --index data/mathlib-metrics.sqlite
```

- 原生导出器由固定 Lean 版本的 Lake 配置构建，并在 CI 中与解释执行版比对小例，要求依赖次数、声明范围与 token 计数完全一致。
- 摘要、图表、分桶中位数、循环清单及前 100 条参考口径定理评分写入 `reports/mathlib/`；较大产物（`mathlib.jsonl`、`mathlib-metrics.sqlite.gz`）作为工作流产物保留 30 天。

### 查询已构建的 SQLite 索引（无需 Lean）

```bash
gzip -dk mathlib-metrics.sqlite.gz
python -m maam score-index --index mathlib-metrics.sqlite \
  --name AlgebraicGeometry.Scheme.exists_hom_hom_comp_eq_comp_of_locallyOfFiniteType
python scripts/reproduce.py --index data/mathlib-metrics.sqlite
```

`reproduce.py` 校验索引指纹匹配后，将实测原文示例指标写入 [results/mathlib_examples.json](../results/mathlib_examples.json)。

## 方法与口径约定

- **图范围**：来源模块内节点收缩前/后为 `463,719 → 463,661`；保留 `9,626` 个显式基础边界后完整图为 `473,345 → 473,287`。每个 `const` 与 `Sort` 按出现次数计数；Mathlib 内 `unsafe` 定义保留在图中，外部声明与 `Sort` 作为原始边界。
- **SCC 收缩**：删除强连通分量内部边、合并外部重数，收缩后的汇点展开长度取 `1`（属于图统计约定，并非把递归程序展开成有限字符串）。多声明分量返回 `null` 压缩比，不混淆单声明与分量指标。
- **源码 token**：使用 Lean 命令解析器统计声明范围内带原始位置的 atom/identifier 叶节点（排除注释、保留字符串），按文件重放 `namespace`/`section`/`open`/本地语法/`set_option`，不重新检查证明。主口径保留属性与修饰符（`declModifiers`），同时另列统一排除修饰符的敏感性分析；缺失范围或解析失败保持缺失（见 [source_failures.json](../reports/mathlib/source_failures.json)），绝不用内部引用数填补。
- **排名口径**：全声明 token 尚未拆分命题与证明，因此全库兴趣排名采用引用计数口径。

## 实测结果与论文目标核对

[已完成的全库工作流运行](https://github.com/Love-in-idleness/MAAM/actions/runs/39060623030) 已核验产物指纹与原文示例查询（源码修复前后依赖指纹完全一致，见 [results/mathlib_baseline.json](../results/mathlib_baseline.json)）：

| 原文示例 | 完整 token | 去修饰符 | 原文值 | 测得展开量 |
| --- | ---: | ---: | ---: | ---: |
| `VectorBundleCore.isOpenMap_proj` | 7 | 7 | 7 | ≈1.066×10^48 |
| `ContDiffBump.integrable` | 10 | 9 | 9 | ≈2.437×10^54 |
| `Hyperreal.infinitesimal_zero` | 8 | 8 | 8 | ≈3.635×10^31 |

**已知数值差异**（如实保留，不通过删节点或调窗口强行凑齐）：
- **token 斜率**：固定分桶窗口（深度 `[10, 250]`、token `[10, 200]`，每桶 ≥20 元素）无权线性拟合约为 `0.228`，低于原文的约 `0.4`。
- **最大展开量**：`10^110.6394` 对比原文约 `10^104`（最大值对应同一条定理，差异原因尚未确定）。

## 单子覆盖实验

仅依赖 Python 标准库（无需 Lean 或科学计算库）：

```bash
python scripts/reproduce_monoids.py
```

结果输出至 [reports/monoids/summary.json](../reports/monoids/summary.json) 与 [reports/monoids/finite_coverage.csv](../reports/monoids/finite_coverage.csv)：
- `A1`：动态规划枚举至 `65536`，宏集合分别为 2 的幂、`2^(2^j)`、`{2, 5, 13}` 与平方数（截断前无反例时仅报告下界并标 `right_censored=true`）。
- `A_n`：各坐标 `b` 次幂宏的精确覆盖半径公式 `n(b^q - 1) + r·b^q - 1`（`s + 1 = q·n(b - 1) + r`），并与二维/三维穷举交叉核对。
- `F2`：枚举长度至多 `12` 的二元串，以同字母幂串为宏（交替串保持原长）。
