# 指标与操作定义

[English](METRICS.md)

## 测量对象

MAAM 评价的对象是六元组 `(proposition, supplied proof, corpus, primitive boundary, representation, parameters)`，仅凭自然语言命题无法计算这些指标。

对于依赖图中的非原始节点 `u`，记 `w(u, v)` 为 `u` 的命题类型与证明体中引用 `v` 的总次数：

```math
U(u) = \sum_v w(u, v)\,U(v), \qquad U(g) = 1 \quad (g \text{ 为原始节点}).
```

分别对命题类型与证明体求和得到 `Us` 与 `Ub`。引用定理时会展开其类型与证明体的合计长度，符合论文图模型。该过程只做递归引用代换，不做 beta 归约、最优定义搜索或最短证明搜索。

- 通用 JSON 语料接口拒绝含环数据。
- 独立的 Mathlib 全库复现管线按论文先收缩强连通分量（SCC），删除内部边、合并外部重数，并记录分量大小（这是图统计约定，不表示把递归程序展开成有限字符串）。
- 整包压缩计量（[COMPRESSED_PACKAGES.md](COMPRESSED_PACKAGES.md)）是使用规范 JSON 与标准库压缩器（`zlib`/`bzip2`）的独立工具，不替代下述论文指标。

## 论文指标（[ABFM §5](https://arxiv.org/html/2603.20396v1#S5)）

```math
T_0 = \frac{U_s + U_b}{W_s + W_b}, \qquad
I_0 = \frac{W_b}{W_s}, \qquad
I_{\mathrm{primitive}} = \frac{U_b}{U_s}.
```

- **长度口径**：`references` 模式以类型与证明体中的引用次数作为 `Ws`、`Wb`；`source_tokens` 模式使用调用方提供的源码 token 数。同一语料内不可混用。
- **边界与空值**：原始边界节点约定 `Ws = Us = 1`、`Wb = Ub = 0`；无证明体的公理不视为已证定理；猜想的证明长度为 `null`，故 `T0`、`I0` 与综合分为 `null`（分母为零时亦然）。

## PageRank 与相对分

内在指标经对数归一化（最大值为零时取零；指标不完整或受 `sorry` 污染的节点不提供内在偏好）：

```math
\widetilde T(u) = \frac{\log(1 + T_0(u))}{\max_v \log(1 + T_0(v))}, \qquad
\widetilde I(u) = \frac{\log(1 + I_0(u))}{\max_v \log(1 + I_0(v))}.
```

```math
J_0(u) = \beta\,\widetilde T(u) + (1 - \beta)\,\widetilde I(u), \qquad
q(u) = (1 - \epsilon)\,\frac{J_0(u)}{\sum_v J_0(v)} + \frac{\epsilon}{N}.
```

若所有 `J0` 为零则均匀跳转，并以 `epsilon = 10^-12` 平滑。依赖边从使用者指向被使用者，转移概率与引用重数成比例，悬挂节点质量按 `q` 再分配：

```math
\pi(v) = (1 - \alpha)\,q(v)
+ \alpha \sum_{u:\,W(u) > 0} \pi(u)\,\frac{w(u, v)}{W(u)}
+ \alpha\,q(v) \sum_{u:\,W(u) = 0} \pi(u), \qquad I_1(v) = \pi(v).
```

默认参数 `alpha = 0.85`、`beta = 0.5` 为可调工程初值。输出包含迭代步数、平稳方程 L1 残差与总质量，未收敛时直接报错。

相对分 `score`（0–100）仅对指标完整、无 admission 污染且 `kind = theorem` 的节点计算，同分取平均秩（单元素对照组为 50）：

```math
\operatorname{score}(u) = 100\,\frac{\#\{v : I_1(v) < I_1(u)\} + \tfrac{1}{2}(\#\{v : I_1(v) = I_1(u)\} - 1)}{n - 1}.
```

综合分随语料、边界、证明改写与参数变化，不可跨语料直接比较。

## 证明效率（[BDF §3.4.1](https://arxiv.org/html/2604.06107v1#S3.SS4.SSS1)）

对显式给定的有限推理超图（公理集 `A`、命题长度 `l`、规则 `r => P`）：

```math
m_F(P) = \min\left(\{l(P) : P \in A\} \cup \left\{l(P) + \sum_{s \in r} m_F(s) : r \Rightarrow P\right\}\right), \qquad
E_F(P) = \frac{m_F(P)}{l(P)}.
```

没有公理或无前提规则支撑的循环无法自证（不可导出时返回 `null`）。该算法在给定的有限**树证明**空间求精确最小值（重复子证明重复计费），并非 DAG 共享子证明最优化或全局形式系统最小值，也不会自动混入 `score`。

## 已知解释边界

- 静态指标不直接度量规格充分性、推广范围、AI 理解难度或未来复用价值。
- 依赖展开量不代表每次都需要重新学习全部前置理论；较长的模块化证明可能比更短的整体证明更易使用。
- 源码长度、内核证明项大小、引用树展开与共享声明账本属于不同成本模型，不可混淆。
- 冗长或较差的证明会抬高 `I0`；本工具不声称识别最优证明，启发式分位数仅作可检验研究信号，而非命题价值的概率。
