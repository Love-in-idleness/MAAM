# 开放猜想榜验收 / Open conjecture ranking

| 中文 | English |
| --- | --- |
| [榜单、目标族和证据路径](ranking-v1.md)由 MAAM 直接生成。[v1 语料](corpus-v1.json)收录 9 个假设、17 个目标、22 条规则。 | MAAM generates the [ranking, target families and witness paths](ranking-v1.md). The [v1 corpus](corpus-v1.json) records 9 assumptions, 17 targets and 22 rules. |
| Langlands 项采用数域上 Artin 表示的互反律。涉及 motive 理论的条目采用 Hodge 猜想及有限域代数闭包上的 Lefschetz 标准猜想 B。BSD 采用秩形式。 | The Langlands entry is reciprocity for Artin representations over number fields. The Hodge conjecture and Lefschetz standard conjecture B over finite-field closures supply entries relevant to motives. BSD uses its rank formulation. |
| 目标与分组由人工选定。输入由文献和书面推理提供，程序核验图结构并计算传递可达性。证据尚未逐条用 Lean 核验。样本覆盖和目标分组影响跨领域名次。 | The targets and their families are curated. The program validates the graph and computes reachability from cited implications and written arguments. The arguments have not been checked in Lean. Cross-field ranks depend on the sample and how its targets are grouped. |

从仓库根目录运行 / Run from the repository root

```bash
python -m maam rank-conjectures --corpus experiments/conjecture_ranking/corpus-v1.json
python -m maam rank-conjectures --corpus experiments/conjecture_ranking/corpus-v1.json --format markdown
```

| 中文 | English |
| --- | --- |
| 从同一个已知结论集出发，每次只额外假设一个候选。每条推导规则的所有前提均须可达，才可加入其结论。 | Each run starts from the same established results and assumes one candidate. A rule fires when all its premises have been reached. |
| 先扣除基线可导目标和候选本身。若语料也提供目标推出候选的路径，则将它记为等价表述。其余新增目标按族计数，每族一分，同分并列。 | Remove targets already reachable at baseline and the candidate itself. If the graph also derives the candidate from a reached target, record an equivalence. Each remaining family counts once and equal scores share a rank. |
| 软件重用 MAAM 的有限证明求解器。单位长度用于选出一条可展示路径。JSON 报告保留规则 ID、原始语料指纹，以及逐次去掉一个目标族后的全部名次。 | The command reuses MAAM’s finite proof solver. Unit lengths select a witness path. The JSON report preserves rule IDs, the input hash and all ranks after each single-family omission. |
| 第一阶段的验收覆盖排序、条件推导、等价改写与已知结论去重。分值衡量语料中的下游覆盖；对猜想的演绎压缩、所需证明成本与社会影响仍缺测量。 | This milestone tests ranking, conditional inference and the exclusion of equivalent formulations and established outcomes. The score measures downstream coverage in the corpus. Deductive compression, proof cost and social impact have no measurements here. |
