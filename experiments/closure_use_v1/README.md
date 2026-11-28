# Closure-use development protocol v1

| 中文 | English |
| --- | --- |
| 本目录冻结构造法真实试验的外层协议，复用 [closure_transport_v1](../closure_transport_v1/README.md) 的六个作者设计任务、数学源码、人工参考和 288 词英文指南。原离线材料保持不变；`protocol.json` 绑定其套件、参考和指南哈希。 | This directory freezes the outer live-trial protocol, reusing six author-designed tasks, mathematical sources, author references, and the 288-word English guide from [closure_transport_v1](../closure_transport_v1/README.md). Offline material stays unchanged; `protocol.json` binds its suite, reference, and guide hashes. |
| A、B 两组数学材料完全相同，包括一般原像封闭性引理；仅 B 组额外收到指南。人工参考、任务角色、期望方法和已有目标证明不进入模型请求。每个会话使用独立上下文，修复时只追加该会话自己的输出和核验反馈。 | A and B receive identical mathematics, including the general preimage-closure lemma; only B additionally receives the guide. Author references, task roles, expected methods, and existing target proofs stay outside model requests. Sessions have independent contexts; repairs append only their own output and verification feedback. |
| c01–c04 要求生成受约束的存在性证书：目标已指定映射类型和逐点行为，内核检查同态保持性质、逐点一致性和封闭性。成功表示完成这些构造义务，不表示发现未知映射、自动选择策略或提取可执行见证。 | c01–c04 request constrained existential certificates: goals specify map types and pointwise behavior, while the kernel checks homomorphism preservation, pointwise agreement, and closure. Success establishes completion of these construction obligations, without establishing discovery of unknown maps, automatic strategic selection, or executable witness extraction. |
| c05–c06 是缺少必要前提的有限反例，允许使用 `decide`，并与四个正向任务分开报告。直接依赖 `Theory.preimage_mul_closed` 只表示观察到该命名引理的直接使用；缺少直接依赖可能是经辅助引理间接使用，不能据此断言没有使用方法。 | c05–c06 are finite counterexamples for missing premises, permit `decide`, and are reported separately from the four positive tasks. A direct dependency on `Theory.preimage_mul_closed` records direct named-lemma use; its absence can reflect indirect use through a helper and does not establish absence of method use. |
| 六题 × 两组 × 两次重复，共 24 个会话。每次会话最多两次调用，即首轮加一次模型自修复；成功后立即停止。按题依次执行：每题第一轮 A/B，第二轮 B/A。全试验最多 48 次调用，总预算上限 5 美元，不沿用旧试验的剩余额度。 | Six tasks × two conditions × two repetitions produce 24 sessions. Each allows at most two calls—an initial attempt and one model repair—and stops on success. Run task by task: A/B in the first repetition and B/A in the second. The complete trial allows at most 48 calls and US$5, without reusing any previous trial's remaining allowance. |
| 两组使用相同的 DeepSeek Flash、低推理配置、输入预约、输出上限和超时。保留失败、中断和未知用量；已消耗的失败调用同样计费。准备协议不等于执行试验或产生结果。 | Both conditions use the same DeepSeek Flash model, low reasoning setting, input reservation, output cap, and timeout. Preserve failures, interruptions, and unknown usage; failed calls that consumed resources still count. Protocol preparation is not execution or a result. |
| 首轮与预算内成功率、资源和完整材料大小分别报告。指南效果包含注意、检索和语法帮助；这批开发任务不支持跨领域迁移、新理论效果、自动方法发现或普遍理解能力的结论。 | Report first-attempt success, within-budget success, resources, and complete material size separately. Guide effects include attention, retrieval, and syntax assistance. These development tasks do not establish cross-domain transfer, new-theory effects, automatic method discovery, or general comprehension. |

| 预算项 / Budget item | 固定值 / Fixed value |
| --- | --- |
| 输入预约 / Input reservation | 16,384 tokens per call |
| 输出上限 / Output limit | 32,768 tokens per call |
| 调用超时 / Call deadline | 180 seconds |
| 价格与余量 / Prices and margin | US$0.30 input / US$1.20 output per million tokens; ×1.25 reservation margin |
| 价格核对日期 / Pricing check date | 2026-10-27 |

