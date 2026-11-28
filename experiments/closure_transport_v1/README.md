# 映射构造与封闭性运输 / Map construction and closure transport

| 中文 | English |
| --- | --- |
| 本目录是六个作者设计开发任务的离线夹具，不含真实模型试验或调用许可。四个正向任务要求证明同态对象存在、与指定原始函数逐点一致以及原像的乘法封闭性；两个边界任务给出明确反例。这里不声称已提取可执行见证。 | This is an offline fixture of six author-designed development tasks, without a live model trial or call authorization. Four positive tasks existentially witness a homomorphism, pointwise agreement with the requested raw function, and preimage multiplication closure. Two boundary tasks supply explicit counterexamples. No executable witness extraction is claimed. |
| `Base.lean` 与 `Candidate.lean` 逐字节复用 `experiments/hom_kernel/`。共同基础增加通用乘积群和 Bool XOR 群；新包仅增加 `Theory.MulClosed` 与 `Theory.preimage_mul_closed`，没有复合、配对或等化任务的专用解答定理。 | `Base.lean` and `Candidate.lean` are byte-identical to `experiments/hom_kernel/`. Shared infrastructure adds a generic product group and the Bool XOR group. The new package contains only `Theory.MulClosed` and `Theory.preimage_mul_closed`, without task-specific composition, pairing, or equalizer solutions. |
| 任务声明只依赖共同基础，不导入新方法。人工参考在本地构造映射及保持性质，再使用一般运输引理；参考与说明是作者材料，不是模型输出。 | Task declarations depend only on shared infrastructure and do not import the new method. Author references construct maps and preservation locally, then apply the general transport lemma. References and explanations are authored inputs, not model output. |
| 这里只讨论乘法封闭性，未声称得到子群。群结构并非运输引理的最弱前提；沿用它是为了复用现有材料，不开展通用代数框架建设。复合、交与等化等数学模式已有历史材料，本轮不宣称新数学。 | This concerns multiplication closure, not subgroup construction. Group structure is stronger than necessary for transport; retaining it reuses existing assets without building a general algebra framework. Composition, intersections, and equalizers already have historical precedents; no mathematical novelty is claimed. |
| 本版本没有预留或盲测任务，不支持跨任务族、未见数据或指南收益结论。将来如做指南比较，两组须使用同一数学库，新增真实试验须另行冻结协议与额度。 | There are no reserved or blind tasks. This fixture establishes neither cross-family or unseen-data performance nor guidance benefit. A later guidance comparison must share mathematical sources and freeze a separate protocol and allowance. |

| ID | 中文任务 | English task |
| --- | --- | --- |
| c01 | 原始函数打包后运输封闭性 | Bundle a raw function and transport closure. |
| c02 | 构造复合映射及保持证据 | Construct a composite map and preservation evidence. |
| c03 | 配对映射运输同时约束 | Use a paired map for simultaneous constraints. |
| c04 | 配对映射与对角谓词处理等化约束 | Use a paired map and diagonal predicate for an equalizer. |
| c05 | 目标封闭但缺少映射保持性质的反例 | A closed target with a non-preserving map. |
| c06 | 映射保持运算但目标不封闭的反例 | A preserving map with a nonclosed target. |
