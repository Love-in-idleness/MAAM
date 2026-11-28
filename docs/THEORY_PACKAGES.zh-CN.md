# 理论包评估指南（M1 参考接口）

[English](THEORY_PACKAGES.md)

本接口实现研究计划 M1 的参考迁移：在隔离基础库中检查引入候选理论包前后的两份给定证明，并输出可追溯的成本账本。

## 运行方式

需要 Python 3.11+ 与 Lean 4.24.0，参考源码与清单位于 [experiments/hom_kernel/](../experiments/hom_kernel/)：

```bash
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json
```

输出报告并运行真实 Lean 负例拒绝检查（输出文件必须尚不存在）：

```bash
mkdir -p data/theory-package
python -m maam evaluate-package \
  --experiment experiments/hom_kernel/experiment.json \
  --output data/theory-package/theory-package-reference.json
python scripts/check_theory_package.py \
  --report data/theory-package/theory-package-reference.json \
  --negative-output data/theory-package/theory-package-negative.json
```

**退出码**：`0` 比较完成；`1` 输入或运行配置错误；`2` 验证预算耗尽；`3` 证明或依赖审计被拒绝。

## 输入清单

- `experiment.json` 固定基础模块、基线/实验条件、原始目标、源码 SHA-256、Lean 版本与验证资源限制。
- `package.json` 描述核心思想以及包内定义、定理与对象。
- 首版仅接受 `reference_migration` 阶段与 `development` 任务；给定证明属于参考见证，不能标为预留集独立发现或求证性能证据。
- 所有源码须位于实验目录内并匹配冻结 SHA-256；基础、候选与证明模块互不重叠且不遮蔽 Lean 核心模块。改动候选或源码须新增实验版本。

## 核验流程

1. 两种条件的源码分别复制到全新临时目录，覆盖 `LEAN_PATH` 并按固定顺序重新编译，防止外部 `.olean` 泄露。
2. 基线仅获得基础库与原证明；实验组获得同一基础库、候选包与迁移证明。
3. 审计器检查传递导入、自有模块的每个声明及其依赖，并核实目标确为原始命题的定理。
4. 仅允许 Lean 标准公理 `propext`、`Quot.sound`、`Classical.choice`（报告列出实际使用集合）；其余公理、`sorryAx` 与 `unsafe` 依赖一律拒绝（包括候选中未被目标使用的声明）。
5. 注意：模块与依赖审计是实验有效性约束，不构成操作系统级安全沙箱。

## 成本口径

- **源码 token**：由 Lean 命令解析器统计带原始位置的 atom 与 identifier 叶节点，去重并排除注释。对 `:=` 目标声明按语法位置拆分声明头、分隔符与证明体。
- **内部证明大小**：统计证明体中表达式构造器出现次数（含绑定变量类型、排除元数据包装），不展开所引用引理。
- **整包源码账本**：局部证明缩短仅作描述；净源码账本比较全部非共享模块，将候选定义、引理证明、辅助对象与迁移代码各计一次。相同基础库从差额中消去，源码 token 与内部证明大小分别输出。
- **时间记录**：仅反映编译与核验耗时，不作为求证搜索效率证据。

## 报告解读

- `verified_reference_comparison` 仅表示两边源码编译通过、通过审计并完成了本次比较。
- 计入整包后净源码增加同样是有效结果。
- M2 的 20 个校准任务、skill 与逐任务协议见 [MIGRATION_PROTOCOL.md](MIGRATION_PROTOCOL.md)；另见 [RESEARCH_PLAN.zh-CN.md](RESEARCH_PLAN.zh-CN.md) 与 [.github/workflows/theory-package.yml](../.github/workflows/theory-package.yml)。
