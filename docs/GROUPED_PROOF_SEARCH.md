# 成组预压缩与共享引理 / Grouped precompression and shared helpers

2026-11-28

| 中文 | English |
| --- | --- |
| 将完整路线计量接到可提交、可修复、受预算限制的成组求证。 | Connect complete-route measurement to grouped proof submissions, repairs and bounded attempts. |
| 固定每道原目标的名字与定义，控制器构造其合取，并复用原迁移核验器。 | Fix each original goal constant. The controller constructs their conjunction and reuses the migration verifier. |
| 共享辅助引理写在整组成证明的局部作用域内，按实际完整源码计一次。 | Shared helpers are local to the entire group proof and charged once in its complete source. |
| 双方继承同一批已核验预压缩路线。控制组请求不含候选源码，也不含另一侧反馈。 | Both arms inherit the same verified prepared pool. Control requests contain neither candidate source nor opposite-arm feedback. |
| 两种固定旧工具方法已可自动执行。一般跨模块重构和独立计量的模型生成仍是后续工作。 | Two fixed existing-tool methods run automatically. General cross-module refactoring and independently metered model generation remain future work. |

## 工作单元 / Unit of work

设原目标是 $G_1,\ldots,G_n$。控制器从原名字生成共同的规格
$G_1\land\cdots\land G_n$，并为每个目标接收一个 Lean 证明项。工作者可以提交局部辅助定义、`have` 引理或其他局部证明构造，供所有目标共同使用。控制器用明确的原目标类型标注每个分量，再构造合取。整个结果沿用 Init 核心背景和三个标准公理策略，通过旧 `PackageCheck.lean` 的类型、导入、公理及声明审计。一个分量错误会使整个尝试失败。用户提供的目标定义仍属于冻结背景。

For original goal constants $G_1,\ldots,G_n$, the controller generates their conjunction in a shared specification module. Each submitted component is annotated with its original type, then combined under a shared local context. The unchanged auditor checks the conjunction, all local declarations, imports and axioms. Conjunction elimination recovers every original goal. This interface supports local helper tactics and definitions. It inherits the migration verifier's Init/core foundation and standard three-axiom policy. Broader library import policies and arbitrary generated modules need a subsequent protocol version.

源代码账本包含共同的组装器开销、所有局部辅助内容、候选的完整模块和生成的证明。共同基础和规格模块对所有路线相同。控制器保留经过核验的较长路线，供联合计量选择，而不先按单题长短丢弃它们。

The source ledger includes assembly overhead, local helpers, generated proofs and the entire candidate package where imported. The foundation and goal-specification modules are common. Verified longer routes remain available for joint selection rather than being discarded by individual-goal length.

## 阶段与预算 / Stages and budgets

| 阶段 | Contract |
| --- | --- |
| 初始化 / Initialisation | Compile the historical group in the base, then in the candidate context to check every candidate declaration as well. These preflights are outside both comparison arms. |
| 预压缩 / Preparation | Export a base-only request. Retain the historical proof and every verified prepared alternative. Complete the declared attempt schedule before freezing. |
| 冻结 / Freeze | Bind the complete prepared pool. Subsequent preparation submissions cannot change it. |
| 控制 / Control | Base-only requests, the frozen prepared pool and this arm's own feedback. Helpers may be independently invented. |
| 候选 / Treatment | The same prepared pool, original goals and caps, with candidate sources additionally available. Own feedback remains local to this arm. |

每个阶段的响应次数有上限。`retain` 决定也占一个槽位。候选响应的字节数、组装后证明的字节数、Lean heartbeats、单命令时间和单尝试时间均受冻结预算约束。开始核验前先保存响应和事件。拒绝、超时、中断及修复继续使用原预算。重复读取一个待答请求得到相同请求，旧响应无法回答新槽位。

Each response consumes a phase slot, including retain decisions. Both the serialized response and assembled proof respect the frozen byte cap. Lean heartbeats and per-command/per-attempt times are bounded. Responses and journal events are saved before verification. Rejections, timeouts and interruptions retain their budget usage. Pending requests are idempotent; stale or opposite-arm responses are rejected.

请求隔离是这个控制器检查的内容。模型是否在别处见过答案、供应商生成 token、采样参数和真实使用量，需要外部隔离与计量证据。相同上限不会自动证明实际消耗相同，当前报告保留未知生成成本和未成立的因果归因。

The controller enforces exported-request boundaries. Prior model exposure, sampling, provider tokens and actual usage require external evidence. Equal caps do not establish equal consumption. Reports retain unknown generation costs and no causal or training-readiness claim. Lean sources execute as code under the trusted controller, following the existing migration protocol's execution model.

## 运行 / Running

先将固定 Lean 工具链的 `bin` 加入 PATH。清单示例是
[plan.json](../experiments/grouped_search_v1/plan.json)。原目标、基础、候选、源码指纹、预算和历史证明都在清单中，新增会话会复制并冻结这些内容。

Put the pinned Lean toolchain's bin directory on PATH. The runnable plan pins original goals, the foundation, candidate, sources, budgets and historical component proofs. New sessions snapshot them before issuing requests.

```bash
python -m maam group-start \
  --plan experiments/grouped_search_v1/plan.json \
  --session /tmp/maam-group \
  --solver-id deterministic-core-v1 --mode supplied_reference
python -m maam group-run-local --session /tmp/maam-group --phase preparation
python -m maam group-freeze --session /tmp/maam-group
python -m maam group-run-local --session /tmp/maam-group --phase control
python -m maam group-run-local --session /tmp/maam-group --phase treatment
python -m maam group-report --session /tmp/maam-group --output /tmp/group-report.json
```

两种方法先展开固定的原目标定义，依次尝试 `intros` 后用已有假设或自反性，以及建立一次局部恒等引理再处理各目标。它们完全从导出的请求生成候选，由 Lean 决定正确性；多于两个槽位时，后续槽位保留原路线。方法及其代码哈希随结果保留，其有限范围不等于一般旧工具搜索已经充分完成。

The two methods unfold the fixed original goal definition and try core hypotheses/reflexivity after introductions, then a shared local identity lemma. They generate from the exported request and rely on Lean for validity. Beyond two slots they retain incumbents. The method source hash is retained, and their limited scope does not certify sufficient general baseline search.

## 外部工作者接口 / External worker interface

用 `group-request --phase ... --output request.json` 导出一份请求。工作者只接收这份请求和本段指令，依据 `inner_request.sources` 内的源代码工作。`incumbents` 提供已核验的共同证明，`prior_feedback` 只提供同侧反馈。提交格式如下，所有原目标 id 必须出现一次。

Export a request with `group-request`. Give a worker only that request and these instructions. It works from `inner_request.sources`, verified common incumbents and same-arm feedback. Return exactly one term per original target ID, with optional shared local tactics. Keep the original goal definitions, imports, axioms and budgets fixed.

```json
{
  "action": "candidate",
  "request_sha256": "the exported request fingerprint",
  "helpers": "have reuse (P : Prop) (h : P) : P := h",
  "proofs": {
    "one": "by\n  intros\n  apply reuse\n  assumption",
    "two": "by\n  intros\n  apply reuse\n  assumption"
  },
  "bridge": "Explain which original hypotheses discharge every helper precondition."
}
```

```bash
python -m maam group-submit --session /tmp/maam-group \
  --phase control --response response.json --output attempt-report.json
```

`retain` 响应只包含 action、request_sha256 和非空 reason。每次响应和报告采用新文件，历史事件与日志保留。控制器在提交时检查现行请求身份与完整目标覆盖；JSON 包装本身不会建立证明有效性。

A retain response contains only action, request_sha256 and a nonempty reason. Keep responses, reports and logs under new filenames. Submission validates request identity and complete coverage; packaging alone does not verify a proof.

## 校准 / Calibration

```bash
python scripts/check_grouped_search.py \
  --workdir /tmp/group-calibration-new --output /tmp/group-calibration-new.json
```

校准先执行给定证明、共享引理、一个错误分量及其修复，再执行三个阶段的两种确定性方法。两组继承相同预压缩内容，候选源码仅在包侧请求中出现，完整包仍接受独立预检。它核验的是协议和有限方法，可用作回归例子。

The calibration checks supplied shared-helper proofs, an incorrect component and repair, then runs both deterministic methods in all three phases. It verifies matching prepared inputs, treatment-only candidate exposure and complete candidate preflights. This is a protocol and limited-method regression calibration.

同预算的独立模型求证、任意新模块的生成、跨模块展开策略，以及预留数学题上的迁移仍是下一步。成组接口让这些后续工作可以交付到原目标并进入已有的完整路线账本。

Independent metered model search, arbitrary generated modules, general cross-module unfolding and transfer to reserved mathematical tasks remain subsequent work. The grouped interface now gives those searches a fixed-goal delivery and accounting contract.

本轮结果见 [grouped-search-calibration-v1.json](../results/grouped-search-calibration-v1.json)，首次自动方法未展开目标的六份失败记录见 [grouped-search-development-v1.json](../results/grouped-search-development-v1.json)。

The committed calibration records the final supplied and deterministic runs. The development record retains the six rejected intros-only proposals and their exact source, input snapshots and command logs.
