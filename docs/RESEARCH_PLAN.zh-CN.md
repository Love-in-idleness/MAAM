# 研究计划与进度

[English](RESEARCH_PLAN.md) | [当前目标](REUSE_COMPRESSION_OBJECTIVE.zh-CN.md)

## 当前阶段（2026-10-29）

当前研究入口已收敛至 [工具复用与整包压缩目标](REUSE_COMPRESSION_OBJECTIVE.zh-CN.md)，核心关注在固定目标与严格核验前提下，后续证明节省的空间能否抵消可复用数学工具的完整引入成本。此前各阶段的设计方案与实验记录保留归档在 `docs/` 中，不产生新的 API 调用额度。

## 研究目标

MAAM 旨在评估 Lean 中的新命题、新定义以及围绕核心思想组织的**候选理论包**（定义、性质、引理与桥接），为数学探索与未来 AI 学习提供可核查的反馈：

- **评估单位**：候选理论包（包含 `base`、`core`、`declarations`、`bridges`、`dependencies`、`conjectures`、`applicability`、`provenance`），先整体评估再通过消融对照（如仅命名、仅定义、完整包）检查贡献，不以各节点静态分数相加代替整体价值。
- **核心对照**：固定背景知识 `K`、预设任务集 `T` 与求证预算 `B`，比较 `Run(K, T, B)` 与 `Run(K + P, T, B)`，将 `P` 的完整成本计一次，并分列源码长度、内部证明大小、搜索资源、核验时间与通过目标。
- **输出形态**：允许条件支配、权衡不可比、经验同等或证据不足，不强行合并为单一标量分或全局排序。
- **静态指标定位**：现有静态指标（[METRICS.zh-CN.md](METRICS.zh-CN.md)）作为描述与检索信号保留，不视为新概念未来价值的已验证估计。

## 里程碑与进度总览

| 阶段 | 目标交付 | 已实现控制 | 已观测证据 | 尚未完成的缺口 |
| --- | --- | --- | --- | --- |
| **M0：设计** | 研究范围、包结构与证据约定 | 已完成（研究计划、整包压缩目标与理论约束文档） | — | AI 理解难度与未来价值模型暂缓 |
| **M1：可验证对照** | 隔离 Lean 执行器、清单格式、同态/核参考迁移与审计 | 已完成（[THEORY_PACKAGES.zh-CN.md](THEORY_PACKAGES.zh-CN.md)、[COMPRESSED_PACKAGES.md](COMPRESSED_PACKAGES.md)） | 局部证明体 `77 → 29` token；非共享总源码 `89 → 353` token | 单条参考任务，不构成一般价值结论 |
| **M2：系统化迁移** | 约 20 目标、`evaluate-theory-package` skill、计量 LLM 接口与预留划分 | 部分完成：独立上下文、DeepSeek 阶段门控与预算预约调用器、原证保留选择层、有限旧工具改写、指南/构造试验与 v2 `theorem` 契约 | 独立上下文 40 份核验见证；正式计量 v1：16 次 DeepSeek 调用（估 US\$0.296767125），13/16 通过，5 道共解题目 `2572 → 3679` token（含 1100-token 整包）；指南试验 `24/24`（26 次调用，估 US\$0.057759）；构造试验 `24/24`（39 次调用，暴露 `def/theorem` 契约歧义）；v2 契约 `12/12` 固定对照与 449 项测试通过 | 基线充分优化、严格因果归因、更大任务覆盖与预留集有效性未验收 |
| **M3：整包与延迟价值** | 消融对照、版本演化、成本/用途比较与多轮探索 | 部分完成：包消融、`v1 → v2` 演化、来源衔接器（收据→清单→有限确认→原证保留压缩） | 2 道开发题经 DeepSeek 旧工具搜索 `367 → 186` token；加整包后 `121 + 1100 = 1221` token（压缩字节亦增加） | 自动多轮候选搜索与远距离迁移未实现 |
| **M4：学习接口** | 可重放轨迹、偏好比较数据与训练反馈适配器 | 未启动 | — | 训练前后对比与奖励投机检查未实现 |

## 实验协议核心原则

1. **固定与隔离**：固定基础库、目标集、等价判据、成本口径、证明器配置与预算；检查传递导入与自动化扩展，防止候选概念泄露进基线。
2. **开发/预留分离**：按推理模式分组避免近重复跨组；候选仅在开发集上修改；预留集一旦用于指导修改即转为开发数据，后续最终评价须启用新任务。
3. **局部迁移与原证保留**：始终保留已核验原证；仅当新证明核验通过且完整 `Proof` 源码 token 严格更少时更新当前选用证明；较长的可复用分解另行留档。
4. **诚实核算**：同时报告总节省与扣除 `P` 一次成本后的净节省；保留失败与中断记录，未知生成成本保持未知而不记为零。

## 历史设计与实验归档索引

`docs/` 下其余历史文档作为过往阶段的完整档案保留：

- **基线准备与选证**：[BASELINE_PREPARATION.md](BASELINE_PREPARATION.md)、[BASELINE_SEARCH.md](BASELINE_SEARCH.md)、[BASELINE_METHODS.md](BASELINE_METHODS.md)、[BASELINE_STABILITY.md](BASELINE_STABILITY.md)、[MODEL_BASELINE.md](MODEL_BASELINE.md)、[RETAINED_COMPRESSION.md](RETAINED_COMPRESSION.md)、[MODEL_PORTFOLIO.md](MODEL_PORTFOLIO.md)
- **迁移与计量试验**：[MIGRATION_PROTOCOL.md](MIGRATION_PROTOCOL.md)、[INDEPENDENT_EXPERIMENT.md](INDEPENDENT_EXPERIMENT.md)、[GENERATION.md](GENERATION.md)、[METERED_TRANSFER.md](METERED_TRANSFER.md)、[PACKAGE_ABLATIONS.md](PACKAGE_ABLATIONS.md)、[VERSION_EVOLUTION.md](VERSION_EVOLUTION.md)
- **方法使用与契约**：[METHOD_RESEARCH_DESIGN.md](METHOD_RESEARCH_DESIGN.md)、[METHOD_USE.md](METHOD_USE.md)、[CLOSURE_TRANSPORT.md](CLOSURE_TRANSPORT.md)、[CONSTRUCTION_USE.md](CONSTRUCTION_USE.md)、[THEOREM_CONTRACT.md](THEOREM_CONTRACT.md)、[METHOD_REUSE_REVIEW.md](METHOD_REUSE_REVIEW.md)
- **理论探讨**：[COMPRESSION_FRAMEWORK.md](COMPRESSION_FRAMEWORK.md)、[COGNITIVE_COMPRESSION.md](COGNITIVE_COMPRESSION.md)、[PROOF_METHODS.md](PROOF_METHODS.md)、[EXECUTABLE_METHOD.md](EXECUTABLE_METHOD.md)
