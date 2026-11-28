# 猜想对已有定理的压缩 / Conditional compression of known theorems

固定目标 (B) 是欧几里得定理 `Nat.exists_infinite_primes`。每条替代证独立编译并接受 Lean 审计。三条替代证使用同一个 (B)，各自只引入一条猜想作为局部假设。 [原定理](https://github.com/leanprover-community/mathlib4/blob/d167cc6dc962ab340507362ea2f4bcfcff44f01b/Mathlib/Data/Nat/Prime/Infinite.lean#L29-L38)

The fixed goal (B) is Euclid's theorem `Nat.exists_infinite_primes`. Each replacement is compiled and audited independently. All three use the same (B) and introduce a single conjecture as a local hypothesis. [Upstream theorem](https://github.com/leanprover-community/mathlib4/blob/d167cc6dc962ab340507362ea2f4bcfcff44f01b/Mathlib/Data/Nat/Prime/Infinite.lean#L29-L38)

| 排名 / Rank | 猜想 / Conjecture | 证明体 / Proof body tokens | 完整证明文件 / Proof file tokens | 猜想文件 / Statement file tokens | 条件净节省 / Conditional net tokens | 证明项节点 / Proof expression nodes |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 孪生素数 / Twin primes | 85 → 22 | 113 → 55 | 31 | +27 | 433 → 509 |
| 2 | Landau 的 (k^2+1) 素数猜想 / Landau's primes of the form (k^2+1) | 85 → 32 | 113 → 65 | 30 | +18 | 433 → 599 |
| 3 | 强哥德巴赫 / Binary Goldbach | 85 → 49 | 113 → 82 | 36 | −5 | 433 → 1673 |

| 中文 | English |
| --- | --- |
| 原证和替代证的固定目标由 Lean 检查定义等价。原证与上游源码区间逐字节匹配，仅替换了声明名。两个条件使用相同的库导入闭包，并从中移除原定理及列出的同族声明。替代证必须使用 (A) 的外层局部参数。 | Lean checks definitional equality against the fixed goals. The original matches its upstream source range byte for byte, apart from the declaration name. Both conditions use the same library import closure with the original and listed related declarations withheld. The replacement must use the outer local assumption (A). |
| 证明体 token 来自 Lean 对 `:=` 之后的语法计数。排名依据完整证明文件节省的 token 之和，扣除完整猜想陈述文件一次。每个目标保留两份已验证证明中按文件 token 计量的较短者。 | Proof body tokens are counted by Lean after `:=`. Ranks sum savings in complete proof file tokens and charge the full conjecture statement file once. For each goal, the smaller of the two verified proof files is retained. |
| 有目标缺少合格证据时，净节省或整个面板排序留空。猜想本身的证明成本留空。上表仅比较固定见证的源码成本，证明项节点数单列。 | A goal without admissible evidence leaves the net score or panel ranking unavailable. Proof cost for the conjecture itself is unknown. The ranking compares source costs of fixed witnesses. Elaborated proof sizes are also reported. |
| 这次实验仅使用一个已证目标。实际核验拒绝了四种输入：导入被遮蔽的原定理、忽略猜想假设、使用 `sorry`、改写成另一个结论。 | This experiment uses one established goal. Actual Lean runs rejected four inputs: importing the withheld original, ignoring the assumption, using `sorry`, and proving a different goal. |

准备 `suite.json` 指定的 Mathlib 提交及 Lean 4.24.0。从 Mathlib 目录获取所需的缓存 / Prepare the Mathlib revision from `suite.json` and Lean 4.24.0. Fetch the required cache from the Mathlib checkout

```bash
lake exe cache get Mathlib/Data/Nat/Prime/Infinite.lean
```

从 MAAM 目录运行 / Run from MAAM

```bash
python -m maam measure-conjecture-compression \
  --suite experiments/conjecture_compression/suite.json \
  --mathlib /path/to/mathlib
```

[原始核验及计量结果 / Verification and measurement report](report-v1.json) · [冻结输入 / Frozen suite](suite.json)
