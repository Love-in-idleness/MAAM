# 新概念与理论包的评估计划 / Evaluating new concepts and theory packages

日期：2026-10-21。状态：M1 已完成参考迁移并新增离线整包压缩计量；M2 保留 20 题公开校准、另 20 题的 40 个独立求解上下文及一次 8 题计量对照，但尚未证明原有基线充分优化，严格概念归因与训练验收未完成；M3 已实现整包消融、成本偏序及父子版本复用校准，自动多轮探索与 M4 未完成。
Date: 2026-10-21. Status: checked reference migrations now include an offline compression sidecar; public and independent-context calibrations, a small metered comparison, package ablations and version-reuse controls exist, while baseline preparation, strict concept attribution, automatic multi-round search and learning acceptance remain incomplete.

当前优先级是可计算、可实现的小范围工具：[整包压缩计量](COMPRESSED_PACKAGES.md)已对冻结 M1 归档完成离线计量，[方法说明](PROOF_METHODS.md)先明确一套已有证明的入口、选择和义务；随后在[已准备的基线](BASELINE_PREPARATION.md)上检查少量新实例。
Prioritize computable package measurements and explicit existing-method interfaces, then bounded applications over prepared baselines; one archived example does not establish new transfer or concept value.

[分层框架](COMPRESSION_FRAMEWORK.md)与[广泛数学背景下的 AI 理解成本](COGNITIVE_COMPRESSION.md)保留作为理论约束；尚不可计算或未标定的理解难度、无限未来价值和统一综合分冻结为后续研究，不阻塞当前工程。
Keep semantic contracts and broad AI background assumptions, while deferring unimplemented cognitive scores and unobserved future-value models instead of requiring a complete evaluation theory first.

旧工具能够完成的整理先于基线冻结，依赖新包的重构则属于加入新包后的候选效果；现阶段只做理论论证、工具验收与小范围实验，大规模实验留待用户指定的未来 `gpt6bel` 可用且身份确认后再冻结协议。
Separate old-tool preparation from package-enabled refactoring and keep experiments small; the future model name is a planning condition rather than a release claim or an automatic switch.

当前实现及实际结果见 [理论包接口](THEORY_PACKAGES.md) 与 [同态/核实验](../experiments/hom_kernel/README.md)。
See the [theory-package interface](THEORY_PACKAGES.md) and [homomorphism/kernel experiment](../experiments/hom_kernel/README.md) for the current implementation and measured results.

早期 [生成计量接口](GENERATION.md) 接入 OpenAI Responses、逐任务修复、预算预约和原始收据，并完成两个 GPT-6 Luna 公开任务条件的隔离 Lean 核验，记录 2332 输入、514 输出 token；后续实际调用仅走 DeepSeek，计量对照与当前准备限制见下文。
The historical OpenAI calibration stays separate from subsequent DeepSeek-only calls; neither it nor the later retained-proof summaries establish that the existing baseline was sufficiently optimized before a package comparison.

## 目标 / Objective

MAAM 的主要目标是评估新命题、新对象及围绕一个核心思想形成的一组定义、性质和推论，为数学探索与 LLM 学习提供可核查的反馈。
MAAM's main objective is to evaluate new propositions, objects and connected collections of definitions, properties and consequences, providing auditable feedback for mathematical exploration and LLM learning.

评价主体始终是面向多个数学领域、已有广泛理论背景的 AI；通用理论的历史学习成本不为每个对象重算，新增理论包的准备与获取成本计一次，并结合不同任务族的使用成本与可靠性评价。
Evaluate an AI with broad mathematical knowledge, charging genuinely new setup once and assessing conditional use, reliability and transfer across task families.

知识库中存在某个定理不等于 AI 已熟练掌握；要记录模型、检索、记忆和能力证据，实际内部知识及预训练暴露不可确定时保持未知。
Library availability and operational competence remain separate, with unknown internal knowledge and pretraining exposure preserved.

评价可以输出带条件的比较、不可比或证据不足；不要求单个数值或统一的全局排序。
Evaluation may return a contextual comparison, incomparability or insufficient evidence; it need not produce a scalar or a universal ranking.

核心实验是：在固定背景知识、任务和资源下，加入候选理论包并实际重述、重证之后，发生了什么可验证的变化？
The central experiment asks: with background knowledge, tasks and resources fixed, what verifiable changes occur after introducing a candidate package and actually reformulating and reproving results?

同背景下的模块组织效果与加入新理论后的效果分开比较，旧工具能完成的整理先做好；现有小型同态/核实验是工程和局部归因对照，不能代表广泛数学背景下的理解难度。
Separate organization effects from new-theory effects, retaining narrow existing experiments as controls rather than evidence of broad mathematical competence.

原有静态指标仍作为描述和检索信号；全库复现差异继续单列追踪，静态分数不是新概念未来价值的已验证估计。
Existing static metrics remain descriptive and retrieval signals; full-library reproduction discrepancies remain tracked separately, and static scores are not validated estimates of a new concept's future value.

## 来源与项目扩展 / Sources and project extensions

ABFM 第 5.2 节明确指出，固定定义集上的压缩指标尚未解决动态提出新定义的问题。
ABFM Section 5.2 explicitly notes that compression metrics over fixed definitions leave the problem of proposing new definitions open.

BDF 第 4.4 节讨论抽象与重构，第 4.5 节式 (7) 讨论用重写语料节省的成本扣除抽象本身成本，第 4.6 节将后续任务表现作为实用性证据。
BDF Section 4.4 discusses abstraction and refactoring; Section 4.5, equation (7), considers corpus rewriting savings minus abstraction cost, and Section 4.6 treats subsequent task performance as evidence of usefulness.

下面的候选格式、实验控制、skill 协议与非数值反馈是 MAAM 的研究设计，不声称是论文已验证的方法。
The candidate format, experimental controls, skill protocol and non-scalar feedback below are MAAM research designs, not methods already validated by those papers.

LILO 与 Stitch 可提供库学习和重构的技术参考；它们在程序合成上的结果不能直接视为依赖类型数学证明中的效果保证。
LILO and Stitch provide technical references for library learning and refactoring; their program-synthesis results do not establish effectiveness for dependent-type mathematical proofs.

## 评估单位 / Evaluation unit

一次输入称为候选理论包，可以退化为单条命题或单个定义，也可以包含一个思想的多个协同部分。
An input is a candidate theory package, which may contain a single proposition or definition, or several cooperating parts of one idea.

| 字段 / Field | 内容 / Content |
| --- | --- |
| base | 固定知识库、工具链、允许依赖及指纹 / Fixed library, toolchain, allowed dependencies and fingerprints |
| core | 核心思想说明、定义与对象构造 / Core idea, definitions and object constructions |
| declarations | 性质、定理、实例及其证明状态 / Properties, theorems, examples and proof status |
| bridges | 新旧表达之间的等价、同构或结果回传证明 / Equivalences, isomorphisms or certified transport back to original statements |
| dependencies | 包内依赖与外部依赖 / Internal and external dependencies |
| conjectures | 待证明猜想，不能作为已证前提使用 / Pending conjectures, unavailable as proved premises |
| applicability | 预期应用模式及适用条件，作为搜索建议 / Suggested application patterns and conditions for search |
| provenance | 父版本、生成轨迹与已耗资源 / Parent version, generation trace and resources already spent |

包首先整体评价，随后通过去掉部分引理、仅保留定义等对照检查贡献；不能把各节点静态分数相加当成整体价值。
Evaluate the package jointly first, then inspect contributions with controls that remove lemmas or retain definitions alone; do not substitute a sum of static node scores for joint value.

首版使用既定基础上的定义与已证扩展；若候选改变公理，记录为不同假设下的实验，不能把更强假设产生的收益混入同一比较。
The first version uses definitions and proved extensions over fixed foundations; candidates that change axioms belong to experiments under different assumptions, and gains from stronger assumptions cannot be mixed into the same comparison.

## 实验协议 / Experiment protocol

设 K 为背景知识，P 为候选包，T 为预先确定的任务，B 为求证预算；比较 Run(K, T, B) 与 Run(K + P, T, B)，并单列 P 的引入成本。
Let K be background knowledge, P a candidate package, T a predetermined task set, and B the proof-search budget; compare Run(K, T, B) with Run(K + P, T, B), separately accounting for the cost of introducing P.

### 1. 固定对照 / Freeze the comparison

固定基础库、目标集、声明等价判据、成本口径、证明器配置与预算。
Fix the base library, goals, statement-equivalence criteria, cost conventions, prover configuration and budget.

任务身份需要固定对象、参数、假设与结论的结构对应；任意两个已证命题都可建立 `iff`，所以逻辑等价证书本身不是完整的语义兼容标准。
Task identity requires a structural interpretation of objects, parameters, hypotheses and conclusions, because arbitrary equivalence between proved propositions is not a complete semantic contract.

两边均得到改写和重证机会；不能用一边经过优化的证明对比另一边未经同等搜索的旧证明。
Both conditions receive opportunities to rewrite and reprove; compare equally searched conditions rather than optimised proofs against untouched historical proofs.

在引入候选之前，先仅用旧工具准备基线，包括已有定义与自动化的利用、适用引理检索和局部缩短；语义兼容与成本核验后冻结最佳保留证明及知识环境，再让两边从同一基线得到匹配的继续搜索机会。
The historical-to-final saving splits exactly into old-tool preparation, continuing old-tool search, and the package-associated net difference; the [baseline note](BASELINE_PREPARATION.md) defines the costs and explains why this identity alone does not establish causality.

准备不足、未尝试或仅搜集了旧证时，不把基线声明为已充分优化；对一般 Lean 搜索只能记录指定方法与预算内找到的最好结果，未来发现更短旧证时重新冻结基线。
The first offline inventory fixes its preparation and attribution readiness flags to false; the additive [supplied-local workflow](BASELINE_SEARCH.md) records incumbent-bound requests, strict-shorter candidates and clean sweeps, and [two deterministic methods](BASELINE_METHODS.md) now have actual execution evidence, while metered baseline search and definition acceptance remain incomplete.

基线检查依赖的传递闭包及自动化扩展，防止同态、核或配套定理通过 imports、simp 规则等途径预先进入。
Check the transitive dependency closure and automation extensions so that homomorphisms, kernels or supporting theorems do not enter the baseline through imports, simp rules or similar routes.

### 2. 固定候选并分开任务 / Freeze candidates and separate tasks

首轮建议 12 个开发任务和 8 个预留任务，并按推理模式分组，避免仅换名字的近重复跨组。
Start with approximately 12 development tasks and 8 held-out tasks, grouped by reasoning pattern so near-duplicates with renamed variables do not cross the split.

候选生成与修改只使用开发任务；预留评价时，求证器可以看见目标，但候选包保持固定，不能把测试答案补进包中。
Candidate generation and revision use development tasks only; at held-out evaluation, the prover sees the goals but the package stays fixed and cannot be extended with test answers.

预留结果一旦用于修改候选，这批任务就成为开发数据；之后的最终评价需要新的未使用任务。
Once held-out outcomes guide candidate revisions, those tasks become development data and final evaluation needs fresh unused tasks.

### 3. 局部迁移 / Migrate locally

先检索可能受影响的命题与对象；结合类型、假设和已验证的应用模式，限制需要尝试重构的局部范围。
First retrieve potentially affected propositions and objects, using types, assumptions and verified application patterns to bound the local refactoring scope.

按代价逐步尝试定义折叠或展开、已证等价转换、应用配套引理和局部重证。
Try definition folding or unfolding, proved equivalence transformations, supporting-lemma application and local reproving in increasing order of cost.

如果新表示改变了命题表述，必须给出回到原目标的证明；单向蕴涵只能支持相应方向，不能标记为等价。
If a new representation changes a statement, provide a proof transporting the result back to the original goal; one-way implications certify only their supported direction and must not be labelled equivalences.

旧证明保留，新证明作为同一目标的备选证明记录；不同推导的全部前提要分组，防止把多种证明混成一个依赖集合。
Preserve old proofs and record new ones as alternatives for the same goal; group all premises of each inference so alternative proofs are not conflated into one dependency set.

添加理论包不要求过去的定理全部重证或强制采用新对象；默认按完整证明模块源码长度，仅当新证明核验通过且严格更短时更新当前选用证明，等长、更长、失败或长度未知都保留原证。
Search may skip unaffected goals; preserve the original certificate and import context, treat newly solved goals separately from shortening, and charge the complete theory package once when reporting net value.

该严格缩短规则决定当前采用哪份证明，不限制研究档案保留较长但可能可复用的分解；适用范围更广的命题作为新节点保留，通过核验的特化关系连接原命题，不能简单覆盖原命题。
Strict shortening governs adoption rather than all research value; keep potentially reusable decompositions and retain broader statements as new nodes linked to the originals by checked specialization.

### 4. 验证与核算 / Verify and account

Lean 检查候选定理、迁移桥接和最终证明；运行程序检查未授权的公理、sorry 污染、依赖范围、数据指纹与预算。
Lean checks candidate theorems, transport bridges and final proofs; the runner checks unauthorised axioms, sorry contamination, dependency scope, data fingerprints and budgets.

单列源码长度、内部证明大小、求证预算消耗、验证时间和成功目标，不把不同单位直接相加。
Report source length, internal proof size, proof-search resources, verification time and solved goals separately rather than directly adding unlike units.

包中的定义、引理证明、表示转换及可供后续调用的共享辅助结果要纳入账本，共享内容只计一次；查找和构造成本另行报告。
Include definitions, lemma proofs, representation bridges and reusable shared auxiliaries in the ledger, counting shared content once; report search and construction costs separately.

证明节省应同时报告总节省与扣除包成本后的净节省；加入一个同义名称可能有真实的记号收益，但不能靠忽略名称定义成本制造收益。
Report gross savings and savings net of package cost; a new alias may genuinely improve notation, but ignoring its definition cost must not manufacture gains.

一般 Lean 任务报告给定预算内找到的最好证明，不声称求得普遍最短证明；既有 E_finite 只对显式提供的有限树证明空间保持精确含义。
For general Lean tasks report the best proof found within the budget, not a universal minimum; existing E_finite retains its exact meaning only for the explicitly supplied finite tree-proof space.

### 5. 证据输出 / Evidence output

输出逐任务证明证书、旧新表示映射、依赖变化、成本向量、失败原因、资源轨迹及探索覆盖率。
Output per-task proof certificates, old/new representation maps, dependency changes, cost vectors, failure reasons, resource traces and exploration coverage.

正确性状态与价值判断分开：无效证明、预算耗尽、没有找到适用方式、已发现改善是不同事件。
Keep correctness status separate from value judgement: invalid proofs, budget exhaustion, failure to find an application and observed improvement are distinct events.

## 比较与学习信号 / Comparison and learning signals

在相同任务与口径下，若一候选在选定维度上均不差且至少一项更好，可以记录经验支配关系。
Under the same tasks and conventions, record empirical dominance when a candidate is no worse on the selected dimensions and strictly better on at least one.

有成本与收益权衡时保留不可比；探索不足时保留未知；有限任务上的相同结果只记为经验同等表现。
Preserve incomparability when costs and benefits trade off, unknown status when exploration is insufficient, and empirical equivalence when finite-task outcomes coincide.

时间等随机量采用重复试验，并报告不确定性；带误差容限的成对判断不能未经检查就声明为传递的全局序。
Repeat stochastic measurements such as time and report uncertainty; pairwise decisions with tolerances cannot automatically be declared a transitive global order.

记录相同背景下候选 A、候选 B、比较依据与结论，可供偏好训练或奖励模型学习；强化学习需要的标量或其他训练信号由后续训练接口明确生成。
Record candidates A and B in the same context, the comparison evidence and the outcome for preference training or reward-model learning; a later training interface must explicitly generate whatever scalar or other signal its reinforcement-learning method requires.

先建立可重放的比较证据，再选择训练算法；导出轨迹或偏好记录不等于已经完成强化学习。
Build replayable comparison evidence before choosing a training algorithm; exporting trajectories or preferences is not itself reinforcement learning.

## 新方向与延迟价值 / New directions and delayed value

旧任务上的重构收益是首个可验证目标；它不足以完整评价能提出新问题的新概念。
Refactoring gains on existing tasks are the first verifiable target, but cannot fully evaluate concepts that enable new questions.

后续增设有预算的多轮探索：候选可以诱导新对象、实例、一般化和推论，但新命题数量本身不作为价值奖励。
Later add budgeted multi-round exploration in which candidates induce new objects, instances, generalisations and consequences, without rewarding the number of new statements itself.

优先检查后续结果是否支持预留任务、连接原有结构或给出经验证的迁移；尚无独立用途的探索结果保留为证据待积累。
Prioritise whether downstream results support held-out tasks, connect existing structures or enable verified transfer; exploratory results without independent uses remain pending further evidence.

给候选定义发展配套引理的机会，并比较整包、子包和版本演化；本轮未找到收益不能推出该思想没有数学价值。
Allow definitions to develop supporting lemmas and compare packages, subpackages and successive versions; failure to find gains in one round does not establish that an idea lacks mathematical value.

## 首个 skill 的职责 / Responsibilities of the first skill

evaluate-theory-package 已创建，仓库版本见 [SKILL.md](../skills/evaluate-theory-package/SKILL.md)；其职责与下述研究目标衔接。
The evaluate-theory-package skill is created; see its [repository version](../skills/evaluate-theory-package/SKILL.md), whose responsibilities connect to the research goals below.

输入：固定实验清单、候选包、允许读取的开发或评价任务、预算和输出路径。
Input: a frozen experiment manifest, candidate package, permitted development or evaluation tasks, budget and output paths.

执行顺序：核对前提与阶段 → 检索适用位置 → 提出迁移计划 → 输出 Lean 证明与转换 → 调用检查器 → 修复预算内错误 → 汇总结构化证据。
Sequence: check assumptions and evaluation phase → retrieve application sites → propose a migration plan → produce Lean proofs and translations → invoke the checker → repair errors within budget → summarise structured evidence.

skill 指导 LLM 操作；程序检查证明、依赖、逐任务请求、提交预算和计费，独立的求解上下文与外部模型生成预算还需实验控制器管理。
The skill guides LLM operations; software checks proofs, dependencies, task-local requests, submission budgets and accounting, while the experiment controller must manage independent solver contexts and external model generation budgets.

LLM 可以提出新证明和找不到用途的解释，但其自我评价不作为通过验证或有效性的证据。
The LLM may propose proofs and explain unsuccessful searches, but its self-assessment does not count as proof verification or evidence of effectiveness.

只有实验驱动器冻结候选后，skill 才进入预留评价阶段；阶段间状态、可读文件与可写输出应由接口限制。
The skill enters held-out evaluation only after the runner freezes the candidate; interfaces should constrain state, readable files and writable outputs across phases.

## 第一个数学实验 / First mathematical experiment

主题：从只有群运算、公理与基本函数、集合操作的小型基础库，引入群同态及其核的理论包。
Topic: introduce group homomorphisms and kernels into a small base library containing group operations, axioms, and basic function and set operations.

这是把已知数学当作受控的新概念输入，用来检查评估系统；不声称发现历史上未知的数学。
Known mathematics serves as a controlled new-concept input to test the evaluator; this is not a claim of historically novel mathematics.

原有目标用函数 f 及条件 f(xy)=f(x)f(y)、集合 {x | f(x)=1} 等表达；v1 固定校准包含同态、核载体和乘法闭合，v2 在不改变基础的条件下另证单位元、逆元性质和核群结构；复合等更远的迁移仍待研究。
Original goals use a function f satisfying f(xy)=f(x)f(y) and sets such as {x | f(x)=1}; the frozen v1 package contains homomorphisms, kernel carriers and multiplication closure, while v2 proves identity/inverse properties and a kernel group over the unchanged foundation; more distant transfer such as composition remains to be studied.

在此基础上，预留不同推理模式的迁移任务，例如复合下核的描述、平凡核与单射的关系；具体划分在生成候选前固定，近重复归入同组。
Reserve transfer tasks with different reasoning patterns, such as kernels of composites and the connection between trivial kernels and injectivity; freeze the exact split before candidate generation and keep near-duplicates together.

对照包含基础库、仅命名、定义本体、定义与配套定理四种配置；计入各自成本，不预设完整理论包必然胜出。
Compare the base library, naming alone, definitions alone, and definitions with supporting theorems; account for each cost without presupposing that the full package wins.

首轮先准备一条完整、可检查的迁移作为参考轨迹，再扩展到约 20 个目标并由 LLM 在相同接口下尝试迁移。
First prepare one complete checkable migration as a reference trace, then expand to approximately 20 goals and let the LLM attempt migrations through the same interface.

## 里程碑与验收 / Milestones and acceptance

| 阶段 / Phase | 交付 / Deliverable | 验收 / Acceptance |
| --- | --- | --- |
| M0：设计 / Design | 本计划、实验范围与证据约定 / This plan, scope and evidence conventions | 明确当前实现与未来接口 / Clear distinction between existing and proposed capabilities |
| M1：可验证对照 / Verified comparison | 候选与实验清单格式、隔离 Lean 工程、一条参考迁移及结构化前后报告 / Package and experiment manifests, isolated Lean projects, a reference migration and structured comparison | 原目标在两边可检查；成本可追溯；对隐藏依赖、目标偷换及无证明断言给出正确状态 / Checked original goals in both conditions, auditable costs and correct handling of hidden dependencies, changed goals and unsupported claims |
| M2：系统化迁移 / Systematic migration | 约 20 个目标、LLM 调用接口、evaluate-theory-package skill 与完整轨迹 / Approximately 20 goals, an LLM interface, the skill and complete traces | 固定候选后评价预留集；两边预算公平；所有声称的改善有证书；允许无结论 / Frozen-package held-out evaluation, fair budgets, certificates for claimed gains and explicit inconclusive outcomes |
| M3：整包与延迟价值 / Packages and delayed value | 定义与配套引理的对照、多轮版本档案、成本与用途的比较 / Definition/lemma controls, multi-round archives and cost/use comparisons | 能区分单项贡献、组合效果、权衡与探索不足 / Distinguish individual contributions, joint effects, trade-offs and insufficient exploration |
| M4：学习接口 / Learning interface | 可重放轨迹、比较数据和选定训练算法的反馈适配器 / Replayable trajectories, comparison data and a feedback adapter for the selected learning algorithm | 在另一个冻结任务集上比较训练前后表现，并检查奖励投机 / Compare pre/post-training performance on another frozen task set and check reward exploitation |

M1 已完成参考迁移与完整审计；M2 的 [独立上下文实验](INDEPENDENT_EXPERIMENT.md) 已实际生成并核验 40 份见证，保留全部 46 次提交记录，但模型修订、采样和生成 token 未取得，预算公平性未验收；M3 的校准消融见 [包消融](PACKAGE_ABLATIONS.md)。
M1 has a reference migration and complete audits; M2's [independent-context experiment](INDEPENDENT_EXPERIMENT.md) generated and verified 40 witnesses and retains all 46 submissions, but model revision, sampling and generation tokens were unavailable, so budget fairness remains unaccepted; see [package ablations](PACKAGE_ABLATIONS.md) for M3 calibration.

已有父子版本的 [后续复用校准](VERSION_EVOLUTION.md) 在四个预选开发任务上得到 12 份核验证明、一次失败后修复和完整的包成本比较；这只完成 M3 的受控版本演示，并未完成自动候选搜索或严格预留效果验收。
The parent-child [later-use calibration](VERSION_EVOLUTION.md) yielded twelve checked proofs on four preselected development tasks, one failure followed by repair, and full package-cost comparisons; this demonstrates a controlled M3 version exercise without completing automatic candidate search or strict held-out effectiveness acceptance.

统一调用接口现已实现请求模型、响应模型标识、采样、生成用量与预算停止事件的记录，并完成单个公开任务上的真实调用校准，但不把模型别名当成精确修订证明；接下来应单独冻结包含新迁移模式、总实验预算和停止规则的协议，再比较同等资源下的版本，已公开的任务不得重新标为最终预留集。
The unified interface now records requested and response-reported model identities, sampling, generation usage and budget-stop events and has completed a live calibration on one public task, without treating model aliases as proof of exact revision; next, separately freeze a protocol with new migration patterns, total experiment budgets and stop rules before resource-matched version comparisons, and never relabel published tasks as a final held-out set.

后续已新增 [DeepSeek 冻结对照协议](METERED_TRANSFER.md)：候选 v2 保持不变，四个开发目标与四个新预留目标按推理模式分开，并实现阶段门控、整轮调用/输入/输出/费用预约及中断停止；预留目标的声明编译不算求解证据。
The additive controller preserves old evaluator fingerprints and calibration flags, uses only DeepSeek for new paid calls, and separates matched allocations, observed usage and effectiveness claims; formal model outcomes are recorded separately from offline fixtures.

DeepSeek 首轮开发校准的 16 次调用均在 2048 token 输出上限截断；独立的两次调用改用 8192 token 上限后，首个开发目标的两个条件均通过隔离 Lean，两轮合计费用含余量估算为 US$0.070540125，四个预留目标仍未调用。
This establishes a metered DeepSeek development workflow and exposes output-budget sensitivity, while remaining short of complete development coverage, strict reserved effectiveness, exact model-revision verification or training acceptance.

按用户不以 DeepSeek token 节省为约束的调整，后续使用宽松生成额度，d02、d03、d04 六个条件均通过隔离 Lean，开发集跨轮累计四题各两条件；完整保留 24 次调用及 16 次早期截断，合计含余量费用估算 US$0.133583625，整包源码账本为 1039→2019 token，未观察到净收益。
This completes observed development coverage across separate adaptive protocols, not one matched-budget formal experiment; source-cost aggregation charges the 1100-token candidate once and retains each original context and failure.

新的 [正式协议 v1](../experiments/metered_transfer_v1/protocol-formal-v1.json) 已完成同一次固定额度运行：开发集基础库 4/4、工具包组 3/4，预留集两边均 3/4、成功题目不同，13 份证明通过隔离 Lean，3 次拒绝保留，16 次调用用量完整且没有中断或预算越界。
This completes the small metered development-to-reserved workflow and its matched allocations, not representative model effectiveness; the five commonly solved goals cost 2572 baseline source tokens versus 3679 with the full 1100-token candidate charged once.

正式轮含余量费用估算 US$0.296767125，连同此前校准共 40 次 DeepSeek 调用、US$0.430350750，账户账单未核对；原始收据与逐阶段汇总均保存在本机，历史校准证明不补入正式覆盖。
M2 still needs broader task coverage and independence/repetition evidence, while exact model revision, automatic candidate search and learning remain unverified; completing the execution does not require a positive candidate result.

另在 d02、d03 上检查了明确复用现有引理的作者辅助参考证明，源码从 474→163、299→79 token，完整包成本后仍为 1342 对基础库 672，生成用量未知，不作为正式修复或模型成功率证据。
The user subsequently clarified that project correctness and optional shortening take priority over diagnosing individual model outputs; keep these references as historical diagnostics, not a mandate to repair each rejected proof.

已新增保留原证的独立选择层，正式汇总另列其事后证明组合：七个原有目标保留，两个更短替代使证明源码为 3975→3651，扣整包后净节省 -776，新增成功目标单列，原始模型通过率不改写。
Further necessary model checks remain DeepSeek-only, preserve strict-shorter retention and complete accounting, and require fresh reserved goals when earlier outcomes have informed revisions.

已在两道开发题上实际执行两种通用旧工具改写：四次扫描产生两份候选，均通过隔离 Lean，源码 220→217 的候选被采用，150→152 的候选保留记录而不替换，所选成本合计 370→367，全部 299 项测试通过。
This no-API pilot establishes replayable finite method execution and ordinary old-tool cleanup, leaving sufficient preparation, definition compatibility, model search and concept attribution unaccepted; the single sweep is exhausted without a later clean confirmation.

后续理论审查已区分定义、规格、实现、存在性、唯一性、命题与证明，分析实数、行列式及 Cayley–Hamilton 案例，并提出分层成本、条件偏序与 19 个反例验收案例。
The new theoretical note proposes explicit semantic contracts and layered evaluation; its general shared ledger, scope relations and acceptance cases remain design work rather than implemented or Lean-verified controls.

下一步先审查这些规则是否会错误奖励偷换目标、隐藏依赖或任意拆分，再用三个小案例搭建最小验证：构造转存在性、较长分解的复用、推广后保留原命题。
Audit these rules for counterexamples first, then implement a small validation covering realization evidence, reuse of a longer decomposition and retention under generalization.

M1 参考迁移的局部证明体为 77→29 个 token，总非共享源码为 89→353 个 token；阶段验收依据证据完整和可重放性，不要求候选得到正收益。
The M1 reference proof body is 77→29 tokens and total nonshared source is 89→353 tokens; acceptance depends on complete replayable evidence, without requiring a positive gain for the candidate.

## 与当前代码的衔接 / Connection to existing code

当前 maam/proofs.py 在调用方提供的有限规则上计算树证明成本，规则本身的逻辑有效性由调用方负责；reuse_gain 只支持一个已可导命题在固定图中的复用。
Current maam/proofs.py computes tree-proof costs over caller-supplied finite rules, whose logical validity remains the caller's responsibility; reuse_gain supports one already-derivable proposition reused within that fixed graph.

maam/theory.py 与 PackageCheck.lean 提供隔离编译和目标审计；maam/migration.py 管理逐任务请求、预算及提交；maam/independent.py 记录独立求解上下文的输入输出；maam/evolution.py 记录版本祖先、后续依赖路径、失败及完整包成本；maam/generation.py 绑定原始响应、用量与 Lean 结果，maam/live_calibration.py 管理私密凭据和小额校准，scripts/lean_sandbox.py 隔离宿主资源，既有评估器指纹保持不变。
The additive maam/transfer.py controller now audits matched DeepSeek allocations across both phases; scripts/summarize_formal_transfer.py replays one formal run offline and includes earlier calibration costs without importing their proofs or promoting the result to general effectiveness or training claims.

Mathlib 索引、压缩计数、PageRank 和源代码分析可复用作检索及描述；第一轮受控实验采用隔离基础库，以免完整 Mathlib 已经包含待引入概念。
The Mathlib index, compression counts, PageRank and source analysis remain useful for retrieval and description; the first controlled experiment uses an isolated base so full Mathlib does not already supply the candidate concepts.

M2 的公开校准接口见 [迁移协议](MIGRATION_PROTOCOL.md)，新的 20 题实测见 [独立上下文实验](INDEPENDENT_EXPERIMENT.md)；源码与完整表达式出现权衡，当前输出保留条件性不可比，尚未转成强化学习奖励或偏好标签。
See the [migration protocol](MIGRATION_PROTOCOL.md) for M2 calibration and the [independent-context experiment](INDEPENDENT_EXPERIMENT.md) for the new 20-task run; source and complete-expression costs trade off, so outputs retain contextual incomparability without converting it into an RL reward or preference label.

## 参考文献 / References

- Aksenov, Bodnia, Freedman, Mulligan. [Compression is all you need: Modeling Mathematics, Section 5.2](https://arxiv.org/html/2603.20396v1#S5.SS2).
- Barkeshli, Douglas, Freedman. [Artificial Intelligence and the Structure of Mathematics, Sections 4.4–4.6](https://arxiv.org/html/2604.06107v1#S4.SS4).
- Grand et al. [LILO: Learning Interpretable Libraries by Compressing and Documenting Code](https://arxiv.org/abs/2310.19791v4).
- Bowers et al. [Top-Down Synthesis for Library Learning (Stitch)](https://arxiv.org/abs/2211.16605v2).
