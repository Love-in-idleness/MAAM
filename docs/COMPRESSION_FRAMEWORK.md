# 数学对象、理论重构与分层压缩 / Mathematical objects, refactoring and layered compression

日期：2026-10-20；状态：理论设计与反例分析，尚非已实现的统一评价器，也未完成下述案例的 Lean 形式化。
Date: 2026-10-20; this is a theoretical design with counterexamples, not an implemented unified evaluator or a Lean formalization of these cases.

## 1. 研究方向与边界 / Research direction and limits

MAAM 应研究：在明确的数学基础、任务含义、知识背景和资源条件下，一个理论变化能否减少重复表达、组织共享论证、扩大可处理的问题范围，以及改善后续求证。
MAAM should study whether a theory change reduces repeated expression, organizes shared arguments, extends the problems it can handle, or improves subsequent proving under explicit foundations, task meanings, background knowledge and resources.

评价主体是具备广泛数学背景的 AI；理解难度指相对于其已有掌握的新增负担，通用理论的历史投入不对每个新对象重复收取，新包则按一次性投入与跨任务用途评价。
The subject is an AI with broad mathematical knowledge, evaluated through marginal demands and cross-task use while separating shared history from new acquisition.

这些效果不能由单个长度比值推断，也不必同时发生；评价结果应允许“某一方面改善、另一方面变差、未来用途未知”。
These effects need not occur together and cannot be inferred from one length ratio; an evaluation must allow improvement on one axis, deterioration on another, and unknown future usefulness.

[ABFM §5.2](https://arxiv.org/html/2603.20396v1#S5.SS2) 将动态选择定义列为未解决的问题；[BDF §4.4–4.6](https://arxiv.org/html/2604.06107v1#S4.SS4) 讨论重构、扣除抽象成本的语料重写收益及后续任务表现。
Those sources motivate this investigation, but the semantic contracts, accounting rules and acceptance cases below are MAAM proposals rather than results established by those papers.

“新证明严格更短才替换旧证明”继续作为当前源码证书的采用策略；较长证明可能在首次理解时就有收益，也可能提供可复用引理，推广命题则作为新节点保留。
Strict shortening governs current source-certificate adoption, while longer proofs can improve immediate comprehension or reuse and generalizations remain separate statements.

## 2. 首先区分评价的对象 / Distinguish the evaluated objects

一次评价先声明背景 \(\mathcal C=(F,K,\mathcal E,Q,\mathcal B)\)：\(F\) 是逻辑基础与公理，\(K\) 是允许免费使用的共同背景，\(\mathcal E\) 是表示和计量规则，\(Q\) 是目标及其含义，\(\mathcal B\) 是搜索条件与资源范围。
An evaluation fixes foundations \(F\), common background \(K\), representation and measurement rules \(\mathcal E\), goals and their meanings \(Q\), and search conditions and resources \(\mathcal B\).

“免费背景”仅指本次增量账本不重复收取共同历史成本；AI 是否掌握及能否检索这些理论需另行记录，具体行为比较还须冻结模型与记忆状态。
Common background is free only of repeated historical acquisition charges, while operational familiarity, retrieval and current use remain separate conditions.

| 对象 / Object | 需要保留的内容 / Required information |
| --- | --- |
| 显式定义 / Explicit definition | 名称、类型、定义体、依赖与计算规则 / Name, type, body, dependencies and computation rules |
| 公理化规格 / Axiomatic specification | 允许哪些对象、操作、条件及观察方式 / Objects, operations, conditions and observable behavior |
| 实现或实例 / Implementation or instance | 具体对象 \(C\) 及其满足规格的证书 \(h_C:A(C)\) / A concrete object and its specification certificate |
| 存在与唯一性 / Existence and uniqueness | \(\exists X,A(X)\)，以及按指定相等或同构意义的唯一性 / Existence and uniqueness under a specified equality or isomorphism |
| 命题 / Proposition | 参数、假设、量词、对象表示与结论 / Parameters, assumptions, quantifiers, representations and conclusion |
| 证明 / Proof | 某个命题的一个已核验证书及实际依赖 / One checked certificate and its actual dependencies |
| 搜索过程 / Search process | 尝试、失败、模型与工具设置、资源消耗 / Attempts, failures, model and tool settings, resource usage |
| 理论包 / Theory package | 相互配合的定义、定理、实例、算法和桥接 / Cooperating definitions, theorems, instances, algorithms and bridges |

因此，构造不直接“变成一个命题”：构造仍提供对象，另有证明说明它满足新规格，再由该实例推出存在性命题。
The construction continues to supply an object; a separate certificate verifies the new specification, and that instance then witnesses an existence proposition.

数学上不区分同一命题的证明，并不妨碍项目区分证明的长度、依赖、可计算内容和找到它的成本。
Mathematical identification of proofs of one proposition does not identify their representations, dependencies, computational content or discovery costs.

目前 `maam/corpus.py` 中的声明种类和引用边不足以承载上述全部关系；新增分类首先是设计要求，不能宣称现有节点分数已经评价了这些方面。
The current corpus kinds and reference edges do not represent all these relationships, so these distinctions are design requirements rather than capabilities already supplied by node scores.

## 3. “含义相同”不能只检查逻辑等价 / Logical equivalence alone is insufficient

若 \(p:P\) 与 \(q:Q\) 都已证明，则 \((\lambda\_ .q,\lambda\_ .p)\) 就给出 \(P\leftrightarrow Q\)，即使两者讲述完全不同的数学事实。
If both propositions are proved, maps that ignore their inputs establish their equivalence, even when the propositions express unrelated mathematical facts.

所以，任意一个 `iff` 证书只证明逻辑关系，不能单独作为“同一任务”“同一定义”或“同一概念”的身份判据。
An arbitrary equivalence certificate establishes a logical relation but cannot by itself identify a task, definition or concept.

项目需要固定原任务的参数、数据、操作、假设与待证明结论，再给出逐项对应的解释及结果回传；允许的转换模板须事先约定或另行审查，并核验其证书与依赖。
The project needs a fixed contract for inputs, operations, assumptions and the requested conclusion, together with an explicit interpretation and result transport whose template and dependencies are audited.

对于函数接口，可以要求输入对应后输出相等；对于不同载体的代数结构，可以要求同构保持有关运算，并逐项运输目标性质；计算任务还要检查算法、可执行性与约定的资源性质。
Function interfaces can require equal outputs on corresponding inputs, while changed carriers can require operation-preserving isomorphisms and property transport, with additional obligations for computational tasks.

定义展开即可识别的相等、需要证明的相等与同构有不同使用成本；若存在多条运输路径，还须说明它们在任务要求的观察上是否一致。
Definitional equality, proved equality and isomorphism have different operational costs, and multiple transport paths may require coherence on the observations demanded by the task.

不能把待评估目标的旧答案预先藏进免费的 \(K\)，再通过别名调用宣布压缩；若新证明调用旧证，应把该旧证作为实际依赖计入相应成本。
An archived answer must not become a free oracle for its own evaluation; when a candidate calls that answer, its proof belongs in the relevant dependency cost.

这些限制提供可审查的局部判据，不声称一般数学语义存在自动且完备的判定算法。
These are auditable local criteria, not a claim of an automatic complete decision procedure for mathematical meaning.

## 4. 定义整理发生在哪一步 / When refactoring happens

| 阶段 / Stage | 可进行的工作 / Permitted work | 收益归属 / Attribution |
| --- | --- | --- |
| 旧工具准备 / Old-tool preparation | 仅依靠已有定义、引理和自动化进行整理 / Refactor using existing definitions, lemmas and automation | 旧工具优化 / Old-tool improvement |
| 冻结基线 / Baseline freeze | 固定原目标、表示对应、背景、证书与核算口径 / Fix goals, interpretations, background, certificates and accounting | 比较起点 / Comparison starting point |
| 加入新包后 / After introducing a package | 使用新规格、一般理论、实例与桥接 / Use new specifications, general theory, instances and bridges | 包相关变化及其完整成本 / Package-associated change and complete cost |
| 后续观察 / Subsequent observation | 两边获得匹配的继续搜索机会，观察新的用途 / Match continued search and observe subsequent uses | 有条件的后续效果 / Conditional subsequent effects |

依赖新理论才能表达或证明的重构，属于加入新包之后；不能提前送给对照组，也不能把本可用旧工具完成的整理全部归给新包。
Refactoring enabled by the new theory belongs after its introduction, while improvements already available from old tools belong to baseline preparation or matched continued search.

“已有条件下相对简短”只能表示在声明的方法和资源内已完成搜索，不能表示一般 Lean 证明已经全局最短。
Relative brevity means that the declared search scope has been completed, not that general Lean proofs are globally minimal.

## 5. 实数：规格、实现与存在性 / Reals: specification, implementation and existence

设原构造给出具体实数结构 \(C\)，新包提出规格 \(A(X)\)，则保留 \(C\)，新增 \(h_C:A(C)\)、存在性 \(E:\exists X,A(X)\)，并在需要时另证唯一性和表示转换。
Keep the concrete construction, add its specification certificate and the resulting existence theorem, and prove uniqueness and representation transport separately when required.

“有序域加一个完备一致空间结构”本身还不足以刻画实数：有理数域配上离散一致结构也是完备的，因为其柯西滤子必须包含单点集。
An ordered field with an arbitrary complete uniform structure does not characterize the reals, as the rationals with the discrete uniformity provide a counterexample.

必须说明这些结构如何相容及采用哪种完备性；例如可选择 Dedekind 完备有序域的规格，并使用相应[唯一性定理](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Algebra/Order/CompleteField.html)，而不能把不同完备性条件悄悄互换。
Specify compatibility and the exact completeness notion, such as a Dedekind-complete ordered field, rather than exchanging distinct completeness conditions without proof.

若一个一般定理为 \(\forall X,\ A(X)\to T(X)\)，其证明不必依赖 \(E\)；应用于原实数时通常只需 \(C\) 和 \(h_C\)，具体引用决定依赖账本。
A theorem conditional on an abstract structure need not use its existence theorem, and its concrete application may require only the construction and instance certificate.

若另行从存在性选择抽象实数对象，还要记录选择所用的基础、与 \(C\) 的同构及计算行为；可继续让 \(C\) 作为实现而通过新接口工作，避免无收益的全库迁移。
Choosing a separate abstract realization creates obligations about foundations, isomorphism and computation, whereas retaining the existing realization behind the new interface can avoid unnecessary migration.

存在性命题放在新规格的实例或实现部分，依赖指向原构造及新验证；文件位置或声明类别改变，不会让构造成本消失，也不会凭空产生数学收益。
The existence theorem belongs with the specification's realization evidence, with dependencies on its construction and verification, regardless of its file location or declaration category.

## 6. 行列式：同一函数的不同角色 / Determinants: different roles of one function

令 \(R\) 为含幺交换环，\(n\) 为正整数，固定 \(R^n\) 的有序标准基 \(e_1,\ldots,e_n\)，规格要求 \(d:(R^n)^n\to R\) 多线性、交替且 \(d(e_1,\ldots,e_n)=1\)。
Over a commutative unital ring with an ordered standard basis, specify a multilinear alternating map normalized to one on that basis.

这里“交替”指两个输入相同时取零；只要求交换两个输入变号，在特征为二的环上不足以替代这一条件。
Alternation means vanishing on repeated inputs, and skew symmetry alone is insufficient in characteristic two.

原莱布尼兹表达式记为 \(D(v_1,\ldots,v_n)=\sum_{\sigma\in S_n}\operatorname{sgn}(\sigma)\prod_i(v_i)_{\sigma(i)}\)，它继续提供具体函数及求值公式。
The Leibniz expression remains the concrete function and its evaluation formula.

| 内容 / Content | 加入公理化规格后的角色 / Role after specification |
| --- | --- |
| 莱布尼兹公式 \(D\) / Leibniz formula | 实现与计算表达式 / Implementation and computational expression |
| \(h_D:A(D)\) | 多线性、交替、归一化的验证 / Verification of the specification |
| \(\exists d,A(d)\) | 由 \(D,h_D\) 给出的存在性 / Existence witnessed by the implementation |
| \(A(d)\Rightarrow d=D\) | 唯一性及与旧公式的一致性 / Uniqueness and agreement with the old formula |
| 一般性质 / General properties | 尽量通过抽象规格证明，再应用到 \(D\) / Prove through the specification and instantiate at \(D\) |

唯一性的直接论证是把每个 \(v_i\) 按标准基展开，再用多线性展开；交替性消去重复基向量项，剩余排列项由符号与归一化确定，正好得到莱布尼兹公式。
Expand each input in the basis, eliminate repeated basis indices by alternation, and use normalization and permutation signs to recover exactly the Leibniz formula.

此处载体及输入输出相同，可以证明函数相等；若改用一般有限自由模，标量形式还涉及基的选择，不能把 \(R^n\) 的接口原封不动搬到任意模。
Here the maps have the same domain and codomain and can be equal as functions, while extending the interface to general modules requires further structure and explicit hypotheses.

Mathlib 同时提供排列求和定义、交替映射形式与基上的行列式性质，可作为这种并存方式的参考，而不是本项目已经完成迁移的证据。
See Mathlib's [matrix determinant](https://leanprover-community.github.io/mathlib4_docs/Mathlib/LinearAlgebra/Matrix/Determinant/Basic.html) and [basis determinant](https://leanprover-community.github.io/mathlib4_docs/Mathlib/LinearAlgebra/Determinant.html) documentation for these complementary interfaces.

反例：在 \(\mathbf F_2^2\) 上，\(f(v,w)=\det(v,w)+v_1w_1\) 双线性、交换输入变号且 \(f(e_1,e_2)=1\)，但 \(f(e_1,e_1)=1\)，所以它不是所需行列式。
This normalized bilinear skew-symmetric map in characteristic two fails alternation, making it a concrete rejection case for an incomplete specification.

含求和符号的公式可以很短，而直接枚举仍有 \(n!\) 项；源码长度、展开长度、实际算法和运行成本应分别测量。
A compact summation can encode factorially many terms, so source size, expansion size, algorithm choice and execution cost are separate quantities.

## 7. Cayley–Hamilton 与行列式技巧 / Cayley–Hamilton and the determinant trick

交换环上的矩阵命题 \(\chi_A(A)=0\) 应作为新命题保留，域上有限维线性空间的旧命题也保留，通过选基及把域视为交换环建立特化关系。
Keep both the commutative-ring matrix theorem and the finite-dimensional vector-space theorem, connecting them through specialization and the required representation bridge.

这里的推广是对象范围扩大；只有原目标的经核验替代证明确实更短时，才更新该目标的选用证明。
Broader scope is a separate achievement, and it changes the selected proof of an existing goal only when the checked alternative is strictly shorter.

对有限生成 \(R\)-模 \(M\) 的自同态 \(\varphi\)，行列式技巧给出某个首一多项式 \(p\) 使 \(p(\varphi)=0\)；若 \(\varphi(M)\subset IM\)，可使其第 \(j\) 个系数属于 \(I^j\)。
The finite-module annihilating-polynomial statement and its ideal-sensitive version are recorded in [Stacks, Lemmas 10.16.2–10.16.3](https://stacks.math.columbia.edu/tag/05G6).

这不等于给每个有限生成模的自同态都定义了规范的特征多项式；由生成元及提升矩阵得到的多项式可能依赖这些选择。
An annihilating polynomial obtained from generators and a lifting matrix does not automatically define a canonical characteristic polynomial on every finitely generated module.

可直接检查的推导是：取生成元 \(m_i\)，写 \(\varphi(m_i)=\sum_j a_{ij}m_j\)，把 \(M\) 看成 \(T\) 按 \(\varphi\) 作用的 \(R[T]\)-模，则 \((TI-A)m=0\)，乘伴随矩阵得 \(\det(TI-A)m=0\)。
Using the polynomial-module action makes the adjugate argument legitimate; when the matrix entries lie in \(I\), the coefficient containing \(j\) such entries lies in \(I^j\).

此论证避免把一般矩阵多项式的“代入矩阵”误当作无条件的环同态；若 \(\varphi=x\,\mathrm{id}\)，所得是 \(p(x)M=0\)，进一步断言 \(p(x)=0\) 需要例如 \(M\) 忠实这样的额外条件。
Polynomial annihilation of a module is weaker than equality in the coefficient ring, and faithfulness is one sufficient condition for the latter inference.

范围确实扩大的证据可以使用 \(\mathbb Z\) 或 \(\mathbb Z/4\mathbb Z\) 这样的非域实例，但不把“包含无限多个新实例”换算为无限收益。
Nonfield examples witness genuine additional scope, while quantitative coverage must use a declared finite task family or distribution.

一般定理、特化证明、行列式技巧与旧证明有不同依赖及用途，需保存各自节点；新一般定理若利用了旧域上定理证明，也必须保留这条反向的证明依赖。
Semantic specialization and actual proof dependence are different relations and may point in opposite directions, so they must not be conflated.

例如，一般定理若使用旧特例的原证，再把该特例的选用证明改成调用一般定理，不能同时让一般定理的依赖自动改指这个新版本；必须保留原证依赖并计费，否则会形成循环论证。
If the general proof uses the old specialized certificate, replacing that certificate by a call to the general theorem requires preserving the original dependency version, or the resulting library becomes circular.

## 8. 1000 与 10×120：当前理解和后续使用 / Present comprehension and subsequent use

对已经掌握有关通用理论的 AI，1200 的结构化证明可以在首次接触这个证明时就比 1000 的整体证明更容易处理，因为模块可能减少需要协调的条件和中间结论。
For an AI familiar with the supporting theories, a longer structured proof can reduce coordination demands on first encounter.

需要测量条件辨认、整体拼装和新问题上的应用，只对尚未掌握的模块计入新增获取成本；论证、论文和跨任务摊销见[AI 理解成本](COGNITIVE_COMPRESSION.md)。
Measure applicability, integration and transfer, charging acquisition for unfamiliar components under the conditional AI framework.

分段和解释也可能改善呈现，即使没有新导出的形式引理；语义模块与可复用引理提供的是进一步可能性，不能只按段落数自动奖励。
Presentation changes can help without new formal lemmas, while semantic modules and reusable interfaces require their own evidence beyond block counts.

在源码轴上，仍应确认 1200 包含完整陈述、假设、证明和最终拼装，并按当前严格缩短策略保留 1000 的选用证书；AI 理解与使用可以另选较长接口。
The source ledger and certificate policy remain separate from the preferred interface for AI comprehension and use.

源码复用的账本也单独保留：若 1000 原证仍被选用且额外加入全新 1200 模块，则组合为 2200，后续源码节省应回收实际新增成本，不能直接假定投入只有 200。
Future source savings must repay actual incremental costs, which can differ from the difference between two alternative portfolios.

例如，实际新增成本为 200、每次后续净省 60 时，四次净省 40；新增成本为 1200 时二十次才打平，这些假设数字不用于计算理解难度。
These illustrative break-even calculations concern source accounting, while comprehension needs its own measurements.

## 9. 200 与 100：定义的长度不是概念复杂度 / Definition length and conceptual complexity

这里固定相同依赖和前置知识：200 的书写长度是 100 的两倍，但需要同时协调的关系、隐含推理与量词结构可能造成非线性理解负担。
Under equal dependencies and prerequisites, relational and inferential demands can produce nonlinear comprehension costs despite the simple length ratio.

增加内容若带来更高的耦合，理解可能远不止难两倍；增加内容若提供解释和有意义的分块，也可能使较长版本更易理解，因此不能把难度设为仅依赖长度的函数。
Additional coupling can make comprehension disproportionately harder, while explanation and meaningful organization can make longer material easier.

[AI 理解成本说明](COGNITIVE_COMPRESSION.md)将已有掌握、模型状态、目标、交互关系和接口纳入评价，比较固定资源下的可靠性及达到指定掌握要求的资源量，具体非线性形式待检验。
The AI note conditions outcomes on operational knowledge and compares reliability and resources without prescribing a power law.

依赖与展开成本继续单列，但不能代替相同背景下的 AI 行为测量；通用理论的统摄力通过不同任务族的组合与迁移考察，不将全部基础知识展开成本算作每次理解负担。
Expansion costs do not measure AI understanding, and broad theory is assessed through diverse uses without repeatedly charging shared foundations.

## 10. 哪些层面的压缩可以计算 / Measurable layers of compression

| 层面 / Layer | 量及核算方式 / Measurement | 不能据此断言 / Unsupported conclusion |
| --- | --- | --- |
| 表达压缩 / Expression | 固定编码下的类型、定义体、证明体及模块总长 / Signature, body and module lengths under a fixed encoding | 短表达必然更易懂 / Shorter implies easier understanding |
| 共享压缩 / Sharing | 新增声明及其依赖的去重成本，整包计一次 / Distinct new declarations and dependencies, charging the complete package once | 逐题最短之和就是全库最优 / Local minima imply a global library optimum |
| 推导压缩 / Derivation | 核证明项大小、指定边界的引用展开量、有限规则证明成本，分别列出 / Certificate size, reference expansion and finite-rule proof costs separately | 任一展开量就是执行时间 / Expansion size equals execution time |
| 规格与命题族压缩 / Specifications and families | 一般陈述及证明，加选定实例的特化和回传成本 / General statement and proof plus selected instance bridges | 更一般就必然更短 / Generality guarantees brevity |
| 搜索资源改善 / Search resources | 固定任务和条件下的解决覆盖、尝试量、生成用量及检查时间 / Coverage, attempts, generation usage and checking time | 一次失败就是没有短证 / One failure proves no short proof exists |
| 后续复用 / Subsequent reuse | 随任务到来的累计净收益、额外解决的目标与成本曲线 / Cumulative net savings, additional solved goals and costs over subsequent tasks | 少量用途就预测无限未来 / A few uses predict unlimited future value |
| AI 理解与稳健性 / AI comprehension and robustness | 广泛背景下的条件性掌握、资源、组合与跨领域迁移，新增获取成本计一次 / Conditional competence, resources, composition and transfer, with acquisition charged once | token 数等于难度；统摄力或库中存在等于已掌握 / Tokens, generality or library presence automatically establish difficulty or mastery |

前四项涉及不同表示层面的描述成本，搜索与理解还涉及 AI 的行为；使用“压缩”一词时必须指明具体测量层面。
Description costs and AI outcomes require separate operational definitions and evidence.

### 10.1 声明与共享依赖的成本 / Declaration and dependency cost

给定已选证明组合 \(\Pi\)，令 \(D(\Pi,P)\) 包含这些证明、完整候选包 \(P\)、必要桥接和辅助声明，以及它们的实际传递依赖；声明以版本身份去重，同文异义的声明不可仅按文本合并。
Let \(D(\Pi,P)\) contain selected proofs, the entire package, required bridges and helpers, and their transitive dependencies, deduplicated by declaration identity and version rather than text alone.

在冻结编码 \(\mathcal E\) 下，定义供后续实现审查的账本：
The proposed ledger under the frozen encoding is:

```math
L_{K,\mathcal E}(\Pi,P)
  = O_{\mathcal E}(\Pi,P)
  + \sum_{d\in D(\Pi,P)\setminus K}\ell_{\mathcal E}(d).
```

其中 \(\ell\) 包括声明的类型与定义或证明体，\(O\) 包括尚未计入的导入、命名空间、模块包装等实际开销，避免把同一内容分别藏在两处或重复收费。
Declaration cost includes type and body, and \(O\) accounts for remaining actual module overhead without omitting or double-charging content.

研究档案保留所有旧证、候选和失败，评价组合只选择指定证书及实际所需依赖，档案存储另列；如果旧证仍是当前选择而新模块也被使用，两者都进入组合。
Archive storage is separate from the selected portfolio, but a retained selected proof and any additionally used modules both belong in that portfolio.

包中没有用到的内容也按当前整包政策计入；若以后评价裁剪包，必须建立新版本，不能只在结算时免掉未使用部分。
Unused package declarations remain charged under the current whole-package policy, and pruning requires a separately versioned candidate.

共同背景只有在两边相同且确属预先可用时才能抵消；需要同时列出绝对账本和背景指纹，防止仅靠改变边界制造收益。
Common background cancels only when it is genuinely identical and previously available, with absolute ledgers and background fingerprints exposing boundary changes.

这是新的理论核算定义，尚未实现为一般 Lean 库的共享优化器；当前逐模块 `source_tokens` 账本仍按原规则解释，不能直接改算并覆盖冻结报告。
This proposed general ledger does not replace the current module-token convention or establish an implemented shared-library optimizer.

### 10.2 同一目标集上的净压缩 / Net compression on the same goals

对预先固定且两边都有合格证书的目标组合 \(Q\)，分别给出完整成本 \(L_{\mathrm{old}}\) 与 \(L_{\mathrm{new}}\)，净节省为 \(S=L_{\mathrm{old}}-L_{\mathrm{new}}\)，当 \(L_{\mathrm{old}}>0\) 时才定义比例 \(S/L_{\mathrm{old}}\)。
Compare complete costs on the same certified goals, report their difference, and use a relative saving only with a positive baseline denominator.

全部预定目标的成功、失败及未尝试状态同时保留；共同成功子集的成本比较是条件结果，不能抹去其余目标的覆盖差异。
Keep every scheduled goal's outcome, because cost comparisons on the commonly solved subset are conditional and do not replace coverage reporting.

若只是把一段构造从定义文件移到存在性证明的依赖中，在编码和开销不变时，上式的依赖集合与总成本不变；产生桥接后则增加桥接的实际成本。
Moving a construction between files or roles preserves its ledger cost when the declaration contents and overhead are unchanged, and added bridges incur their actual costs.

这条重定位性质只约束账本，不声称任意公理化前后成本必相等，因为真正重构可能改变定义、共享方式和证明。
This relocation property concerns accounting, while substantive refactoring can change definitions, sharing and proofs.

### 10.3 树证明、共享证明与已发现的最短证明 / Trees, sharing and observed minima

树计费会把同一子证明的两次使用重复计费，共享图则保存一次证明并支付调用开销；二者回答不同问题，必须在结果中写明。
Tree costs repeat a reused subproof, whereas shared representations store it once and pay reference overhead, so their meanings differ.

当前 `E_finite` 在给定有限规则及树成本内求精确最优，不能作为共享图或一般 Lean 搜索的最优性证书。
The current finite solver is exact only for its supplied tree-proof model, not for shared graphs or unrestricted Lean search.

一般搜索记录的是 \(m_{\mathrm{found}}(q)=\min_{\pi\in\text{已核验候选池}(q)}L(\pi)\)，它是相应真正最小值的上界；若候选池为空，则未知，不能填零。
The best checked candidate gives an upper bound on the corresponding optimum, and an empty candidate pool gives an unknown value rather than zero.

多个目标共享辅助引理时，单题各自选最短证明未必使总库最短，因此既保留当前严格缩短策略，也明确它没有解决联合优化。
Independent shortest-proof selections need not minimize a shared library, so the current adoption policy must not be advertised as joint optimization.

### 10.4 推广与命题族压缩 / Generalization and family compression

“更一般”需要逐项解释原对象如何成为新对象的特例、原假设如何满足新假设、原结论如何由新结论得到，而不是仅给两个已证命题之间的蕴涵。
Generality requires a structural specialization of objects, hypotheses and conclusions, rather than an arbitrary implication between proved propositions.

对指定有限命题族 \(\{q_1,\ldots,q_m\}\)，比较独立陈述及证明的共享账本，与一般定理加这些实例和回传证书的共享账本；不能把无限多潜在实例当作已经节省的证明。
Compare a declared finite family's complete ledger with a general theorem and its instance bridges, without treating infinitely many potential instances as realized savings.

适用范围扩大还需要非空且超出旧条件的实例证据；只添加无关参数、复制任务或把假设变得矛盾，不获得范围收益。
Additional scope needs inhabited cases outside the former conditions, and irrelevant parameters, duplicated tasks or inconsistent hypotheses provide no such evidence.

### 10.5 后续复用与发展潜力 / Subsequent reuse and development potential

在声明的后续任务序列 \(Q_{1:N}\) 上，记录 \(S_N=L_{\mathrm{old}}(Q_{1:N})-L_{\mathrm{new}}(Q_{1:N})\)，每个前缀的账本均计入完整引入成本一次，再观察收益何时转正及是否稳定。
Use cumulative ledgers that charge setup once for each evaluated prefix, then observe break-even and stability as subsequent tasks arrive.

若任务按预先规定的分布 \(\mu\) 抽样，可报告 \(\mathbb E_\mu[S_N]\) 的估计及不确定性；没有合理分布和样本时，只报告情景分析与已观察用途。
Expected future savings require a specified task distribution and uncertainty estimates, otherwise report scenarios and observed uses.

新增可解决的问题应另列覆盖及资源成本；未找到旧证明不代表旧理论不能证明，也不能把未知旧成本当作无穷来制造无限收益。
Newly solved tasks require separate coverage reporting, since failure to find an old proof establishes neither impossibility nor an infinite saving.

近重复任务应按事先确定的结构族分组和赋权，并使用未参与造包的新任务检查复用，避免用复制题目或回看答案增加价值。
Freeze task-family grouping and weights and assess reuse on fresh tasks to prevent duplication and answer leakage from inflating value.

## 11. 如何综合评价 / Combining the measurements

先检查证书、基础假设、目标对应与完整成本是否合格，再比较结果；证明正确不能弥补题目被换掉，源码较短也不能弥补增加未经证明的公理。
Check certificates, foundations, goal interpretations and complete costs before comparing outcomes, since correctness and brevity do not excuse changed tasks or unproved assumptions.

一个候选的结果首先是带条件的记录，而非单个分数：
A candidate first receives a contextual record rather than one score:

```text
context: foundations, background, encoding, goals, search conditions
evidence: certificates, semantic bridges, dependencies, provenance
costs: source, certificate size, expansion, search usage, checking time
coverage: original goals, additional goals, certified specialization
development: cumulative reuse, fresh task families, observed stability
comprehension: broad background, AI state, competence, integration, transfer
acquisition_and_use: one-time setup, conditional use costs, task families, horizon
unknowns: uncalibrated cognitive predictions, unexplored uses, uncertain costs
```

在相同上下文、相同覆盖及可比测量下，一个候选若所有声明比较的成本都不高且至少一个更低，才在这些轴上支配另一个；各有优劣则保留不可比。
Under matched context and coverage, a candidate dominates on the declared cost axes only when it is no worse on every axis and strictly better on at least one.

范围关系可以另给结构化特化证书，未知的未来收益仍为未知；不能把非数字关系或缺失量强制塞入同一数值偏序。
Structural scope relations and unknown future outcomes remain explicit rather than being coerced into numeric costs.

具体工程决策可以采用“保持目标覆盖和验证时间上限，最小化完整源码成本”这类约束优化；若使用加权总分，权重、单位换算和任务偏好必须预先说明并做敏感性检查。
Operational decisions can minimize a declared cost under constraints, while weighted scores require explicit units, preferences and sensitivity checks.

同一效果在源码长、展开比和图中心性中重复出现时，不应当作三份独立证据相加；跨语料重新归一化的分位数也不代表同一概念增加了多少价值。
Correlated indicators are not independent evidence, and renormalized ranks from different corpora do not measure a concept's value increase.

存在性、抽象定理和实例可能相互补充，单独使用都无效而联合有效；先评价整体，再用移除组件的对照研究条件贡献。
Existence certificates, general results and instances may be complementary, so assess the joint package before conditional component ablations.

移除组件时还要移除依赖它的缓存定理和自动化规则，否则“没有该组件”的对照仍偷偷使用它；各贡献通常不能唯一地加总成概念的固有价值。
An ablation must also exclude dependent cached results and automation, and interacting contributions do not generally have a unique additive attribution.

## 12. 还需避免的误判 / Further failure modes

| 问题 / Issue | 设计要求 / Design requirement |
| --- | --- |
| 类型相同但规格不足 / Incomplete specification | 核对交替、归一化、完备性相容等必要条件 / Check all defining conditions and compatibility |
| 逻辑等价塌缩 / Equivalence collapse | 保留原任务的结构和含义，不能合并所有已证命题 / Preserve the task contract rather than merging all proved facts |
| 证明无关性与成本混淆 / Proof identity versus cost | 同一命题保留多种证书及其各自成本 / Keep distinct certificates and costs |
| 计算内容丢失 / Lost computation | 区分存在证明、可执行构造、求值公式与复杂度保证 / Separate existence, executable construction, evaluation and complexity |
| 依赖方向混淆 / Conflated relations | 使用依赖、特化、同构、实例和版本来源分别记录 / Distinguish use, specialization, isomorphism, instance and provenance |
| 包装与命名作弊 / Wrapping and naming artifacts | 显式计入别名及实现成本，固定词法计量规则 / Charge aliases and implementations under fixed lexical rules |
| 分步与重复作弊 / Splitting and duplication | 不按步骤数、重命名题数或节点数直接奖励 / Do not reward raw step, renamed-task or node counts |
| 背景或公理漂移 / Drifting foundations or background | 固定依赖闭包、公理与自动化，变更另建比较 / Freeze dependencies, axioms and automation |
| 泛化导致原目标消失 / Lost original goals | 保留原命题及证书，新增一般命题与特化 / Retain original goals and add a generalization with specialization |
| 实验成功被当作理论必然 / Overinterpreted experiments | 分开有限模型结论、Lean 证书、模型实测和价值假说 / Separate finite results, checked proofs, observed runs and value hypotheses |
| 搜索能力与概念价值混淆 / Search versus concept | 保存搜索计划、失败与资源，区分未发现和不存在 / Record search conditions and distinguish unfound from impossible |
| AI 理解被代理指标替代 / Unvalidated comprehension proxy | 固定广泛背景与 AI 状态，结构指标须由独立行为评价验证 / Condition on broad knowledge and validate proxies against behavior |

定义作为缩写、规格作为接口、一般化作为覆盖扩展，并不是同一种改变；它们可以同时出现，但每一项都需要自己的证据。
Abbreviation, interface specification and generalization are distinct changes that may coexist but require distinct evidence.

## 13. 后续工具必须通过的反例 / Acceptance cases for later tools

以下是设计层面的预期行为，不是声称现有程序已经具备这些检查。
These are design-level expected outcomes, not claims that the current software implements every check.

| 编号 / ID | 输入变化 / Change | 必须得到的结论 / Required conclusion |
| --- | --- | --- |
| A01 | 两个不相关已证命题之间构造 `iff` / An arbitrary equivalence between proved facts | 不能仅据此合并任务 / Insufficient for task identity |
| A02 | 构造改放到存在性证明的依赖文件 / Move a construction behind existence evidence | 实现成本保留，新增桥接另计 / Retain construction cost and charge new bridges |
| A03 | 使用有序域与任意完备一致结构定义实数 / Specify reals without uniformity compatibility | 有理数离散一致结构揭示规格不足 / Reject using the rational discrete-uniformity counterexample |
| A04 | 用变号代替交替 / Replace alternation with skew symmetry | \(\mathbf F_2\) 反例不通过 / Reject using the characteristic-two counterexample |
| A05 | 把有限生成模的湮灭多项式称为规范特征多项式 / Treat an annihilator as canonical characteristic polynomial | 缺少额外定义与条件，不接受 / Require additional definition and hypotheses |
| A06 | 由 \(aM=0\) 推 \(a=0\) / Infer scalar equality from module annihilation | \(\mathbb Z\)-模 \(\mathbb Z/2\mathbb Z\) 与 \(a=2\) 反驳 / Reject without conditions such as faithfulness |
| A07 | 环上 CH 覆盖域上 CH / Generalize CH to rings | 保留两命题及特化关系，原证不强制替换 / Keep both statements and optional proof replacement |
| A08 | 1000 整体证明对比 1200 模块化证明 / Compare whole and modular proofs | 源码与理解分别评价，1200 可有首次理解收益 / Separate source cost from possible immediate comprehension gains |
| A09 | 每次后续净省 60，实际新增成本不同 / Saving 60 per use with different actual investments | 新增 200 时四次 +40；新增 1200 时二十次打平 / Distinguish alternative-portfolio differences from actual incremental setup |
| A10 | 定义 200+20 对比 100+1000 / Definitions with dependencies | 完整成本 220 对 1100，边界固定 / Compare 220 and 1100 under the fixed boundary |
| A11 | 拆成十步但没有新的可复用接口 / Split a proof without reusable interfaces | 不按步数自动奖励，但允许单独验证呈现改善 / No automatic step-count reward; presentation benefits remain testable |
| A12 | 新增别名或把目标答案藏入导入 / Add an alias or import the target answer | 展示其依赖及完整成本 / Expose dependencies and complete cost |
| A13 | 复制题目或制造矛盾假设 / Duplicate goals or add contradictory hypotheses | 不增加有效覆盖 / No additional meaningful coverage |
| A14 | 故意加长证明以提高 `I0` / Pad a proof to increase `I0` | 描述分数可变，不能标记为更有价值 / Metric change is not a value improvement |
| A15 | 共享子证明用于两题 / Share a subproof across two goals | 树与共享账本分别报告 / Keep tree and shared costs separate |
| A16 | 全包有未使用部分 / Leave package components unused | 当前政策仍计完整包 / Charge the full package |
| A17 | 移除定义但保留依赖它的已证引理 / Remove a definition but retain dependent lemmas | 消融对照不合格 / Reject the contaminated ablation |
| A18 | 无旧证明、无生成收据或无未来观测 / Missing baseline, usage or future evidence | 相应量为未知，不能补零或无穷 / Preserve unknowns rather than inventing zero or infinity |
| A19 | 一般定理使用旧特例，再以一般定理回证特例 / Generalize using an old special case, then specialize back | 原证版本仍作依赖并计费，拒绝循环改指 / Retain and charge the old proof version; reject circular rebinding |

这些案例优先用于检验评价器能否拒绝不合法的结论，不要求模型逐一修复现实题库中的失败输出。
Use these cases to test the evaluator's claims rather than to demand repairs of every failed model answer.

## 14. 对当前项目的具体结论 / Consequences for the current project

现有源码计数、展开统计、有限树证明求优、原证保留和整包核算仍有明确用途，但它们分别回答限定问题，尚未构成定义、命题与理论发展的统一评价。
The existing counters, finite solver, retention policy and package ledger remain useful for their stated purposes, without constituting a unified theory-development evaluation.

本轮修正基线说明中过于笼统的定义整理顺序，并在指标及研究计划中明确语义对应、推广保留和分层比较；旧实验、评估器源码及其指纹均不改写。
This round narrows the refactoring rule and updates the metric and research documents while preserving historical evidence and evaluator fingerprints.

下一步先审查[AI 理解成本](COGNITIVE_COMPRESSION.md)的共同背景、跨任务摊销、非线性假设与反例，再制作少量同依赖的组织对照及新增包对照。
Review conditional AI costs, amortization and structural assumptions before preparing small organization and package comparisons.

复核应明确哪些性质可在有限模型中证明、哪些需要 Lean 桥接证书、哪些只能通过后续任务观察，之后才扩充工具或进行必要的 DeepSeek 小实验。
Classify each proposed property as a finite-model result, a Lean certificate obligation or an empirical claim before expanding tooling or running necessary small DeepSeek experiments.

本轮不调用项目模型 API、不读取密钥、不进行大规模实验，也不把理论审查完成写成已通过一般定义兼容性或概念价值验收。
This round uses no project model API or credentials and establishes neither general definition-compatibility acceptance nor validated concept-value measurement.

首版核对记录包含来源、文档差异和 83 个本地链接、19 个案例编号，以及 \(\mathbf F_2^2\) 上反例的有限枚举和示例账本算术；后续认知文献修订不把这些检查升级为 AI 理解的实验验证。
The first-version checks remain evidence for documentation and finite examples, not experimental validation of the subsequent cognitive framework.
