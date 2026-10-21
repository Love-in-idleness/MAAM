# 可执行的证明方法 / An executable proof method

| 中文 | English |
| --- | --- |
| 这次把一个已有证明中的消去步骤整理成可读、可实例化、可核验的方法卡；没有引入新数学定义或理论包。卡与实例绑定由人工整理，工具没有自动发现方法。 | This work turns cancellation steps from an existing proof into a readable, instantiable and checkable method card. No mathematical definition or theory package is added. Extraction and instance bindings are authored rather than automatically discovered. |
| [方法卡](../experiments/left_inverse_method_v1/method.json)绑定此前 DeepSeek 的 d03 核验证书。相同的左消去步骤可处理源证明中的幂等关系，也可用于另一开发目标的平方关系。 | The [card](../experiments/left_inverse_method_v1/method.json) is bound to the earlier DeepSeek d03 certificate. The same left-cancellation steps cover the source proof's idempotent relation and a square relation in another development goal. |

| 接口 / Interface | 明确内容 / Explicit contract |
| --- | --- |
| 输入对象 / Objects | `h : Foundation.Group H`, `a b c : H` |
| 输入证据 / Evidence | `E : h.mul a b = c` |
| 结论 / Conclusion | `b = h.mul (h.inv a) c`, normalized by the declared identity laws |
| 参数 / Bindings | Group, element `a`, equality name and fresh intermediate name; `b,c` inferred from `E` |
| 所需工具 / Required tools | `congrArg`, `mul_assoc`, `inv_mul`, `one_mul`, `mul_one` |
| 步骤 / Steps | Multiply the equality on the left by `inv a`; reassociate; simplify the inverse and identity terms |
| 剩余义务 / Obligations | Correct types, equation direction, fresh names and exact argument occurrence; all checked by Lean |

```lean
have hc := congrArg (h.mul (h.inv a)) E
simpa only [← h.mul_assoc, h.inv_mul, h.one_mul, h.mul_one] using hc
```

| 中文 | English |
| --- | --- |
| 源 d03 使用 a·a=a，消去后得到 a=1；目标 d04 使用 a·a=1，消去后得到 a=inv(a)。这两个实例共有的是等式变换，而不只是相同的最终命题。 | Source d03 uses a·a=a to obtain a=1; target d04 uses a·a=1 to obtain a=inv(a). Their shared content is the equality transformation, rather than an identical final proposition. |
| d02 需要右侧消去；固定适配器没有实现右逆元性质的推导，因而保留原证。这不是说现有群公理推不出右逆元，也不是说目标不可证明。 | d02 needs right cancellation. The fixed adapter does not derive the right-inverse identity and retains its incumbent. This does not imply that the group axioms cannot derive right inverses or that the goal is unprovable. |
| 适用检查绑定基础库、目标源码、工具链、目标身份和导入集合的准确指纹。模板可参数化，但本次适配器仅覆盖两个已声明的开发目标，未实现一般数学匹配器。 | Applicability checks bind exact base and goal sources, toolchain, target identity and imports. The template is parameterized, but this adapter covers only two declared development goals, without a general mathematical matcher. |

## 执行和成本 / Execution and costs

| 中文 | English |
| --- | --- |
| 执行器复用冻结的 baseline_search：原证默认保留，候选必须通过隔离 Lean 且完整 Proof 模块严格更短，才允许替换。 | Execution reuses frozen baseline_search: originals remain unless an isolated Lean check validates a strictly shorter complete Proof module. |
| 参数、模板输出、方法卡、来源证书和提交结果逐项绑定。中断的实例不能重试覆盖；status 只回放记录，不重新求证。 | Bindings, template outputs, cards, origin certificates and submissions are linked. Interrupted instances cannot be retried or overwritten; status only replays records. |
| 局部辅助步骤已经计入完整 Proof 源码。新增 Lean 理论模块成本为零；方法卡、渲染器和控制器的字节及压缩成本仍另计一次，不能说方法本身没有成本。 | Local helper steps are charged in complete Proof source. Added Lean theory-module cost is zero; the card, renderer and controller still have separate once-only byte and compression costs. |
| executable 层包括这三个新增文件，并依赖共享的现有仓库工具；它不是包含所有依赖的独立可运行压缩包。另报“证明加卡”和“证明加执行层”的实际压缩字节，不将不同单位混成总分。 | The executable layer contains those three new files and assumes shared repository tools. It is not a standalone archive containing every dependency. Joint proof-plus-card and proof-plus-executable bytes are reported separately, without mixing units into a total score. |

```bash
python scripts/control_method_reuse.py prepare \
  --model-root data/model-baseline-pilot-20261021-v1/run \
  --root data/method-reuse-NEW
python scripts/control_method_reuse.py next --root data/method-reuse-NEW
python scripts/control_method_reuse.py next --root data/method-reuse-NEW
python scripts/control_method_reuse.py status --root data/method-reuse-NEW
```

## 已保留的开发检查 / Preserved development checks

| 中文 | English |
| --- | --- |
| 开发时的第一次 d04 包装代码失败：宽泛 rw 同时替换两个相同项。第二次明确只变换乘法的一个参数，通过 Lean，完整源码 90 token。两次记录均保留在 data/method-reuse-development-20261022-v1/。 | The first d04 development wrapper failed because a broad rw changed both repeated terms. The second explicitly transports one multiplication argument and passed Lean at 90 complete source tokens. Both records remain in data/method-reuse-development-20261022-v1/. |
| 这些人工开发检查与后续固定两槽实验分开计数；零模型调用不意味着没有开发或核验成本。测试中的 Lean 审计是模拟夹具，不能代替真实证书。 | These author-development checks are counted separately from the later fixed two-slot pilot. Zero model calls does not mean zero development or verification cost. Lean audits in unit tests are fixtures rather than actual certificates. |
| 本方法仍未证明能帮助 AI 独立找到参数或完成证明义务；也没有认知难度、预留效果或新理论因果收益结论。 | The method has not established that AI can independently find bindings or discharge obligations. There are no cognitive-difficulty, held-out-effect or causal theory-benefit conclusions. |
