# MAAM 猜想条件压缩榜 v2 / Conjecture compression v2

每个分数等于原证明文件总 token 减去选定的证明文件总 token，再减去一次猜想陈述文件的 token。
斜线列按原文件 → 替代文件显示。— 表示该项冻结为保留原证。

Each score is the original proof portfolio’s token count minus the retained proof portfolio’s tokens and one charge for the conjecture statement. Each target shows original → alternative. A dash denotes a frozen decision to carry the original.

| 名次 / Rank | 猜想 / Conjecture | euclid | bertrand | 毛节省 / Gross | 陈述 / Statement | 条件净节省 / Net |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 孪生素数 / Twin primes | 113 → 55 | 111 → — | 58 | 31 | +27 |
| 2 | Sophie Germain 素数无穷 / Infinitely many Sophie Germain primes | 113 → 55 | 111 → — | 58 | 33 | +25 |
| 3 | Landau 的 n²+1 素数猜想 / Landau’s n²+1 primes | 113 → 65 | 111 → — | 48 | 30 | +18 |
| 4 | 强哥德巴赫 / Binary Goldbach | 113 → 82 | 111 → — | 31 | 36 | -5 |
| 5 | Legendre 猜想 / Legendre | 113 → 77 | 111 → 119 | 36 | 44 | -8 |
| 6 | Oppermann 猜想 / Oppermann | 113 → 87 | 111 → 123 | 26 | 68 | -42 |

完整核验和计量 / Full verification and measurement

- [euclid Lean report](euclid-report.json)
- [bertrand Lean report](bertrand-report.json)
