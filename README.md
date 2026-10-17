# MAAM · 命题数学兴趣指标计算器

输入一个有证明及依赖数据的形式命题，计算压缩、证明效率和结构用途，并给出可追溯的相对评分。
Evaluate a formal proposition using compression, proof efficiency, and structural usefulness, with a traceable relative score.

本项目根据 Freedman 参与的两篇论文实现研究用指标；目前发布的是可运行的 Python 计算核心，尚未完成全量 Mathlib 实验或人类兴趣标注验证。
This project implements research metrics from two papers coauthored by Freedman; the Python core runs, while full Mathlib replication and validation against human interest judgements remain unfinished.

## 快速运行 / Quick start

需要 Python 3.11 或以上，计算核心没有第三方依赖，也不调用 LLM 或外部服务。
The core needs Python 3.11 or later, has no third-party dependencies, and makes no LLM or external service calls.

```bash
python -m maam score --corpus examples/paper_simple_lemma.json --name simple_lemma --format text
python -m maam rank --corpus examples/toy_corpus.json --format text
python -m maam efficiency --system examples/finite_proofs.json --name D
python -m unittest discover -s tests -v
```

也可在虚拟环境中执行 `pip install -e .`，随后用 `maam` 替换 `python -m maam`。
You may also run `pip install -e .` in a virtual environment and use `maam` instead of `python -m maam`.

实际运行的论文小例子 `A ∧ B → B` 返回 `T0 = 1`、`I0 = 4/3`；只有一个对照命题时，相对分按约定为 50，不能据此声称它具有中等数学价值。
The paper's small example `A ∧ B → B` returns `T0 = 1` and `I0 = 4/3`; a singleton comparison cohort receives 50 by convention, which does not establish middling mathematical value.

## 计算什么 / What is calculated

令 `Ws, Wb` 为命题和证明的 wrapped 长度，`Us, Ub` 为递归展开后的原始引用数。
Let `Ws, Wb` be the wrapped statement and proof lengths, and `Us, Ub` their recursively expanded primitive-reference counts.

| 输出 / Output | 定义 / Definition | 来源与状态 / Attribution and status |
| --- | --- | --- |
| `T0` | `(Us + Ub) / (Ws + Wb)` | ABFM §5；约化压缩 / reductive compression |
| `I0` | `Wb / Ws` | ABFM §5；演绎压缩 / deductive compression |
| `primitive_proof_to_statement` | `Ub / Us` | ABFM §5 脚注中的替代量 / footnote alternative |
| `I1` | 压缩偏置的加权 PageRank 平稳分布 / compression-biased weighted PageRank stationary mass | ABFM §5.1；归一化等操作约定见下 / operational choices below |
| `E_finite` | `min Σ statement_length / target_statement_length` | BDF §3.4.1 的有限树证明版本 / restricted finite tree-proof version |
| `score` | `I1` 在合格定理中的 midrank 百分位 / midrank percentile of `I1` among eligible theorems | 本项目的展示约定，非论文标定分数 / MAAM presentation convention |
| `direct_users`, `user_domains` | 直接使用者数量和模块类别 / direct users and module labels | 结构描述量；不额外混入综合分 / descriptive only |
| `reuse` | 多目标证明节省减去定理构造成本 / multi-goal savings minus construction cost | 本项目扩展，不冒充论文指标 / MAAM extension |

默认 `references` 模式用内部表达式中的引用数度量 wrapped 长度，这是原文 §3.2 讨论的替代口径。
The default `references` mode measures wrapped length using internal-expression references, an alternative discussed in §3.2.

它与论文实证图表采用的源代码 token 计数不同，尤其会受到 `simp` 等策略展开的影响。
It differs from the source-token measurement used for the paper's empirical figures, particularly when tactics such as `simp` elaborate into large proof terms.

如已取得真实的命题和证明 token 数，可提供 `source_tokens` 语料；程序不会用内部引用数替代缺失的 token 数。
If actual statement and proof token counts are available, supply a `source_tokens` corpus; missing token counts are never replaced with internal-reference counts.

完整定义和操作约定见 [指标说明](docs/METRICS.md)，输入格式见 [数据说明](docs/DATA.md)。
See [metric definitions](docs/METRICS.md) for the operational conventions and [data documentation](docs/DATA.md) for input formats.

## 输入你自己的命题 / Evaluate your own proposition

已有四个长度时，可直接计算压缩指标。
If you have the four measured lengths, calculate the compression metrics directly.

```bash
python -m maam metrics \
  --signature-wrapped 10 --body-wrapped 90 \
  --signature-unwrapped 100 --body-unwrapped 9000
```

这会得到 `T0 = 91`、`I0 = 9`；没有对照语料和依赖图时，不生成虚假的 `I1` 或综合分。
This returns `T0 = 91` and `I0 = 9`; without a comparison corpus and dependency graph, it does not fabricate an `I1` value or overall score.

已有形式命题语料时，用声明名称评分，或批量排序。
For a formal corpus, score a declaration by name or rank the corpus.

```bash
python -m maam validate examples/toy_corpus.json
python -m maam score --corpus examples/toy_corpus.json --name Toy.StructuralLemma
python -m maam rank --corpus examples/toy_corpus.json --alpha 0.85 --beta 0.5
```

`query` 只匹配语料中存储的原文；它不负责把任意自然语言自动形式化，也不根据命题的名气打分。
`query` matches stored statement text exactly; it does not automatically formalise arbitrary natural language or assign scores based on a proposition's fame.

```bash
python -m maam query --corpus examples/paper_simple_lemma.json --statement 'A ∧ B → B'
```

未匹配的命题和未证明的猜想会返回缺少的证据与空分数，退出码为 2。
Unmatched statements and unproved conjectures return the missing evidence and a null score, with exit code 2.

## Lean 接口 / Lean adapter

适配器从已有 Lean 工程导出命题类型、证明体及带重复次数的依赖；已通过 GitHub Actions 上 Lean 4.24.0 的小命题端到端检查。
The adapter exports statement types, proof bodies, and dependency multiplicities from an existing Lean project; it passes the small-proposition end-to-end check on Lean 4.24.0 in GitHub Actions.

该检查包含真实证明导出、指标计算与 `sorry` 污染排除；它不代表全量 Mathlib 已经复现，证据见 [远程验证记录](results/remote_validation.json)。
The check covers actual proof export, metric calculation, and exclusion of `sorry` taint; it does not establish full Mathlib replication; see the [remote validation record](results/remote_validation.json).

```bash
python -m maam export-lean --project /absolute/path/to/mathlib4 \
  --module Mathlib --expand-prefix Mathlib --output data/mathlib.json
python -m maam score --corpus data/mathlib.json --name YourNamespace.yourTheorem
```

工具链、边界设置、局部导出偏差与测试步骤见 [Lean 接口说明](lean/README.md)。
See the [Lean adapter guide](lean/README.md) for toolchains, primitive boundaries, local-export bias, and smoke checks.

## 验证与复现状态 / Validation and reproduction status

执行以下命令生成确定性的演示语料、九组参数敏感性结果，以及每项复现目标的状态。
Run the following to generate deterministic demonstration corpora, nine parameter-sensitivity runs, and an explicit reproduction-status report.

```bash
python scripts/reproduce.py
python -m unittest discover -s tests -v
```

已提交的 [结果](results/) 来自实际运行，包含论文小例子、人工语料排序、有限证明效率以及未证明命题的处理。
The committed [results](results/) come from actual runs and cover the paper's small example, a synthetic ranking, finite proof efficiency, and handling of an unproved statement.

测试还将 PageRank 与独立的稠密线性方程求解器比较，将超图最小证明算法与独立松弛算法比较。
The tests also compare PageRank against an independent dense linear solver and the hypergraph minimum-proof algorithm against an independent relaxation solver.

这些检查验证算法实现；尚没有证据表明本项目的综合分与数学家对任意命题的兴趣判断一致。
These checks validate the implementation; they do not establish agreement between the overall score and mathematicians' interest judgements for arbitrary propositions.

全量 Mathlib token 图表、SCC 收缩、普遍最短证明复杂度及人类标注评估均未完成，详见 [复现状态](results/reproduction_status.json)。
Full Mathlib token plots, SCC condensation, universal minimum proof complexity, and human-label evaluation remain unfinished; see [reproduction status](results/reproduction_status.json).

## 论文与发布 / Papers and publishing

1. Vitaly Aksenov, Eve Bodnia, Michael H. Freedman, Michael Mulligan, [*Compression is all you need: Modeling Mathematics*](https://arxiv.org/abs/2603.20396v1), 2026，尤其是 §3 和 §5 / especially §§3, 5.
2. Maissam Barkeshli, Michael R. Douglas, Michael H. Freedman, [*Artificial Intelligence and the Structure of Mathematics*](https://arxiv.org/abs/2604.06107v1), 2026，尤其是 §3.4 和 §4.4 / especially §§3.4, 4.4.

第二篇是 Freedman 参与的相关后续框架文章，不应被描述为已有完善兴趣评分基准的实验论文。
The second is a related follow-up framework coauthored by Freedman, rather than an experimental paper with an established interest-scoring benchmark.

代码仓库为 [Love-in-idleness/MAAM](https://github.com/Love-in-idleness/MAAM)；克隆、开发与发布步骤见 [仓库使用说明](docs/PUBLISHING.md)。
The repository is [Love-in-idleness/MAAM](https://github.com/Love-in-idleness/MAAM); see the [repository guide](docs/PUBLISHING.md) for cloning, development, and publishing instructions.
