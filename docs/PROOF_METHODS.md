# 证明方法说明卡 / A proof-method card

状态：手工整理一个已有的核乘法封闭性实例，说明如何调用其证明结构。
Status: a manually prepared description of one existing kernel-closure instance and its use.

这份卡没有实现通用方法语言、搜索器或一般逆像封闭性引理，也没有产生新的迁移实验。
This card introduces no method language, search engine, general inverse-image closure lemma or new transfer experiment.

## 六项接口 / Six interface items

1. **入口：**目标是 `Foundation.kernelMulGoal`：群 `g`、`h` 之间的函数 `f` 保持乘法，且 `f x = h.one`、`f y = h.one`，证明 `f (g.mul x y) = h.one`。
   **Entry:** given groups, a multiplication-preserving function and two elements mapped to the identity, prove that their product also maps to the identity.
2. **选择：**使用目标已给出的 `f` 和保持乘法的证明 `hf`，构造 `F : Theory.Hom g h := ⟨f, hf⟩`。
   **Choice:** bundle the supplied function and preservation proof as a homomorphism; this instance does not invent a new map.
3. **转换：**把两个前提和目标识别为 `Theory.kernel F` 的成员条件，调用 `Theory.kernel_mul F hx hy`，再由定义相等回到原陈述。
   **Transformation:** recognize kernel membership, apply the closure theorem, and recover the original statement by definitional equality.
4. **义务：**`hf`、`hx`、`hy` 必须具备所需类型；本例中它们由原目标提供，若另一应用缺少某项，必须保留该证明义务。
   **Obligations:** preservation and membership evidence must have the required types; missing evidence remains an obligation in another application.
5. **正确性：**[`Theory.kernel_mul`](../experiments/hom_kernel/Candidate.lean) 展开核、利用保持乘法、代入两个单位元等式，再用群的单位元律完成证明。
   **Correctness:** the existing theorem proves the transformation using operation preservation, the membership equalities and the identity law.
6. **搜索边界：**这里只记录给定映射和给定引理的调用，不保证自动找到适用映射，也不把匹配失败理解为目标不可证明。
   **Search boundary:** map discovery and automatic applicability are outside this card; failure to match would not establish unprovability.

以下调用原样来自 [`Treatment.kernelMul`](../experiments/hom_kernel/Treatment.lean) 的证明体。
The following invocation is the existing treatment proof body.

```lean
by
  intro G H g h f hf x y hx hy
  let F : Theory.Hom g h := ⟨f, hf⟩
  exact Theory.kernel_mul F hx hy
```

## 证据与采用规则 / Evidence and adoption

[`归档报告`](../results/theory-package-reference.json) 记录同一个原始目标在两种条件下保持不变；这是给定参考证明，报告明确没有执行搜索或留出评估。
The archived report records preservation of the same original goal under both conditions, using supplied reference proofs without search or held-out evaluation.

档案中局部证明体从 77 个源码 token 缩为 29 个，但包含完整候选包的非共享源码总量从 89 增至 353，不能据此宣布整包节省。
The archived proof body shrinks from 77 to 29 source tokens, while the complete nonshared package ledger rises from 89 to 353, so this instance does not establish package savings.

默认保留旧证；只有通过核验且按冻结源码口径严格缩短的候选才允许替换所选证明，完整理论包成本仍另行核算。
Retain the incumbent by default; only a verified, strictly shorter candidate under the frozen source convention may replace it, with whole-package cost accounted for separately.

压缩 sidecar 测量固定编码下整套活动源码的压缩字节数，不改变上述选择规则，也不把压缩包更小解释为方法已被 AI 熟练掌握。
The compression sidecar measures active-source bytes under a fixed encoding without changing proof selection or establishing AI mastery.

## 方法出处与当前边界 / Methodological sources and current limits

[Bundy（1988），The Use of Explicit Plans to Guide Inductive Proofs](https://www.pure.ed.ac.uk/ws/files/6347911/The_Use_of_Explicit_Plans_to_Guide_Inductive_Proofs.pdf) 是显式证明规划的早期工作，本卡借鉴将证明方法单独描述的方向，不声称实现其系统。
Bundy's 1988 work provides an explicit proof-planning precedent; this card adopts the descriptive direction without implementing that system.

[Ying Xie（2026-10-12），What the Machine Invented，§4、§11](https://arxiv.org/html/2610.17090v1#S4) 区分工具提取、文献比较与数学核验，并说明该综述没有编译或核验 Lean 开发。
Xie's survey distinguishes extraction, literature comparison and verification, and reports no Lean compilation or kernel checking of the developments.

本卡仅整理已有一个实例，没有新核验；AI 是否更容易找到或使用它、能否迁移到其他任务，均未测量。
This card organizes one existing instance without fresh verification; AI usability and transfer remain unmeasured.

当前可计算的对象是既有证书、调用及整包源码成本；暂冻结尚无可执行测量程序的认知综合评分。
Current computable objects are the existing certificates, invocations and package-source costs; composite cognitive scores without an executable measurement procedure remain frozen.
