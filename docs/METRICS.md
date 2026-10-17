# 指标与操作定义 / Metrics and operational definitions

## 测量对象 / Measurement object

评价的对象是 `(proposition, supplied proof, corpus, primitive boundary, representation, parameters)`，只给命题的自然语言句子不足以计算这些指标。
The evaluated object is `(proposition, supplied proof, corpus, primitive boundary, representation, parameters)`; a natural-language statement alone does not determine these metrics.

对于依赖图中的非原始节点 `u`，用 `w(u,v)` 表示在命题类型和证明体中引用 `v` 的总次数。
For a nonprimitive node `u`, let `w(u,v)` count occurrences of `v` in its signature and body together.

```math
U(u)=\sum_v w(u,v)U(v),\qquad U(g)=1\quad(g\text{ primitive}).
```

分别对命题类型及证明体求和，得到 `Us` 和 `Ub`；引用定理时，展开其类型与证明的合计长度，符合原文图模型。
Summing separately over signature and body references gives `Us` and `Ub`; a reference to a theorem expands its combined signature-and-body length, following the paper's graph model.

这一过程只做引用的递归代换，不做 beta 归约、自动寻找最佳定义、或最短证明搜索。
This recursively substitutes references; it does not perform beta reduction, search for optimal definitions, or find shortest proofs.

循环会使这种展开失去有限解释，因此本版拒绝带环数据；不会将环悄悄改成原始节点。
Cycles prevent a finite interpretation of this expansion, so this version rejects cyclic data instead of silently making the cycles primitive.

## 论文指标 / Paper metrics

以下为 [ABFM §5](https://arxiv.org/html/2603.20396v1#S5) 中的两项比值及其原始层级替代量。
These are the two ratios and the primitive-level alternative in [ABFM §5](https://arxiv.org/html/2603.20396v1#S5).

```math
T_0=\frac{U_s+U_b}{W_s+W_b},\qquad
I_0=\frac{W_b}{W_s},\qquad I_{\mathrm{primitive}}=\frac{U_b}{U_s}.
```

`references` 模式使 `Ws` 和 `Wb` 分别等于类型和证明中的引用次数；`source_tokens` 模式使用调用方提供的真实 token 数。
In `references` mode, `Ws` and `Wb` are signature and body reference counts; `source_tokens` mode uses the caller's actual token counts.

这两种口径不能混合进入同一语料，原始计数和口径会随报告一起输出。
These measurement conventions must not be mixed in one corpus, and the report includes both the raw lengths and their convention.

原始边界节点按约定取 `Ws=Us=1`、`Wb=Ub=0`；有类型而无证明体的公理不视为已经证明的命题。
Primitive boundary nodes use `Ws=Us=1` and `Wb=Ub=0` by convention; an axiom with a signature and no body is not treated as a proved proposition.

猜想的 `Wb` 和 `Ub` 为未知，`I0`、`T0`、综合分均为空；分母为零的比值也为空。
A conjecture has unknown `Wb` and `Ub`, so `I0`, `T0`, and its overall score are null; ratios with a zero denominator are also null.

## PageRank 与相对分 / PageRank and relative score

原文要求将两个指标归一化到可比尺度，但未给出唯一约定；本实现选择以下可审查的变换。
The paper calls for normalising the metrics to comparable scales without prescribing a unique convention; this implementation chooses the following auditable transformation.

```math
\widetilde T(u)=\frac{\log(1+T_0(u))}{\max_v\log(1+T_0(v))},\qquad
\widetilde I(u)=\frac{\log(1+I_0(u))}{\max_v\log(1+I_0(v))}.
```

最大值为零时，相应归一化分量取零；缺少完整内在指标或受 `sorry` 污染的节点不提供内在偏好证据。
If a maximum is zero, that normalised component is zero; nodes with incomplete intrinsic metrics or `sorry` taint supply no intrinsic preference evidence.

```math
J_0(u)=\beta\widetilde T(u)+(1-\beta)\widetilde I(u),\qquad
q(u)=(1-\epsilon)\frac{J_0(u)}{\sum_vJ_0(v)}+\frac{\epsilon}{N}.
```

若所有 `J0` 为零则使用均匀跳转；`epsilon=10^-12` 的显式平滑保证每个跳转概率为正。
If all `J0` values vanish, teleportation is uniform; explicit smoothing with `epsilon=10^-12` makes each teleportation probability positive.

依赖边从使用者指向被使用的声明，转移概率与重复次数成比例。
Dependency edges point from a user to the declaration it uses, and transition probabilities are proportional to multiplicities.

```math
\pi(v)=(1-\alpha)q(v)
+\alpha\sum_{u:W(u)>0}\pi(u)\frac{w(u,v)}{W(u)}
+\alpha q(v)\sum_{u:W(u)=0}\pi(u),\qquad I_1(v)=\pi(v).
```

最后一项明确处理了没有依赖的悬挂节点，将其质量按 `q` 再分配；否则概率会流失。
The last term handles dangling nodes explicitly by redistributing their mass according to `q`, so probability is conserved.

默认 `alpha=0.85`、`beta=0.5` 只是可修改的工程初值，并非作者验证过的最优参数。
The defaults `alpha=0.85` and `beta=0.5` are editable engineering choices, not author-validated optimal parameters.

程序输出收敛步数、平稳方程的 L1 残差和概率总质量，未收敛时拒绝输出评分。
The report includes iteration count, L1 stationary-equation residual, and total probability mass; failure to converge produces an error rather than a score.

综合分仅对具有完整指标、无已知 admission 污染且 `kind=theorem` 的节点计算。
The overall score is calculated only for nodes with complete metrics, no known admission taint, and `kind=theorem`.

```math
\operatorname{score}(u)=100\frac{\#\{v:I_1(v)<I_1(u)\}+\tfrac12(\#\{v:I_1(v)=I_1(u)\}-1)}{n-1}.
```

同分使用平均秩，单元素对照组约定为 50；浮点近似相等的判据在代码中固定，输出 `I1` 保留原始值。
Ties use midranks and a singleton cohort gets 50 by convention; floating-point tie tolerances are fixed in code, while raw `I1` is retained.

语料新增节点、边界改变、证明改写或参数改变都可能改变综合分，因此跨语料的分数不能直接比较。
Adding corpus nodes, changing boundaries, rewriting proofs, or changing parameters can alter the score, so scores from different corpora are not directly comparable.

## 后续论文的证明效率 / Proof efficiency from the follow-up

[BDF §3.4.1](https://arxiv.org/html/2604.06107v1#S3.SS4.SSS1) 按证明中所有命题的长度之和定义代价，再取最小值。
[BDF §3.4.1](https://arxiv.org/html/2604.06107v1#S3.SS4.SSS1) defines proof cost by summing statement lengths along a proof and then minimising it.

本实现接收显式的有限推理超图；每条规则的全部前提必须成立，多个规则构成备选证明。
This implementation accepts an explicit finite inference hypergraph; all premises of a rule must hold, and different rules provide alternative proofs.

```math
m_F(P)=\min\left(\{l(P):P\in A\}\cup
\left\{l(P)+\sum_{s\in r}m_F(s):r\Rightarrow P\right\}\right),\qquad
E_F(P)=m_F(P)/l(P).
```

未从公理或无前提规则建立的循环不会证明自身，无法导出时返回空值。
A cycle without an axiom or a premise-free rule cannot prove itself; underivability returns null.

该算法精确解决给定有限树证明空间的最小代价，但同一子证明被多次使用时重复计费；它既不是 DAG 共享子证明最优化，也不是遍历所有形式系统所得的普遍最小值。
The algorithm finds the exact minimum in the supplied finite tree-proof space, charging repeated subproofs repeatedly; it does not optimise shared-subproof DAGs or minimise over all formal systems.

`E_finite` 没有自动混入 `score`，因为两者使用的成本模型与对照对象不同。
`E_finite` is not automatically mixed into `score`, because their cost models and comparison objects differ.

## 已知解释限制 / Known interpretive limits

一个命题可以有多种证明，较差或刻意冗长的证明可能抬高 `I0`；本版并不声称识别了最优证明。
A proposition may have many proofs, and a poor or deliberately padded proof may inflate `I0`; this version does not claim to have identified an optimal proof.

数学兴趣还可能来自猜想的启发性、物理意义、概念生成能力与历史处境，这些未被当前指标完整捕获。
Mathematical interest may also come from a conjecture's suggestiveness, physical meaning, concept formation, and historical context, which the current metrics do not fully capture.

输出旨在提供可检验的研究信号，不能将启发式分位数理解为命题有价值的概率。
The output supplies testable research signals; its heuristic percentile is not a probability that a proposition is valuable.
