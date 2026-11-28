# MAAM 猜想条件压缩榜 v2 / Conjecture compression ranking v2

[实际榜单 / Computed leaderboard](ranking.md) · [逐项账本 / Detailed ledger](ranking.json) · [冻结目标与证据计划 / Frozen panel](panel.json)

| 固定目标 / Fixed target | Mathlib 原证明 / Original Mathlib theorem |
| --- | --- |
| 素数无穷 / Prime infinitude | [`Nat.exists_infinite_primes`](https://github.com/leanprover-community/mathlib4/blob/d167cc6dc962ab340507362ea2f4bcfcff44f01b/Mathlib/Data/Nat/Prime/Infinite.lean#L29-L38) |
| $n\ge512$ 版 Bertrand 定理 / Bertrand for $n\ge512$ | [`Nat.exists_prime_lt_and_le_two_mul_eventually`](https://github.com/leanprover-community/mathlib4/blob/d167cc6dc962ab340507362ea2f4bcfcff44f01b/Mathlib/NumberTheory/Bertrand.lean#L191-L202) |

| 中文 | English |
| --- | --- |
| 每个候选从两份相同的原证明出发。对冻结计划中有替代证的项目，分别编译和核验原证与 $A\to B$。完整证明文件较短时才替换。其余项保留原证，替代证长度为空。 | Each conjecture starts from the same two original proofs. Where an alternative is supplied, Lean independently checks the original and $A\to B$. The alternative is retained only when its full proof file is shorter. Carried proofs keep their original cost and have no reported alternative length. |
| 总分是原证明总 token 减去保留证明的总 token，再减一次完整猜想陈述文件的 token。同一猜想跨目标的陈述须逐字节相同，完整陈述成本也须一致。评分按整数精确计算。 | The score is the original portfolio’s total tokens minus the retained proof tokens and one charge for the conjecture statement file. The statement must match byte for byte across targets and have a consistent measured cost. Scores are computed as exact integers. |
| 两个目标的支持库分别冻结，Bertrand 的支持文件复制了上游定理之前的引理。每个目标内部原证与替代证的导入闭包须一致。这个短名单检验给定证明组合的成本，其中「保留原证」表示本轮没有提交替代证。 | Each goal has a frozen foundation. Bertrand’s foundation copies the upstream lemmas preceding the target theorem. For each goal, the original and its replacements must have matching import closures. The scores measure this submitted proof portfolio. Carrying an original means no alternative was submitted for that cell. |
| 这是一份素数相关的榜单。它不含猜想本身的证明成本。跨学科猜想和全库推广需要另外构建并预先冻结目标集及可核验证据。 | This slate covers prime-related conjectures. It leaves the cost of proving the conjectures unmeasured. A cross-field or library-wide ranking requires a separately frozen panel and verified witnesses. |

先准备 Lean 4.24.0 和提交 `d167cc6dc962ab340507362ea2f4bcfcff44f01b` 的 Mathlib。预取所需模块 / Prepare Lean 4.24.0 and the pinned Mathlib checkout, then fetch the required targets

```bash
lake exe cache get Mathlib/Data/Nat/Prime/Infinite.lean Mathlib/NumberTheory/Bertrand.lean
```

从 MAAM 根目录运行以下命令。它在新输出目录生成两份 Lean 核验报告及榜单 / Run from MAAM to generate the two Lean reports and the ranking in a new directory

```bash
bash scripts/replay_conjecture_compression_panel.sh /path/to/mathlib /path/to/new-output
```

Bertrand 的依赖审计用 Lean 的 `Expr.getUsedConstants` 遍历共享子表达式中的常量集合，仍检查相同公理、依赖与目标类型。证明体 token 与目标证明项计数沿用原方法。复现脚本保留实际编译的审计源码指纹。

For Bertrand’s dependency audit, Lean’s `Expr.getUsedConstants` collects the same constants while visiting shared subexpressions once. Axiom, dependency and goal checks are retained, as are the original proof-body token and target expression counts. The replay script records the fingerprint of the compiled auditor source.
