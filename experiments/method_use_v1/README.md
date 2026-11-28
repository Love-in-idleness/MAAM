# Method-use development fixture v1

| 中文 | English |
| --- | --- |
| 本目录实现已审阅方案中的六个作者设计任务。U01–U04 是同一消去方法的近邻变化，U05–U06 检查适用边界；全部属于开发校准，不声称预训练未见或独立领域迁移。 | Six author-designed tasks implement the reviewed proposal. U01–U04 are nearby variations of one cancellation method; U05–U06 test applicability boundaries. All are development calibration, without claims of pretraining-unseen tasks or transfer across independent domains. |
| A、B 两组共享完全相同的 `Base` 和 `Method` 数学模块；仅 B 组额外收到 `guide.txt`。内部核验两组都使用 `condition="treatment"`，这个历史接口标签只代表共享引理可用。 | A and B share identical `Base` and `Method` mathematical modules; only B receives `guide.txt`. Both use the internal verification condition `"treatment"`, a legacy interface label indicating that the shared lemma is available. |
| `Base.lean` 与 `metered_transfer_v1/Base.lean` 字节相同。`MethodUse.left_factor` 是一般引理，证明包含在两组共同材料中。指南为 255 个按空白分隔的英文单词，不含目标专用参数或参考证明。 | `Base.lean` is byte-identical to `metered_transfer_v1/Base.lean`. The general lemma `MethodUse.left_factor` and its proof are common materials. The guide contains 255 whitespace-delimited English words and no target-specific bindings or reference proofs. |
| `suite.json` 与 `package.json` 复用 `maam.migration.load_suite` 模式及源码哈希。`protocol.json` 固定外层两组、重复次数、角色和预算；角色标签与参考材料仅用于控制器和报告。 | `suite.json` and `package.json` reuse the `maam.migration.load_suite` schema and source hashes. `protocol.json` fixes the outer conditions, repetitions, roles, and budgets. Role labels and references are controller/reporting materials only. |
| `reference_proofs.json` 的 `tasks` 按小写任务 ID 映射到 `{proof, bridge}`。`proof` 是 `:=` 后的 Lean 项；`migration.proof_source` 可据此生成完整 `Proof.lean`。人工参考不能进入模型请求。 | `reference_proofs.json` maps lowercase task IDs under `tasks` to `{proof, bridge}`. `proof` is the Lean term after `:=`; `migration.proof_source` constructs the complete `Proof.lean`. Author references must never enter model requests. |
| 六份参考已于 2026-10-27 使用 Lean 4.24.0 通过核验和包、公理审计。这只是人工参考可用性证据，不能当作真实模型生成或独立方法使用结果。 | All six references passed Lean 4.24.0 verification and package/axiom audits on 2026-10-27. This establishes author-reference validity, not live model generation or independent method use. |

从仓库根目录复核人工参考（零 API 调用；下方沿用原核验器，不是新增操作系统沙箱的验收）：

Recheck author references from the repository root (zero API calls; this uses the original verifier and does not establish acceptance of the new OS sandbox):

```python
import json
import tempfile
from pathlib import Path
from maam.migration import start_session, task_request, submit_attempt

fixture = Path("experiments/method_use_v1")
session = Path(tempfile.mkdtemp(prefix="maam-method-use-reference-")) / "session"
start_session(fixture / "suite.json", session, condition="treatment",
              solver_id="author-reference", mode="supplied_reference")
references = json.loads((fixture / "reference_proofs.json").read_text())["tasks"]
for task_id, reference in references.items():
    request = task_request(session, task_id)
    result = submit_attempt(session, {
        "task_id": task_id, "request_sha256": request["request_sha256"], **reference
    })
    assert result["status"] == "verified", result
print(session)
```
