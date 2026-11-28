# 证明预压缩与理论边际价值 / Proof precompression and marginal theory value

| 中文 | English |
| --- | --- |
| 新增[成组求证控制器](GROUPED_PROOF_SEARCH.md)：共同预压缩、冻结、控制与候选阶段，支持在整组中复用局部辅助引理并核验全部原目标。 | Added a grouped controller with shared preparation, freezing, control and treatment phases, local shared helpers and verification of every original goal. |
| 两种有限旧工具方法已可生成候选并自动执行，双方使用同样的响应与 Lean 预算上限。模型生成用量与外部信息隔离仍需另行计量。 | Two bounded existing-tool methods generate candidates automatically under equal response and Lean caps. Model usage and external information isolation require separate evidence. |


理论稿 2026-11-27 · 项目接入 2026-11-28

| 中文 | English |
| --- | --- |
| 固定背景、公理和最终目标，允许改变中间命题、共享引理和证明路线。 | Fix the foundation, axioms and final goals while allowing different intermediate statements, shared lemmas and proof routes. |
| 同表示、整包计费、无预算限制时两侧允许交付同一组合；有限预算实验测量提供候选后的观测帮助。 | Under identical representations and complete accounting, unlimited search admits the same final portfolios. Bounded experiments measure the observed effect of providing a candidate. |
| 可选采用、完整建库、已建库复用有各自的账本。 | Optional adoption, mandatory delivery and installed reuse have distinct ledgers. |
| 本入口测量给定完整路线。自动发现与同预算搜索仍需后续实现。 | This entry point measures supplied complete routes. Automatic discovery and matched search remain future work. |


## 1. 我们究竟在问什么

给定一组已经有证明的定理，以及一个准备引入的理论包，旧证明与新证明之间的长度差可能包含三份收益：清理旧证明的收益、继续搜索其他证明的收益、提供候选理论后才观察到的额外收益。前两项已经写入 MAAM 的基线理论。本稿进一步规定可以改到哪一层、三种收益各自回答什么问题，以及局部结论如何通过跨目标检验。

有三个问题值得分别保留。

| 问题 | 比较条件 | 所得结论 |
|---|---|---|
| 把旧证明重新组织一次，能缩短多少？ | 同一背景、同一组目标，比较历史版本与经过预压缩的版本 | 普通整理和重新求证的已实现收益 |
| 把候选理论交给求证者，到底帮了多少？ | 两方从同一基线继续搜索，只有一方获得候选包，投入相匹配 | 在特定资源、任务和信息条件下的提供收益 |
| 这个抽象值得纳入共同数学语言吗？ | 计入建库成本，比较多组目标的联合成本，并在新目标上检验迁移 | 有范围的复用证据，可随任务和使用者改变 |

## 2. 固定目标，开放中间陈述

**定义 1（背景与证明组合）。** 令 $K$ 为双方共享的语言、基础库、公理和检验规则。令 $G$ 为用共同语言事先陈述的一组目标。一个可接受的证明组合 $P$ 包含从 $K$ 建立这些目标所需的新增定义、引理、证明、表示转换，以及重放所需的额外自动化。其接口须能在原来的语言中交付 $G$。记 $L_K(P)$ 为在预先选定的口径下，整个组合相对于 $K$ 的成本。本文用越小越好的费用举例。搜索消耗另记。

基础库可以免费复用，因为双方得到同一份。新发现的共享引理属于产出的证明组合，只计一次。若预压缩产生了一个共用工具，两组都能从同一份工具开始，但只要它是待交付证明的一部分，它仍属于这一轮的完整账本。一个分支若能去掉该工具，也应能取得这部分节省。这样可防止借“冻结基线”把历史负担永久设为免费。

**定义 2（候选盲的预压缩）。** 在获得待评理论 $T$ 及其特有提示前，使用旧背景 $K$ 对旧证明和实际调用处联合搜索，保留经过检查的可重用证明。搜索可检索已有定理，也可发明辅助引理、改变中间命题、跨模块展开并重新命名、另走一条证明路线。只要最终接口和公理条件成立，中间节点无须一一对应。一个有预算的搜索得到一组可复用的候选路线和一个当前最好值；停止条件由预算或约定的规则给出。它不赋予结果“最短证明”的地位。

旧路线应当作为备选保留，尤其是在多个目标共享引理时。某条新路线即使对单个目标暂时更长，也可以进入一次联合比较。如果每个中间替换都被要求当场变短，建立共享概念所需的前期投入可能永远无法发生。

**命题 1（跨边界替换）。** 设旧推导以 $a:A$ 为输入，经 $u:A\to I$ 和 $v:I\to G_1$ 得到目标。若找到经检验的 $u':A\to H$ 和 $v':H\to G_1$，则 $v'(u'(a))$ 也是该目标的证明。若 $I$ 的其他调用仍需要旧接口，它们须保留旧证明、另有桥接或一并重证，才可从联合账本删去旧分支。

**证明。** 新推导由复合得到。逐一保留或替换其余调用，便为每个原目标给出证明。凡仍从其他目标可达的共享声明，都还有使用者。若中间对象进入依赖类型或目标含有带规格的算法输出，同样须在原接口上证明相应的类型转换、等式或行为规格。∎

这里没有要求 $I$ 与 $H$ 等价。若 $I=P\land Q$ 而所有调用只取第一分量，可尝试直接构造 $P$。反过来，若另一个目标确实需要 $Q$，则两个调用合起来可能正好证明保留 $I$ 更合算。展开的作用是看见这些调用；重新封装的依据是它们实际共享的数学。

## 3. 一个界限定理：无限搜索与有限提供

**命题 2（相同表示语言下的最优值）。** 假设以下条件成立。

1. 候选 $T$ 的全部定义和证明都可在 $K$ 中合法写出，旧侧允许任意构造这类有限辅助包。
2. 两侧允许相同的最终表示，使用相同的编码与成本函数。凡采用 $T$ 的最终组合，都须按同一规则支付其内容的费用。
3. 获得 $T$ 的一方可以忽略它，保存原来的任何证明组合。这里暂时考察所有可行组合，不限制发现它们所需的搜索。

记 $\mathcal P_0$、$\mathcal P_+$ 为未预先给出和预先给出 $T$ 时可交付的全部组合。则

$$
\inf_{P\in\mathcal P_0} L_K(P)
=
\inf_{P\in\mathcal P_+} L_K(P).
$$

**证明。** 任取右侧组合。若它采用 $T$，旧侧可以逐字提交同一理论包以及相同的下游证明，付出完全相同的费用；若它未采用 $T$，旧侧也可直接提交。反向包含由第三项给出。两边甚至可以交付同一份文件，故成本下确界相等。∎

这个结论给出了三种有内容的比较方式。

- **给定有限预算。** 短证明在两边都存在，只有获得 $T$ 的一方可能及时找到它。可测量固定预算下的已核验成本，也可固定成本门槛，测最早找到达标证明所需的资源。
- **固定可用的表示。** 例如，一边要求每个目标独立书写，不得新增跨目标共享名称；另一边允许使用一套明确写出并付费的共享定义。此时可行组合的集合确实不同，可以研究表示制度带来的真实长度差。结论要带上这一限制。单纯封禁名称无法阻止等价的数学构造换名出现。
- **固定已经建好的库。** 如果 $T$ 已为其他用途付费并安装，后续任务可比较以 $K$ 或 $K+T$ 为背景的边际使用成本。若问题改为“今天是否值得首次建立 $T$”，就要恢复建库费用。一个结论不能同时充当这两种决策的答案。

若候选含额外公理、未经证明的猜想或外部黑箱，应标为条件性比较，并声明新增假设。命题 2 的第一项在这种情况下可能失效。研究猜想 $A$ 的条件性压缩价值时，仍可以检查 $A\to G$ 的证明并计量其长度，但报告应保留所假设的 $A$。

## 4. 有限预算下怎样分账

在一项费用口径和同一组已证目标上，令 $H$ 为历史证明组合成本，$B$ 为候选盲预压缩后的最好成本。冻结同一批检查过的起点，随后做两组相同额外预算的搜索。记 $C_0$ 为继续只用旧工具得到的最好完整成本，$C_+$ 为预先提供 $T$ 所得的最好完整成本。两组都可保留共同起点；采用候选的组合须支付候选包及桥接的费用。于是

$$
H-C_+=(H-B)+(B-C_0)+(C_0-C_+).
$$

三项依次是**预压缩收益、继续搜索收益和提供候选的观测净差**。这是已有 MAAM 分账在整包成本口径下的写法。若指标用整包压缩后的字节数，应分别序列化完整组合后作差。把两个单独压缩的文件大小相加，未必等于它们联合压缩的大小。

**可选使用与强制交付。** 若要问是否值得正式纳入库，应另报“必须随成品交付完整 $T$”的成本，哪怕某些目标仍沿用旧证。若问的是向求证者提供 $T$ 有没有帮助，可以保留忽略 $T$ 的候选；完整交付与可选使用这两个最优值可能不同。实际使用的部分若是新打包的精简理论，须单列为 $T'$，连同提取、证明和转换成本重新比较。

**成对比较的边界。** 两侧使用同一求证者版本、旧路线、反馈权限和事先约定的资源上限，分别保存成功与失败的尝试。若搜索含随机性，可对同一组任务做多次配对，报告逐对差额与离散程度。某次净差只描述这次搜索；要把平均差额解释为提供候选的效应，还需隔离跨组信息、控制次序和算力，并说明任务如何抽取。候选的发明成本若已知，可另报；提前获得外部候选的实验只测提供后的效果。

**估计的方向。** 每一边找到的有效证明都给该边最优成本一个上界。两个上界相减，一般既非真实最优差的上界，也非下界。如果某个受限问题还能给两侧最优值 $m_0,m_+$ 分别建立界 $l_i\le m_i\le u_i$，则 $m_0-m_+\in[l_0-u_+,u_0-l_+]$。有限枚举有时可以做到这一点。一般实验更适宜报告预算、单次或重复搜索的结果与不确定性。保留共同起点只保证两侧各自不劣于起点；某次旧侧搜得更好，观测净差可以为负。

**什么成本值得同时记录。** 源码的联合描述长度、内核检验的证明表示大小、生成与验证的资源、对独立任务的迁移表现分别报告。对两个方案，若一个在所选所有指标上都不差、至少一项更好，可以在该范围内给出偏序；若次序冲突，则保留两者。人类理解成本需要阅读、复述或迁移测试，单凭行数与压缩字节都测不出来。

## 5. 算例：同一项理论会出现三个不同的数字

以下是可手算的加性模型，数值为设定的记账单位，不代表任何 RH 实测。两道题 $A,B$ 历史证明合计为 180，预压缩后为 110，旧侧继续搜索后各为 46，合计 92。另一侧采用一个成本为 60 的共享引理包，每道题再用 9，合计 78。假定这些是这次两组实际找到的方案，且没有其他共享费用。

| 所问问题 | 计算 | 含义 |
|---|---:|---|
| 相对历史记录缩短多少 | $180-78=102$ | 全轮改进 |
| 提供候选相对于同预算旧侧多省多少 | $92-78=14$ | 在两题上的观测净差 |
| 单独为一道题建立该包是否划算 | $46-(60+9)=-23$ | 首次采用会增加成本 |
| 包已为其他任务建好，再解决一道题能省多少 | $46-9=37$ | 继续使用的边际节省 |

核对分账得到 $102=(180-110)+(110-92)+(92-78)=70+18+14$。如果有 $k$ 道同成本、同样适用的题，在这两条给定路线之间，共享方案占优当且仅当 $37k>60$。这给出了两题的盈亏分界，未对实际数学任务的分布作任何假设。允许对照组自行发明同一个包，与算例相容；本次对照搜索恰未找到它。

**一个真正的数学例子。** 设 $f:M\to N$ 是模同态，$U\subseteq\ker f$。要构造 $\bar f:M/U\to N$，可以直接令 $\bar f([x])=f(x)$：若 $x-y\in U$，则 $f(x)-f(y)=0$，所以定义与代表元无关；线性由 $f$ 的线性得到，唯一性由商映射满射得到。若多个目标反复进行这段推导，预压缩可以把它封装为商模的泛性质。假如待评候选恰是这条泛性质，这就构成一次可能的独立重建。可预留另一道题检验迁移：给定 $f(U)\subseteq V\subseteq N$，其中 $V$ 是子模，先将 $f$ 与 $N\to N/V$ 复合，再由泛性质得到 $M/U\to N/V$。这次转用只需证明复合在 $U$ 上为零。两份构造都能逐步检查；它们到底省了多少描述或搜索成本，仍要按固定语言实测。

## 6. 从一个证明走向一套数学

设 $G$ 是眼前的目标，$U$ 是独立选定的相邻目标。分别考察 $G$、$U$ 和 $G\cup U$ 的联合成本。可以在 $G$ 中移去的分支，可能在 $U$ 中值得重用；一个单题无力负担的新结构，也可能在联合任务中回本。各目标单独压缩再求和，会反复收取共享成本，也看不见跨题重新组织的机会。对“全局”的每一项判断都要说明目标集合、背景和核算边界。若未来目标只能用分布描述，该分布或几种备选情形也应公开。

**候选由谁提出，决定能声称什么。** 若 $T$ 在预压缩中自然萌生，原来的题可以展示发现过程。冻结 $T$ 的陈述和费用后，到此前未参与选择的任务上比较迁移；旧侧可以再次独立发现相同内容。若 $T$ 是已知的外部候选，旧侧应获取同等的一般信息与搜索资源，只隔离候选特有提示。对公开成果，已看过答案的研究者或模型所做的重建应标为回顾性重建。

**重新发现值得记录。** 两侧使用不同名字时，先核对命题和被调用的性质。对于不同表示，给出能支持这些用途的双向翻译或明确等价证据，并计入必要桥接；若只能证明一侧蕴含另一侧，就只记录这个方向。如果两侧最终找到同一构造且付出相近成本，提前提供的观测收益可能很小，而重复发现仍是这个概念值得迁移检验的理由。它本身还不能证明广泛价值。

已有证明的压缩实验总有历史备选。若另测新题，一侧未在预算内找到证书时，要记录成功率、预算和覆盖范围；可比成本只在双方成功的任务上计算，并标明样本选择。这样才能区分“更容易找到证明”和“已经找到的证明更短”。

## 7. 用 RH 案例检验这套说法

Sernau 等人的可读版和紧凑版给出同样的五个最终结论，独立检验覆盖了两版。按作者的说明，跨模块展开、另寻局部论证和重新封装都参与了精简。它为预压缩提供了一类有实例支持的搜索操作。单次公开成功无法确定这类操作的一般收益，也无法把两版大小之差归给某一个数学思想。[作者仓库](https://github.com/lsernau/grh-lean) · [作者的讨论](https://leanprover.zulipchat.com/#narrow/channel/658556-Riemann-Hypothesis/topic/New.20proof.20in.20300k.20lines/near/643702366) · [独立检验](https://math.mit.edu/~drew/shortgrh/)

提炼案例时可同时保留两份产物。第一份是经检查的整套证明和按同一口径得到的成本。第二份是理论线索，注明哪些中间结论被弱化、绕开、独立重建或跨目标复用，以及每一条判断有何证据。第一份用于比较证明，第二份用于提出下一个可检验的数学问题。

这套框架继承了 Aksenov、Bodnia、Freedman、Mulligan 关于分层定义和引理可以压缩数学表述的出发点。MAAM 原有的基线准备已经分开历史节省与有限搜索后的净收益。本稿新增的是跨边界替换的有效条件、相同表示语言下的最优值命题，以及首次采用、提前提供、持续复用三个比较口径。文中的形式命题在给定假设下有证明，算例只展示推理，没有运行新的求证实验。[原论文](https://arxiv.org/abs/2603.20396) · [MAAM 原有基线理论](https://github.com/Love-in-idleness/MAAM/blob/cd6be57574b912ec72225a8f9a8d16d02504f4f4/docs/BASELINE_PREPARATION.md)

## 8. 工具入口 / Executable interface

```bash
python -m maam precompression \
  --study experiments/precompression_v1/study.json \
  --output /tmp/precompression-report.json
```

| 中文 | English |
| --- | --- |
| 每条路线交付全部目标，新增模块以 SHA-256 冻结并各计一次；历史和预压缩起点由两侧继承。 | Each route declares all targets. New source modules are pinned and charged once. Both arms inherit historical and prepared routes. |
| 控制侧可以重新构造同一候选。具名候选的任一模块被使用时，整个包都计费；精简候选需另有版本。 | Control may rediscover the same candidate. Using any named candidate module charges the entire package. Trimmed candidates require their own versions. |
| 可选采用保留原路线，完整建库在各备选上联合计入完整包，已建库复用单列边际差额。 | Optional adoption retains old routes. Mandatory delivery includes the full package in every alternative. Installed reuse reports a separate marginal difference. |
| 三种度量分别择优：源码 UTF-8 字节、zlib-9 联合压缩、bzip2-9 联合压缩。 | Three metrics select independently: raw UTF-8 bytes, joint zlib-9 and joint bzip2-9. |
| 源码计量只检查结构、指纹和声明的覆盖。目标实际交付、导入闭包和公理需独立形式核验。 | Source measurement checks structure, hashes and declared coverage. Actual goals, import closure and axioms require separate formal verification. |

完整输入见 [study.json](../experiments/precompression_v1/study.json)。每项 source 指定相对路径及 SHA-256。背景与原目标规格共同冻结，背景原源码不收费，交付文件里的导入行保留。新增辅助定义和桥接仍在各自路线中收费。序列化和压缩参数与历史整包计量一致，旧脚本保留其归档版本。

The runnable manifest lists a schema version, phase, study ID, target names, background modules, candidate ID and modules, source descriptors, and complete routes with stage labels. Background bytes are excluded while imports remain. Helpers and bridges are charged. Regression tests compare the new joint encoder against the immutable archived reference.

源码报告始终保留 search_executed=false、information_separation_established=false、baseline_search_complete=false、package_attribution_ready=false。每种指标分别做分账，不对独立压缩的包与证明直接求和。

Source reports establish no search, information isolation, baseline completion or attribution readiness. Each metric gets its own accounting. Entire portfolios are jointly compressed rather than adding independently compressed package and proof sizes.

## 9. 新 Lean 校准与下一步 / Fresh Lean calibration and subsequent work

```bash
python scripts/check_precompression.py \
  --lean /path/to/lean-4.33.1/bin/lean \
  --workdir /tmp/precompression-lean-new \
  --output /tmp/precompression-checked-new.json
```

| 中文 | English |
| --- | --- |
| 两道命题逻辑题的历史、预压缩、控制、包侧四组给定证明新编译，使用原审计器检查目标类型、导入和空公理列表。 | Four supplied variants of two propositional goals are freshly compiled and checked against original types, imports and empty axiom lists by the existing auditor. |
| 原始新增源码为 405→233→173 字节，依次为历史、预压缩和控制。 | Raw source costs are 405→233→173 bytes for historical, prepared and control. |
| 包侧可选结果 233，完整建库 333，已建库复用 225。可选包侧的观测净差为 −60。 | Optional treatment costs 233 bytes, mandatory delivery 333 and installed reuse 225. The optional observed difference is −60. |
| 这是核验与计量校准。自动发现、跨模块重写控制器和同预算模型实验仍待实现。 | This calibrates verification and accounting. Automatic discovery, a cross-module controller and matched-budget model experiments remain future work. |

[任务迁移](MIGRATION_PROTOCOL.md)仍以单个固定目标的证明体为工作单元。[保留原证](RETAINED_COMPRESSION.md)继续保留其历史协议。完整路线入口可接受改变了中间陈述的源码组合，但调用方必须为全部目标提供核验。后续可添加成组请求、共享辅助模块生成、整组形式收据和匹配预算，将搜索结果接到这份计量协议。

Existing migration accepts a single fixed proof body, and retained-proof measurement preserves its historical protocol. Complete routes may change intermediate statements, with all targets verified externally. A later controller can add grouped requests, shared-helper generation, whole-goal receipts and matched budgets.

独立校准报告见 [precompression-calibration-v1.json](../results/precompression-calibration-v1.json)。旧报告与冻结实验保持其原指纹，新状态不把历史结果提升为新协议实验证据。

The calibration report retains fresh audits, measurements and log hashes. Existing frozen experiments keep their fingerprints and are not promoted into evidence for the new search protocol.
