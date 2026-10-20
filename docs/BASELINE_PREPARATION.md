# 引入理论包前的基线准备 / Baseline preparation before theory packages

日期：2026-10-20；当前重心是理论论证、工具搭建与小范围检查，大规模实验暂缓。
Date: 2026-10-20; the current focus is theory, tooling and small checks, with large experiments deferred.

## 比较什么 / What the comparison measures

先充分利用原有条件整理定义、检索已有引理并缩短证明，再评价新增理论包，避免把普通整理的收益算到新概念头上。
First improve definitions and proofs using the existing resources, so ordinary cleanup is not credited to a new concept.

将整理后并已版本化的旧知识环境记为 \(K^*\)，它包含允许使用的定义、定理、依赖、自动化规则与工具配置；加入候选包前冻结这些内容及其指纹。
Write \(K^*\) for the optimized and versioned old environment, including its permitted definitions, theorems, dependencies, automation and tool settings, and freeze their fingerprints before introducing a candidate.

目标集、原始目标的含义与源码计量规则同时固定，原有核验证明始终保留，只有通过检查且严格更短的备选证明才替换当前选择。
Freeze the goals, their original meanings and the source metric as well, retain checked old proofs, and replace a selected proof only with a checked, strictly shorter alternative.

没有适用线索的目标可以跳过，不要求所有旧定理使用新包重证；新增可解目标另列，不把不存在的旧证明当作零成本证明。
Targets without a plausible application may be skipped, old theorems need not all be reproved with the package, and newly solved goals are reported separately rather than assigned zero-cost old proofs.

## 分开三种收益 / Separate three sources of savings

在同一组原有目标及同一核算边界内，令 \(H\) 为历史证明组合的成本，\(B\) 为旧工具优化后冻结的组合成本，\(C\) 为从 \(B\) 出发继续使用旧工具搜索后的成本，\(T\) 为从同一 \(B\) 出发允许新包后选中证明及其非包辅助内容的成本，\(p\) 为完整候选包成本。
For the same original goals and accounting boundary, let \(H\) be historical portfolio cost, \(B\) the frozen old-tool-optimized cost, \(C\) the cost after further old-tool search from \(B\), \(T\) the selected proof and nonpackage auxiliary cost after package-assisted search from the same \(B\), and \(p\) the complete package cost.

所有数量使用同一单位，未知成本保持未知；源码、生成用量、时间与费用分别报告。
Use the same unit for these quantities, keep unknown costs unknown, and report source size, generation usage, time and money separately.

\[
\underbrace{H-(T+p)}_{\text{historical net saving}}
=\underbrace{H-B}_{\text{old-tool preparation}}
+\underbrace{B-C}_{\text{continued old-tool search}}
+\underbrace{C-T-p}_{\text{package-associated net difference}}.
\]

证明只需展开右侧，\(-B+B\) 与 \(-C+C\) 抵消；这是分账恒等式，不是证明新包具有普遍价值的因果定理。
Expanding the right side cancels \(-B+B\) and \(-C+C\); this is an accounting identity, not a causal theorem establishing general package value.

`maam/attribution.py` 检查同单位非负成本与保留原证的单调性，分别计算这些项，缺失输入保留未知，不把分账通过当作已完成基线搜索或因果验证。
The accounting helper validates the numerical retention contract and propagates unknown values; proof correctness, matched search and semantic compatibility require separate evidence.

如果历史与优化后的定义版本不同，必须保持目标语义和核算边界一致，并把定义整理及必要转换的成本纳入相应组合，否则不作上述数值归因。
If historical and optimized definitions differ, keep goal semantics and accounting boundaries compatible and include refactoring and required transport costs in the relevant portfolios, or decline the numerical attribution.

有限规则示例会展示历史表面净节省 45，而相对于原规则最优证明的净节省为 −15，两者相差的 60 来自旧工具优化。
The finite-rule example demonstrates historical apparent net savings of 45 but net savings of −15 against the old-rule optimum, with the difference of 60 coming from old-tool optimization.

该示例只在调用方给定的有限树证明图及成本规则内求最优，规则的逻辑有效性由调用方负责，不能当作 Lean 检查或一般数学证明的全局最短性证据。
Its optimum concerns only the supplied finite tree-proof graph and cost rules, whose logical validity remains the caller's responsibility; it establishes neither Lean validity nor global minimality for general mathematical proofs.

## 定义、共享内容与继续搜索 / Definitions, sharing and continued search

仅依靠旧工具就能完成的定义整理，发生在两边共同使用的旧环境中；依赖新理论的公理化、接口改造或表示转换，属于加入新包后的候选效果，并计入相应验证和桥接成本。
Old-tool refactoring belongs in the shared preparation stage; specification or representation changes enabled by a new theory belong after its introduction, with their verification and transport costs charged.

原任务的对象、参数、假设及结论要固定，并给出结构对应与所需方向的核验回传；任意两个已证命题都可建立逻辑等价，所以单独一个 `iff` 不能作为任务身份判据。
Fix the original objects, parameters, assumptions and conclusion and audit their structural interpretation and result transport; an arbitrary equivalence between proved propositions is insufficient for task identity.

构造、规格、存在性、唯一性及计算接口分别保留来源和依赖；更一般的命题作为新节点，原命题通过特化连接，具体例子及分层核算见[压缩理论框架](COMPRESSION_FRAMEWORK.md)。
Keep provenance and dependencies for constructions, specifications, existence, uniqueness and computation, and connect broader statements to retained originals by specialization as detailed in the framework.

原有共同背景的成本可以抵消，但新增旧工具辅助引理、别名、桥接及包依赖要计入各自组合，共享内容只计一次，不能藏入导入文件。
Common existing background cost may cancel, but new old-tool helpers, aliases, bridges and package dependencies belong in their respective portfolios, with shared content counted once rather than hidden in imports.

逐证明严格缩短是保留策略，并不保证含共享内容的整个库已经达到最小成本；若共享成本使总收益不明，就报告未知或权衡。
Strict per-proof shortening is a retention policy, not a guarantee of minimum total library cost with sharing; report unknown value or trade-offs when shared costs prevent a clear comparison.

冻结 \(B\) 后，对照组仍获得与包组相匹配的额外搜索机会，使用预先确定的目标选择规则、模型设置、预算上限与停止规则，两边均可继承 \(B\)。
After freezing \(B\), give the control matched opportunities for further search under predetermined target selection, model settings, budget limits and stopping rules, and let both arms inherit \(B\).

相同预算上限不等于实际消耗相同，应保留完整尝试与实际资源账本，不能只挑包组的成功结果。
Equal budget limits do not mean equal actual consumption, so retain every attempt and the observed resource ledger rather than selecting only package successes.

证明过的保守扩展提供表示和搜索工具，实验不能把这种帮助解释为增加了原基础的逻辑强度。
A proved conservative extension supplies representation and search tools; its assistance does not establish increased logical strength over the original foundation.

## 最小准备门槛 / A minimal preparation gate

准备清单应记录旧环境与检查器指纹、原目标和证明证书、计量规则、允许工具、有限搜索计划、预算、完整尝试及停止原因。
A preparation manifest should record environment and checker fingerprints, original goals and proof certificates, the metric, permitted tools, a finite search plan, budgets, all attempts and stopping reasons.

只有声明范围内的旧工具搜索已经执行完毕、保留证明有效、依赖及定义转换检查通过、证据冻结后，才能把基线标记为“在声明搜索范围内准备完成”，再接受包组比较。
Mark a baseline prepared within its declared search scope, and admit a package comparison, only after completing that scope's old-tool search, checking retained proofs, dependencies and definition transport, and freezing the evidence.

一次或多次没有发现改善不能保证真正最短，未尝试和未知也不能自动算作完成；以后找到更短旧证时需要更新基线并重新冻结比较。
One or more passes without improvement do not guarantee true minimality, unattempted or unknown work does not count as completed work, and a later shorter old-tool proof requires an updated baseline and a new comparison freeze.

对一般 Lean 证明只报告给定资源下找到的最好结果，有限图示例中的精确最优性不外推到一般证明搜索。
For general Lean proofs report only the best result found under the declared resources, without extrapolating exact finite-graph optimality to general proof search.

## 当前工具与下一步 / Current tool and next step

本轮首个工具仅建立离线清单：重放已有 baseline 会话的证书，在最多四个明确选定的开发目标上选取观察到的最短旧工具证明，并冻结知识环境、证书、计量与检查器指纹。
The first tool builds only an offline inventory: it replays existing baseline session certificates, selects the shortest observed old-tool proofs for at most four explicitly selected development goals, and freezes knowledge, certificate, metric and checker fingerprints.

以下命令中的 `--session` 和 `--task` 可重复，输出文件必须尚不存在。
Repeat `--session` and `--task` as needed, and choose an output file that does not already exist.

```bash
.venv/bin/python scripts/prepare_baseline.py \
  --session data/transfer-deepseek-formal-prepared-20261020/stages/development/baseline \
  --task d01 --task d02 \
  --output data/baseline-inventory-example.json

.venv/bin/python scripts/check_baseline_attribution.py \
  --output data/baseline-attribution-example.json
```

清单工具始终保留 `baseline_search_complete: false` 和 `package_attribution_ready: false`，已有证书的最短选择不等于已经充分搜索，历史实验也不因此变成归因就绪。
The inventory keeps `baseline_search_complete: false` and `package_attribution_ready: false`: selecting the shortest existing certificate does not establish sufficient search or make historical experiments attribution-ready.

本次实际重放了四个已有 DeepSeek 基础库会话，在四道开发题上选取的原证共 990 个源码 token，而正式轮单次 baseline 为 1350，相差 360；这是整理已存在证书的结果，没有新生成或新 Lean 核验。
This 360-token difference belongs to old-tool preparation, not a new-package gain; all failed attempts remain in the source records, and existing generation costs must be read from their original metered ledgers.

后续已搭建[小范围旧工具搜索记录流程](BASELINE_SEARCH.md)，可以给出绑定原证的请求、接收候选或保留决定并调用检查器，但本地响应流程完成不等于基线充分优化，原始清单的未就绪标志不改写。
The supplied-local workflow enforces strict shortening and clean complete sweeps; the [local method executor](BASELINE_METHODS.md) now provides actual deterministic rewrite evidence, while metered solver integration and definition-compatibility acceptance remain unfinished.

继续扩充搜索工具之前，优先复核[理论框架](COMPRESSION_FRAMEWORK.md)中的任务身份、共享成本和反例案例；该文档的设计要求尚未成为当前控制器的通用验收能力。
Prioritize auditing semantic contracts, sharing costs and counterexamples before expanding search tools; the framework's requirements are not yet general controller capabilities.

大规模实验留到用户指定的未来 `gpt6bel` 可用且身份确认之后，再明确配置和冻结新协议；本计划不声称它已经发布，也不会自动切换模型。
Defer large experiments until the user-designated future `gpt6bel` is available and its identity confirmed, then specify settings and freeze a new protocol; this plan asserts no release and makes no automatic model switch.
