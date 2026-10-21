# 广泛数学背景下的 AI 理解成本 / AI comprehension costs with broad mathematical knowledge

日期：2026-10-20；状态：文献核对、条件性论证与测量设计，尚无本方案的 AI 实测、拟合参数或已验证评分器。
Date: 2026-10-20; this is a literature review and measurement proposal, with no AI experiments under this design, fitted parameters or validated scorer.

## 1. 评价对象与问题 / Evaluation subject and question

MAAM 面向具备广泛数学背景、需要跨领域研究的 AI；“难度”始终指它在已有理论基础上的新增理解与使用成本，而非只为学习一个对象而从零补齐全部前置知识的成本。
MAAM targets an AI working across mathematics, so difficulty means additional comprehension and application cost relative to its broad existing knowledge.

用户的 200 对 100 问题还固定了相同依赖：即使 AI 与背景知识相同，需要协调的条件、隐含推理、量词关系与组织方式仍可造成非线性负担，不能设 \(D(200)=2D(100)\)。
Even with the same AI and prerequisites, relational structure and organization can change processing demands nonlinearly, so doubling length need not double difficulty.

分成有意义模块的 1200 长度证明，可能在该 AI 第一次接触这个具体证明时就优于整体呈现的 1000 长度证明；“第一次”不表示它第一次学习模块依赖的通用理论。
A longer modular proof may be easier on first encounter even though the AI already knows its supporting theories.

研究假设是“理解成本依赖 AI 已掌握的理论、目标、关系结构和接口，并允许非线性”，而非字数翻倍必然超线性变难或分块永远有益。
The hypothesis permits knowledge- and structure-dependent nonlinearity without asserting universal superlinear growth or universal benefits from segmentation.

### 1.1 统摄力、已有掌握与新增负担 / Unifying scope, mastery and marginal cost

若 AI 已在多个数学领域熟练使用域、序和相应完备性理论，理解实数的结构性规格主要需要辨认这些结构在此处如何结合，以及必要的相容条件。
For an AI already fluent in fields, orders and the relevant completeness theory, the remaining task is understanding their combination and compatibility in the real-number specification.

这里不能每遇到实数便重新收取这些理论的全部历史学习成本，也不能因为证明库中有它们，就无证据假定 AI 已能正确检索和应用。
Shared historical learning is not charged again for every object, while library availability alone does not establish operational mastery.

统摄力的重要性在于：同一套结构服务许多不同问题，使学习投入得以共享，也使已有概念成为后续理解的可调用单元；范围广、已掌握和新增负担低之间存在需要观察的联系。
Broad scope makes acquisition reusable and supports familiar units for later reasoning, linking generality, mastery and low marginal cost.

因此，项目应分别报告理论能够覆盖哪些任务族、AI 已经掌握什么，以及新增任务实际需要多少处理；不把统摄力直接换成未经验证的“难度倒数”。
Report scope, demonstrated competence and incremental effort separately rather than defining difficulty as the reciprocal of generality.

### 1.2 条件与跨任务账本 / Conditions and cross-task accounting

固定逻辑基础 \(F\)、共同理论库与工具 \(K\)、AI 运行状态 \(s\)，以及任务族和权重 \(\mu\)；\(s\) 包含模型版本、检索与记忆配置、已验证技能和学习协议，不能直接观测的内部知识保持未知。
Fix foundations, a shared library and tools, the AI's operational state, and a task distribution, retaining uncertainty about unobservable internal knowledge.

对任务 \(q\) 的某个呈现 \(V\)，考察达到预定正确性、组合和迁移要求时的条件成本，而非无背景的绝对难度：
For a presentation \(V\) of task \(q\), study the resources needed to satisfy declared correctness, composition and transfer criteria:

```math
C_u(q,V\mid F,K,s).
```

\(u\) 每次只指定一种单位，例如端到端时间、可见生成用量或工具调用次数；这些资源不是内部思考难度的直接读数，单位之间也不自动相加。
Each resource unit is reported separately, and observable consumption is an operational proxy rather than a direct reading of internal cognition.

对尚未掌握的新包 \(P\)，令 \(A_u(P\mid K,s_0)\) 表示本次新增准备与获取成本，包含所采用协议中的文档、索引、练习或训练；包的构造与核验成本也须在相应账本保留，边界应事先声明。
For a new package, record incremental preparation and acquisition under the chosen protocol, retaining construction and verification costs in the relevant ledgers.

在预先指定、长度 \(N\geq1\) 的任务序列 \(q_{1:N}\) 上，一次性投入与每次使用的摊销账本为：
Across a declared nonempty task sequence, account for setup once and subsequent use as follows:

```math
\overline C_u(P; q_{1:N})
 = \frac{A_u(P\mid K,s_0)
          +\sum_{i=1}^{N}c_u(q_i\mid K\cup P,s^{P}_{i-1})}{N}.
```

\(s^P_{i-1}\) 是获取新包并完成前 \(i-1\) 项任务后的状态，\(c_u\) 包含本次检索、适配、核验与增量维护；持续学习的投入只能在相应步骤计一次。
The state may evolve across tasks, and each per-task cost includes retrieval, adaptation, verification and any incremental maintenance without double counting.

旧条件也从相同起点按相同任务顺序和学习规则记录 \(A_u^0,c_u^0\)，再比较两条累计曲线；成功率、错误类型与新增覆盖同时报告，不能只对成功任务求平均而丢掉失败。
Compare matched baseline trajectories alongside success, errors and coverage, keeping failed attempts in the resource accounting.

若有关理论已在共同背景中被掌握，其过去成本属于共享历史，不作为此次新增 \(A_u\) 反复收取；仍需支付当前调用和组合成本。
Already-mastered background has a shared history rather than repeated acquisition charges, while retrieval and composition still incur current costs.

上述平均值针对实际运行资源，不代替源码共享账本：源码仍按声明身份去重并完整计入新包一次，不按每道题重复展开或只收取当前用到的片段。
Operational amortization does not replace the source ledger, which deduplicates declarations and charges the complete new package once.

没有任务分布与观察跨度，就不能把“可用于整个数学”换成任意大的摊销分母；应按预先声明的不同领域任务族报告结果和范围限制。
A broad mathematical ambition does not license an unlimited amortization denominator; results remain conditional on declared task families and horizons.

## 2. 文献及其证据范围 / Literature and evidence boundaries

以下八篇人类认知与证明理解论文用于形成结构性假设，随后三篇 AI 论文用于核对库学习和跨任务使用的研究路径；这是针对性检索，不是系统综述。
Eight cognition papers motivate structural hypotheses, while three AI papers inform library learning and cross-task evaluation; this is a focused review.

人类的记忆上限、主观负荷和教学效果不直接定义 MAAM 的 AI 难度，当前任务也不要求开展人类被试研究。
Human memory limits, reported effort and instructional effects do not define the AI metric or require a participant study.

| 文献 / Source | 可以支持什么 / Supported contribution | 不能直接推出什么 / Limit |
| --- | --- | --- |
| Chen, Paas & Sweller (2023), [A Cognitive Load Theory Approach to Defining and Measuring Task Complexity Through Element Interactivity](https://link.springer.com/article/10.1007/s10648-023-09782-w) | 同时处理的交互元素与已有知识共同决定任务复杂度，并讨论前测和教师判断 / Interaction demands and prior knowledge inform task-complexity estimation | 元素估计仍依赖读者；没有数学文本长度到理解难度的通用公式 / No universal text-length-to-difficulty formula |
| Cowan (2001), [The magical number 4 in short-term memory](https://memory.psych.missouri.edu/assets/doc/articles/2001/cowan-bbs-2001.pdf) | 在限定条件下讨论容量约束和组块 / Capacity constraints under explicit experimental conditions | 不能把约四个组块写成四个 token、变量或引理的通用上限 / No universal four-token or four-lemma limit |
| Halford et al. (2005), [How many variables can humans process?](https://pubmed.ncbi.nlm.nih.gov/15660854/) | 操纵统计交互关系阶数，观察到处理表现的容量限制 / An experiment on the number of jointly related variables | 不能把图形统计交互任务中的阈值直接移植到任意数学定义 / Task-specific results do not calibrate all mathematics |
| Mathy & Feldman (2012), [What’s magic about magic numbers?](https://pubmed.ncbi.nlm.nih.gov/22176752/) | 数字序列实验把可压缩模式、组块和记忆联系起来 / Experiments connect pattern compressibility, chunks and memory | 不等于通用压缩软件或 Lean 展开比能够预测数学理解 / No validation of generic compression or Lean expansion as comprehension scores |
| Mejía-Ramos et al. (2012), [An assessment model for proof comprehension in undergraduate mathematics](https://link.springer.com/article/10.1007/s10649-011-9349-7) | 理解包括局部论证、整体思想、模块、方法和实例 / A multidimensional assessment of proof comprehension | 这是测量框架，不是按源码自动评分的公式 / An assessment framework, not an automatic source metric |
| Hodds, Alcock & Inglis (2014), [Self-Explanation Training Improves Proof Comprehension](https://mjinglis.github.io/files/JRME_SelfExpl_Paper.pdf) | 三个实验检验自我解释训练，使用理解测验及阅读过程证据 / Three experiments assess self-explanation training and proof comprehension | 自我解释干预不等于仅增加分块；更多阅读投入也未必更差 / The intervention is not a pure segmentation experiment |
| Lamport (2012), [How to Write a 21st Century Proof](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/How-to-Write-a-21st-Century-Proof.pdf) | 分层组织证明、标明局部目标与理由的设计论证 / A design argument for hierarchical proof organization | 作者方法与经验不提供认知负担的受控效应量 / Methodological experience is not a controlled cognitive effect estimate |
| Rey et al. (2019), [A Meta-analysis of the Segmenting Effect](https://maria-wirzberger.de/wp-content/uploads/2019/01/Rey2019_Article_AMeta-analysisOfTheSegmentingE.pdf) | 多媒体分段研究总体支持记忆与迁移改善，并区分认知负荷和学习时间 / Segmentation evidence separates learning outcomes, load and time | 多媒体结果需要另行检验才能用于数学证明；学习时间结果还存在偏倚警示 / Domain transfer and the learning-time evidence require caution |

访问范围：Chen、Cowan、Hodds、Rey 使用可访问正文的相关部分，Lamport 使用作者研究页面及可访问作者稿信息，Halford 与 Mathy 使用论文摘要，Mejía-Ramos 使用出版社摘要并对照 Hodds 正文第 6–8 页对该框架的说明。
The access record distinguishes selected full-text passages, author material and abstract-only evidence, without implying that every paper was read in full.

| AI 文献 / AI source | 与本项目有关的证据 / Relevant evidence | 边界 / Limit |
| --- | --- | --- |
| Ellis et al. (2021), [DreamCoder: Bootstrapping Inductive Program Synthesis with Wake-Sleep Library Learning](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf) | 联合学习可复用库和搜索策略，并比较缺少组件的系统 / Joint library and search-policy learning, with component ablations | 程序合成实验不提供通用数学理解函数 / Program synthesis does not calibrate universal mathematical difficulty |
| Grand et al. (2024), [LILO: Learning Interpretable Libraries by Compressing and Documenting Code](https://arxiv.org/html/2310.19791v4) | 文档和命名影响 LLM 对抽象的使用；仅加入匿名抽象可能使表现下降，文档收益也有领域差异 / Usability matters beyond adding compressed abstractions | 三类程序合成任务的结果不能直接当作 Lean 证明效果 / Three synthesis domains do not establish effects for Lean proofs |
| Kumarappan et al. (2024 preprint), [LeanAgent: Lifelong Learning for Formal Theorem Proving](https://arxiv.org/html/2410.06209v3) | 随数学库扩张更新检索器，分别观察新知识适应与旧知识保持 / Evolving libraries, retriever adaptation and retention | 可验证求证与检索表现不等于读出了模型内部理解；其步数复杂度启发式不是本项目的认知定律 / Behavioral evidence and curriculum heuristics are not a universal comprehension model |

AI 文献核对范围为 DreamCoder 的方法概述与消融段落、LILO 的第 2–4 节相关段落、LeanAgent v3 的第 3 节及评价设置，没有复现实验或采用其效果数值作为本项目的参数。
The review uses selected methods and evaluation passages without reproducing experiments or importing their effect sizes as MAAM parameters.

## 3. 非线性首先发生在哪一层 / Where nonlinearity belongs

总文字量描述输入规模，交互结构描述需要协调的关系，而 AI 已掌握的概念和可靠工具接口决定哪些细节可以封装成一个可调用单位。
Input volume, relational structure and reliably usable concepts describe different aspects of the AI's task.

一个较短定义若把多个条件紧密耦合，可能比更长但逐步展开的定义更难；增加解释也可能减少隐含推理，所以理解成本甚至不必对文字长度单调增加。
A compact definition can demand more coordinated reasoning, while added explanation can reduce missing inferences, so difficulty need not even increase monotonically with length.

项目需要区分两条映射：由文本、关系结构与 AI 状态提出处理要求的假设，再由可观察的任务表现检验这个假设；不能跳过这些步骤，直接对 token 数平方。
Structural hypotheses must be tested against AI task outcomes rather than converted directly into squared token counts.

相同依赖、同一个 AI 和相同运行状态下也要比较组织方式；已有知识解释为何无需从头重学通用理论，不会消除新组合的非线性问题。
Controlling knowledge and AI state still leaves structural effects to study, including the demands of novel combinations.

## 4. 分块如何产生当前理解收益 / How chunking can help immediately

| 改变 / Change | 可能作用 / Possible effect | 必须核对 / Required check |
| --- | --- | --- |
| 分段、层级或分次提供 / Segmentation and staged access | 可能改善上下文组织及处理顺序 / May improve context organization and processing order | 单独测量呈现效果，并记录新增调用成本 / Separate presentation effects and charge extra calls |
| 标出子目标、理由和中间结论 / Explicit local goals and reasons | 减少重建省略步骤及维持上下文的负担 / Reduce omitted-inference and context demands | AI 能否正确组合各块得到主结论 / Test integration with the overall argument |
| 掌握一个可调用概念 / Master a usable concept | 后续处理时可调用整体，减少重复展开 / Enable later use without repeating every detail | 已有掌握不重复收费，新学习与必要的展开能力另验 / Separate existing mastery, new acquisition and required unpacking |
| 导出可调用的引理 / Export reusable lemmas | 改善检索、适用性判断与迁移 / Support retrieval, applicability decisions and transfer | 接口假设、调用成本及新问题表现 / Check assumptions, application costs and transfer |

给十段文字起名字不意味着 AI 立刻熟练掌握十个接口；反过来，已经掌握的理论也不需要每次重新展开，呈现改进是否有用由 AI 表现检验。
Naming does not guarantee mastery, established theory need not be repeatedly unfolded, and presentation benefits require AI-specific evidence.

对 1200 的方案，必须同时检查每块是否更容易处理，以及把各块组合起来是否仍需要保持大量未解决条件，不能只看最大块长度。
Assess both local manageability and global integration, since a small maximum block size can conceal a demanding interface between blocks.

接触新证明时，只需为尚未掌握的块记录获取成本；已有模块的检索、条件核对、对象适配和整体组合则属于当前使用成本。
A new proof incurs acquisition only for unfamiliar components, alongside the current costs of finding and composing familiar ones.

## 5. “理解难度”先用什么结果定义 / Operational outcomes before a score

首先固定广泛背景 \(K\)、AI 状态 \(s\)、待理解对象 \(O\)、呈现版本 \(V\)、资源协议 \(\pi\) 与未泄露答案的评估任务集 \(\mathcal T\)，按可核查的外部表现操作性地定义“掌握”。
Define mastery through checkable behavior under a fixed AI state, broad background, presentation, resource protocol and independent assessment tasks.

| 结果 / Outcome | 建议的观测 / Proposed observation |
| --- | --- |
| 局部理解 / Local understanding | 解释术语、说明某一步为何成立、识别条件作用 / Explain terms, justify a step and identify a hypothesis's role |
| 整体理解 / Global understanding | 重建主线、说明模块关系、辨认不合法拼接 / Reconstruct the argument and detect invalid composition |
| 定义理解 / Definition understanding | 判断新例与反例，说明量词或条件变化的后果 / Classify fresh examples and explain changed quantifiers or conditions |
| 迁移能力 / Transfer | 在未见过且非简单换名的题目上选择并应用有关模块 / Select and apply a module on structurally fresh tasks |
| 保持 / Retention | 经后续任务或学习更新后，用新题复查旧能力；固定权重的无状态调用不以经过时间充当遗忘实验 / Recheck competence after intervening tasks or updates, not merely wall-clock delay |
| 成本与负担 / Cost and effort | 生成用量、调用、检索、修复、核验和耗时分列；不可见内部计算保持未知 / Separate observed resources and retain unknown internal computation |

这些维度借鉴证明理解研究，但对 AI 的定义、接口及迁移测量是 MAAM 提案；形式结论由 Lean 核验，说明性回答需要独立评分规则，不能只让同一模型自报“我懂了”。
The AI assessment is a MAAM proposal requiring formal checks where applicable and an independent rubric for explanatory answers.

在某一资源单位 \(u\) 的预算 \(b\geq0\) 下，其余条件按 \(\pi\) 固定，可定义：
For a nonnegative budget \(b\) in resource unit \(u\), with other conditions fixed by the protocol, define:

```math
p_s^u(b\mid O,V,F,K,\mathcal T,\pi)
 = \Pr(\text{declared mastery criterion met}
       \mid O,V,F,K,s,\mathcal T,\pi,u,b).
```

概率来自声明的任务抽样与运行随机性；达到预先规定的目标水平 \(0<\eta<1\) 的资源阈值只是待估计的条件性量，不能凭一次成功给出：
Probability refers to declared task sampling and run randomness, and the resource threshold for a target level requires estimation:

```math
C_\eta^u(O,V\mid F,K,s,\mathcal T,\pi)
 = \inf\{b:p_s^u(b\mid O,V,F,K,\mathcal T,\pi)\geq\eta\}.
```

有限预算范围内未达标应记为尚未观测到阈值，不能补成无穷难度；更多预算也不保证某个实际策略的表现单调改善，曲线和不确定性须保留。
An unobserved threshold is not infinite difficulty, and more allocated budget need not improve a particular strategy monotonically.

固定资源下更可靠、达到同一标准更省资源，以及能处理更多新组合，是不同的改善；较多生成 token 若换来更高正确率，不能直接判为理解退步。
Reliability, resources to a common target and transfer scope are different outcomes, so longer generation is not automatically worse understanding.

模型若仅会复制已给证明，不能据此宣称掌握概念；需用未直接给答案的适用性判断、条件变化和组合任务检查，既有结果作为示例时也应记录其暴露范围。
Copying an exposed certificate does not establish conceptual mastery; use fresh applicability and composition tasks with documented exposure.

## 6. 一个条件性论证：为什么分块可以抵消变长 / A conditional argument for modularity

以下是 MAAM 的简化数学模型，用于明确必须检验的假设，不是从文献中获得的已校准人类或 AI 定律。
The following is a MAAM toy model that exposes assumptions rather than an empirically calibrated human or AI law.

固定广泛背景 \(K\) 与 AI 状态 \(s\)，假设 \(m\) 个模块的有效待处理量为 \(w_i\geq0\)，整段方案必须同时处理 \(S=\sum_i w_i\)，分块方案可分别处理，全部额外开销计入 \(H\geq0\)。
At fixed knowledge and AI state, assume additive simultaneous demand in the unstructured version, separable processing in the modular version, and complete overhead accounting.

再假设所考察区间的处理成本函数 \(g\) 为非负凸函数且 \(g(0)=0\)，则：
Assume a nonnegative convex processing-cost function with zero cost at zero demand:

```math
C_{\mathrm{whole}}=g(S),\qquad
C_{\mathrm{blocks}}=\sum_i g(w_i)+H.
```

当 \(S>0\) 时，凸性给出 \(g(w_i)\leq(w_i/S)g(S)\)，相加得到 \(\sum_i g(w_i)\leq g(S)\)，所以分块优于整段的充分且在此模型内等价的条件是：
Convexity bounds the sum of the local costs, and within this model the exact condition for a strict improvement is:

```math
H < g(S)-\sum_i g(w_i).
```

\(S=0\) 时两种局部处理成本均为零，额外开销不能带来改善；若 \(g\) 线性，右侧也为零，因此该模型中特有的分块收益来自非线性的协调成本。
The zero-demand and linear-cost cases provide no saving under nonnegative overhead, isolating the role of nonlinear coordination cost in this model.

这里 \(w_i\) 不是每块的 token 数，而是相对于已有掌握的条件性处理量；\(H\) 包括尚未计入局部处理的接口学习、导航、调用及整体拼装成本，已掌握的通用理论不重新学习收费。
Demands are conditional on existing competence, and overhead avoids double-counting local processing or recharging familiar foundations.

整段方案是否真的需要同时协调 \(S\)、模块能否独立处理、成本是否在相应区间凸增，都是待检验假设；若 AI 已能自行分块，或模块间高度耦合，上述优势可能消失。
The assumptions can fail when the AI already handles the original modularly or the proposed interfaces remain strongly coupled.

因此，1200 对 1000 的认知比较可以在首次阅读时成立，其关键是协调负担的下降能否超过新增开销，而不是等待 200 长度差额在后续源码调用中摊销。
The relevant comparison is reduced coordination cost versus added overhead during learning, independently of later source-cost amortization.

## 7. 从可观察结构到预测模型 / From observable structure to prediction

在没有相应 AI 实测前，先定义候选描述量：当前条件与中间结论、开放子目标、跨块接口、隐含理由，以及已有概念在独立任务上的使用表现。
Candidate descriptors include active conditions, open goals, interfaces, missing justifications and independently demonstrated competence.

形式依赖图节点不自动等于 AI 的处理单元；应保存标注规则、能力检查与分歧，同一形式结构在不同模型状态下可有不同使用成本。
Formal nodes are not automatically AI processing units, and costs may change with model state.

之后用理解表现比较三类预测模型：仅按长度的基准模型、加入关系和模块结构的模型、允许处理负担产生阈值或平滑非线性影响的模型。
Compare a length-only baseline, a structure-aware model, and a model permitting threshold or smooth nonlinear effects of processing demand.

非线性形式、系数与阈值须由明确数据约束，在未参与选择的任务族和独立运行中验证；若声称跨模型有效，还须跨模型复核，不预设平方、指数或“四个组块”。
Validate response shapes on held-out task families and runs, adding cross-model checks only when making cross-model claims.

仅有 100 和 200 两个长度，或 1000 与 1200 两份材料，不能识别增长曲线，也不足以分开内容复杂度、呈现差异和分块效果。
Two lengths cannot identify a growth law or separate changes in content, presentation and modularity.

AI 的运行费用、证明搜索困难和数学概念的潜在价值也不能混为一项：检索器欠佳可能抬高实测成本，却不证明理论本身缺少统摄力。
Poor retrieval can raise observed costs without disproving a theory's broader mathematical usefulness.

## 8. 小范围验证应该比较什么 / A small validation design

当前阶段先审查少量配对材料与验收问题，不发起大规模调用；目标始终是广泛数学背景下的 AI，只对具体干预做小范围比较。
Prepare a small assessment design for an AI with broad mathematical knowledge, keeping the intervention narrow.

1. 冻结模型版本、工具、可检索库、提示、记忆与学习规则，使用不泄露目标答案的小检查确认相关通用理论可被使用，失败只作为能力边界记录。
   Fix the operational background and check prerequisite competence without exposing target answers or repairing every model failure.
2. 先按[基线准备规则](BASELINE_PREPARATION.md)利用旧工具整理表达和证明，再冻结比较；已有理论足以实现的分块与接口不能归功于新包。
   Prepare the baseline using existing tools before attributing additional gains to a package.
3. 分开比较同一 \(K,s\) 下的呈现变化，以及从 \(K\) 到 \(K\cup P\) 的理论变化；前者可设整体、版式分段、显式模块三个版本，并核对内容与解释差异。
   Separate presentation effects at fixed knowledge from package effects, controlling mathematical content and added explanation.
4. 使用新上下文及明确重置的外部记忆作独立对照，匹配资源上限并记录实际使用；若考察持续学习，则两边从同一起点沿同一任务序列演进。
   Use independent contexts for static comparisons and matched starting states and sequences for lifelong comparisons.
5. 同时检查条件辨认、整体组合及未见任务上的迁移，按预先声明的题族报告结果；近似重命名的题目不能冒充新的数学领域。
   Test applicability, integration and transfer across declared families without counting renamed duplicates as breadth.
6. 新包的准备、获取、索引或训练投入计一次，再记录每次使用；预训练中是否见过相关理论通常不可确定，禁止把隔离导入宣称为清除了模型原有知识。
   Charge new setup once and preserve uncertainty about pretraining exposure; import isolation does not erase model knowledge.
7. 小样本用于检查测量可行性，不能拟合普遍难度定律或估计整个数学的收益；旧实验继续作为工程与局部归因对照，不能升级为成熟数学 AI 的理解证据。
   Small pilots and existing narrow experiments remain limited evidence rather than measures of universal mathematical competence.

给新包足够的协议化获取机会，再与旧条件在相同累计资源下比较；单次读不懂不等于抽象无价值，也不允许把新包组额外获得的训练隐藏在比较之外。
Allow declared acquisition while accounting for it fairly, distinguishing temporary unfamiliarity from the abstraction's eventual usefulness.

## 9. 对 MAAM 评价和采用策略的修改 / Changes to evaluation and adoption

“认知压缩”在这里操作性地指：相对于 AI 的广泛已有知识，降低达到指定掌握与迁移要求的新增处理成本，或在相同资源下提高可靠性与适用范围。
Cognitive compression is operationalized as lower incremental cost, greater reliability or broader transfer relative to the AI's existing mathematical knowledge.

较长但更容易被 AI 掌握和组合的证明，可以在理解轴上更优；源码存储、核验证书、AI 接口及后续使用的优选版本不必完全相同，原有证书仍保留。
A longer proof may offer a better AI interface while the selected short certificate remains preserved.

当前程序的严格缩短规则仍只说明既定源码指标下的证书选择，不能推广为“较长方案在当前没有收益”；本轮不会借文档修订暗中改动冻结的选择器。
The existing source-selection rule does not establish that longer alternatives lack present value, and this theoretical revision leaves the frozen selector unchanged.

综合报告增加共同知识、AI 状态、条件性使用成本、一次性获取成本、不同题族的迁移及保持结果，先报告多维比较与未知量，不制造一个未校准的认知总分。
Report conditional competence and resource outcomes, one-time acquisition, cross-family transfer and retention without an unvalidated scalar score.

## 10. 验收要求 / Acceptance requirements

| 编号 / ID | 必须满足 / Requirement |
| --- | --- |
| C01 | 相同依赖不能触发 \(D(200)=2D(100)\) 的默认推断 / Equal dependencies do not imply proportional difficulty |
| C02 | 1200 的模块化版本可在首次理解上优于 1000，不以已有复用次数为前提 / Initial comprehension gains require no realized future reuse |
| C03 | 仅改变版式可以改善呈现，但不自动获得新增数学抽象标签 / Presentation improvement is distinct from new abstraction |
| C04 | 命名不自动形成已掌握组块，新增获取与拼装成本须记录 / Naming does not grant free learned chunks |
| C05 | 局部模块易懂但整体无法拼装，不能判定已理解整份证明 / Local success without integration is insufficient |
| C06 | 更多处理投入可伴随更好理解，不自动记为认知退步 / More processing can accompany better comprehension |
| C07 | token、形式节点、变量和认知组块不能无证据互换 / Formal and cognitive units require an evidenced mapping |
| C08 | 不从两个长度拟合普遍幂律，不把人的容量常数移植给 LLM / No universal law from two lengths or human-to-LLM threshold transfer |
| C09 | 证明模型中的凸性结论只在其明确假设下成立 / The convexity argument remains conditional on its assumptions |
| C10 | 保留短证书允许同时保存和评价较长易懂版本 / Retaining a short certificate permits a longer accessible exposition |
| C11 | AI 已掌握通用理论时，不因学习新对象而重复计入全部历史学习成本 / Do not recharge shared historical acquisition for each object |
| C12 | 真正新增的包及其获取成本计一次，不能伪装成免费的共同背景 / Charge genuinely new package setup once |
| C13 | 理论范围广与 AI 已熟练使用分别举证，库中存在不等于已掌握 / Distinguish broad scope, availability and mastery |
| C14 | 统摄力用声明的不同任务族检验，不靠复制题目或无界摊销分母 / Use declared task families and finite horizons |
| C15 | 同依赖的组织收益与新增理论的收益分开，旧工具先充分使用 / Separate organization effects from new-theory effects |
| C16 | 小型隔离实验不冒充广泛数学能力；导入隔离不冒充预训练知识清除 / Do not equate narrow controls with broad competence or erased prior knowledge |
