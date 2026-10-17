# 固定快照复现 / Fixed-snapshot reproduction

工作流 `Fixed Mathlib reproduction` 固定使用论文给出的 Mathlib 提交 `d167cc6dc962ab340507362ea2f4bcfcff44f01b` 和 Lean 4.24.0，不会把最新 Mathlib 的结果当成原论文数据。
The `Fixed Mathlib reproduction` workflow uses the paper's Mathlib commit `d167cc6dc962ab340507362ea2f4bcfcff44f01b` and Lean 4.24.0, rather than presenting results from current Mathlib as the original dataset.

## 运行与数据 / Running and data

工作流先检查真实 Lean 小命题的流式导出和源码词法计数，再获取固定快照的编译缓存，导出全量依赖并计算图统计。
The workflow checks streaming export and source lexical counts on actual Lean propositions before obtaining the snapshot's compiled cache, exporting its dependencies, and computing graph statistics.

```bash
python -m pip install '.[reproduction]'
cd /absolute/path/to/the/fixed/mathlib4
lake exe cache get
lake env lean --run /absolute/path/to/MAAM/maam/PaperExport.lean \
  Mathlib Mathlib . /absolute/path/to/MAAM/data/mathlib.jsonl \
  d167cc6dc962ab340507362ea2f4bcfcff44f01b
cd /absolute/path/to/MAAM
python scripts/analyze_mathlib.py --input data/mathlib.jsonl \
  --output reports/mathlib --index data/mathlib-metrics.sqlite
```

运行完成后，摘要、图表、分桶中位数、循环清单及前 100 个参考口径定理评分写入 `reports/mathlib/`。
On completion, the summary, plots, bucket medians, cycle list, and top 100 reference-basis theorem scores are written to `reports/mathlib/`.

原始 JSONL 和完整 SQLite 索引以压缩工作流产物保存；工作流会把体量较小的报告提交到仓库，若有并发提交则拒绝覆盖它们。
The raw JSONL and complete SQLite index are retained as compressed workflow artifacts; smaller reports are committed to the repository, and concurrent commits are never overwritten.

下载并解压 `mathlib-metrics.sqlite.gz` 后，可在没有 Lean 的机器上查询实际测量的声明。
After downloading and decompressing `mathlib-metrics.sqlite.gz`, declarations can be queried on a machine without Lean.

```bash
gzip -dk mathlib-metrics.sqlite.gz
python -m maam score-index --index mathlib-metrics.sqlite \
  --name AlgebraicGeometry.Scheme.exists_hom_hom_comp_eq_comp_of_locallyOfFiniteType
```

## 方法与可比性 / Method and comparability

原始表达式中的每个 `const` 和 `Sort` 都计入重复次数；来自 Mathlib 模块的 unsafe 定义保留在图中，外部声明和 `Sort` 作为原始边界。
Every `const` and `Sort` occurrence is counted with multiplicity; unsafe definitions from Mathlib modules are retained, while external declarations and `Sort` form the primitive boundary.

强连通分量收缩后，内部边删除，外部边的重复次数相加；每个收缩后的汇点按论文递推的原始节点约定取展开长度 1。
After SCC condensation, internal edges are removed and external multiplicities summed; each condensed sink has primitive expansion length 1 under the recurrence convention.

递归定义的收缩值是一种图统计约定，不等于把递归程序真正展开成有限字符串。
A condensed recursive definition's value is a graph-statistical convention, not an actual finite expansion of a recursive program.

源码计数使用 Lean 自身的 `tokenFn`，按声明位置范围统计，并排除普通注释、文档注释和嵌套注释；字符串里的注释标记仍属于字符串。
Source counts use Lean's own `tokenFn` within declaration ranges, excluding ordinary, documentation, and nested comments; comment markers inside strings remain part of the string.

具名声明的选择范围与声明名称匹配时标为 `named_source`；共享或生成的范围另行记录，两种过滤口径的中位数均输出。
A declaration is marked `named_source` when its selection range matches its name; shared or generated ranges are recorded separately, and medians under both filters are exported.

没有声明位置、源码缺失或词法失败时计数保持缺失，并报告覆盖率；不会改用内部引用数填补。
Missing declaration ranges, absent source files, and lexical failures remain missing measurements with reported coverage; internal reference counts are never used to fill them.

全声明 token 总数尚未拆成命题和证明两部分，因此全库兴趣排名明确使用引用计数口径，源码压缩比和论文图表独立报告。
Whole-declaration token totals are not split into statement and proof lengths, so full-corpus interest rankings explicitly use the reference-count convention, with source compression and paper plots reported separately.

索引保留各声明的原始 wrapped 计数和其所在分量的展开量；若分量含多个声明，则不把两种对象混合成单个声明的压缩比，而返回空比值。
The index retains each declaration's original wrapped counts and its component's expansion; for a component containing multiple declarations, it returns null ratios rather than combining measurements of different objects.

共享或生成的源码范围仍保留供检查，但只对具名源码范围提供源码压缩比。
Shared or generated source ranges remain available for inspection, but source compression ratios are supplied only for named source ranges.

## 核对目标 / Comparison targets

论文报告的节点数为收缩前 463719、收缩后 463661，最大展开量约为 `10^104`，最大深度约为 300。
The paper reports 463719 vertices before condensation, 463661 afterward, maximum expansion around `10^104`, and maximum depth around 300.

这些数值仅作为核对目标；程序不会删除节点、调整边界或更换回归区间来强行匹配它们。
These are comparison targets; the program does not drop nodes, alter boundaries, or change regression windows to force a match.

回归在固定范围上对分桶中位数做无权线性拟合：深度 `[10,250]`、token 数 `[10,200]`，每桶至少 20 个元素。
Regressions are unweighted fits of bucket medians over fixed ranges: depth `[10,250]` and token count `[10,200]`, with at least 20 elements per bucket.

原文未给出精确回归窗口和全部源码过滤细节，因此报告同时保留全部分桶数据、原文例子和数值差异，不将近似斜率写成精确复现。
The paper does not specify exact regression windows or every source filter, so reports retain all bucket data, source examples, and numerical differences rather than labelling approximate slopes as exact replications.

原文来源：[ABFM §3](https://arxiv.org/html/2603.20396v1#S3)；实现的自动检查和实际输出均以仓库中的工作流记录为准。
Source: [ABFM §3](https://arxiv.org/html/2603.20396v1#S3); workflow records are authoritative for implementation checks and actual outputs.

## 单子实验 / Monoid experiments

以下命令不需要 Lean 或科学计算依赖，输出五组模型的精确有限覆盖曲线。
The following command needs neither Lean nor scientific dependencies and produces exact finite coverage curves for five models.

```bash
python scripts/reproduce_monoids.py
```

`A1` 用动态规划求最短加法表示，枚举到 65536；宏集合分别为 2 的幂、`2^(2^j)`、有限集合 `{2,5,13}` 和平方数。
For `A1`, dynamic programming finds shortest additive representations through 65536, using powers of two, `2^(2^j)`, the finite set `{2,5,13}`, or squares as macros.

对每个预算 `s`，覆盖半径是从 0 开始所有元素都能用至多 `s` 个生成元表示的最大整数；若枚举到边界仍没有反例，仅输出下界和 `right_censored=true`。
For each budget `s`, the coverage radius is the largest integer such that every element from 0 through it has a representation of length at most `s`; if no counterexample appears before the cutoff, the report gives only a lower bound and `right_censored=true`.

位值模型另有独立的进位边界公式作核对，平方数模型验证截至边界每个整数至多使用四个平方数。
The place-value model is cross-checked with an independent digit-boundary formula, and the square model checks that every integer through the cutoff uses at most four squares.

对于 `A_n` 中各坐标的 `b` 次幂宏，最短长度等于各坐标的 `b` 进制数字和；若 `s+1=q n(b-1)+r`，则精确覆盖半径为 `n(b^q-1)+r b^q-1`。
For coordinate-wise powers of `b` in `A_n`, shortest length equals the total base-`b` digit sum; if `s+1=q n(b-1)+r`, the exact coverage radius is `n(b^q-1)+r b^q-1`.

原因是首次需要 `s+1` 个数字单位的向量，会先填满所有坐标中较低的数位；该公式还与二、三维向量的独立穷举比较。
The first vector requiring `s+1` digit units fills the cheapest positions across coordinates first; the formula is also checked against independent exhaustive two- and three-dimensional vectors.

`F2` 保留字母顺序，使用同字母的幂串作为宏，枚举所有长度至多 12 的二元字符串；交替字符串仍需逐字表示，因此当前截断下的最坏长度等于原长度。
For `F2`, order is preserved and unary power strings serve as macros; all binary strings of length at most 12 are enumerated, with alternating strings still requiring one generator per character, so the observed worst-case length equals the original length.

结果在 [单子报告](../reports/monoids/summary.json) 和 [覆盖曲线](../reports/monoids/finite_coverage.csv)；这些是选定模型的有限检验，不是对所有多项式密度宏集合、概率构造或幂零单子的定理证明。
See the [monoid report](../reports/monoids/summary.json) and [coverage curves](../reports/monoids/finite_coverage.csv); these are finite checks of selected models, not proofs covering all polynomial-density macro sets, probabilistic constructions, or nilpotent monoids.
