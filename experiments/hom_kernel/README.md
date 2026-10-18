# 同态与核的参考迁移 / Reference migration: homomorphisms and kernels

这是研究计划 M1 的第一个受控实验：把乘法保持函数及其单位元原像组织为同态、核的载体类型和核上的乘法，再用这些对象重证同一个原始目标。
This is the first controlled M1 experiment: organise multiplication-preserving functions and their identity fibres as homomorphisms, kernel carrier types and multiplication on kernels, then reprove the same original goal using those objects.

## 数学目标 / Mathematical goal

设 f 满足 f(xy)=f(x)f(y)。若 f(x)=1 且 f(y)=1，则 f(xy)=1。
Let f satisfy f(xy)=f(x)f(y). If f(x)=1 and f(y)=1, then f(xy)=1.

Base.lean 定义群的运算与公理，并把上述全称命题定义为共同目标 Foundation.kernelMulGoal。
Base.lean defines group operations and axioms and records the universally quantified proposition as the shared goal Foundation.kernelMulGoal.

Baseline.lean 直接使用乘法保持条件、等式替换和单位元律证明目标；Treatment.lean 构造 Theory.Hom，再调用候选包中的核封闭性定理。
Baseline.lean proves the goal directly with multiplication preservation, equality transport and the identity law; Treatment.lean constructs a Theory.Hom and applies the candidate's kernel-closure theorem.

Candidate.lean 提供 Hom、kernel、Kernel、kernel_mul 与 Kernel.mul；Kernel 是子类型载体，此阶段只实现其乘法，完整的群结构与更多配套性质属于后续工作。
Candidate.lean provides Hom, kernel, Kernel, kernel_mul and Kernel.mul; Kernel is a subtype carrier with multiplication at this stage, while its full group structure and further properties remain future work.

## 运行 / Run

在仓库根目录运行：
Run from the repository root:

~~~bash
python -m maam evaluate-package --experiment experiments/hom_kernel/experiment.json
~~~

输入源码、工具链与验证资源由 experiment.json 冻结；package.json 列出核心思想和必需声明。
experiment.json freezes sources, toolchain and verification resources; package.json lists the idea and required declarations.

两个证明都返回原始目标，Lean 在隔离环境中重新编译并审计依赖。
Both proofs establish the original goal, freshly compiled and dependency-audited in isolated Lean environments.

## 首次实际结果 / First measured result

[实际工作流](https://github.com/Love-in-idleness/MAAM/actions/runs/39096441833) 已通过；仓库保留 [对照报告](../../results/theory-package-reference.json)、[六种错误输入的检查结果](../../results/theory-package-negative.json) 和 [运行来源记录](../../results/theory-package-validation.json)。
The [actual workflow](https://github.com/Love-in-idleness/MAAM/actions/runs/39096441833) passed; the repository retains the [comparison report](../../results/theory-package-reference.json), [six invalid-input checks](../../results/theory-package-negative.json) and [run provenance](../../results/theory-package-validation.json).

| 测量 / Measurement | 基线 / Baseline | 引入候选后 / Treatment |
| --- | ---: | ---: |
| 局部证明体源码 token / Local proof-body tokens | 77 | 29 |
| 局部内部证明构造器 / Local proof-expression constructors | 379 | 124 |
| 全部非共享源码 token / All nonshared source tokens | 89 | 353 |

这条证明的源码体减少 48 个 token，内部证明体减少 255 个构造器；计入候选包后，本轮总源码增加 264 个 token。
The local proof body saves 48 source tokens and 255 expression constructors; after charging the candidate package, total source increases by 264 tokens.

这一结果同时记录了局部复用收益和引入理论的成本；它没有确定同态概念的一般数学价值，也没有独立测量求证搜索收益。
The result records both local reuse gains and theory-introduction costs; it determines neither the general mathematical value of homomorphisms nor independently measured proof-search gains.

目标声明头在两边都引用共同的目标定义；报告中的头部 token 数是这种写法的源码计数，不是把全称命题展开后的长度。
Both declaration headers refer to the shared goal definition; header token counts measure that source representation rather than the expanded universal proposition.

这是单条开发任务、给定证明的参考轨迹；尚未进行预留任务评价、自动迁移或 LLM 强化学习。
This is a supplied reference trace for one development task; held-out evaluation, automatic migration and LLM reinforcement learning have not yet been performed.

详见 [接口与成本口径](../../docs/THEORY_PACKAGES.md) 和 [研究计划](../../docs/RESEARCH_PLAN.md)。
See the [interface and cost conventions](../../docs/THEORY_PACKAGES.md) and [research plan](../../docs/RESEARCH_PLAN.md).
