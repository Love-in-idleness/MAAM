# 定理输出契约 v2 / Theorem output contract v2

| 中文 | English |
| --- | --- |
| 本版本修正上一轮 `def/theorem` 输出说明歧义。完整 JSON 响应只含 `proof` 字符串，内容是完整 `Proof.lean`，明确要求用 `theorem` 声明 `Submission.solve`，类型保持所给目标。不改写提交源码，也不把证明项当作完整源码接受。 | This version clarifies the previous `def/theorem` ambiguity. The JSON response contains only a `proof` string holding complete `Proof.lean` source. Explicitly declare `Submission.solve` using `theorem` with the supplied goal type. Submitted sources are not rewritten, and proof terms are not accepted as complete source. |
| 数学内容、六个开发目标、人工参考和指南逐字节复用 [closure_transport_v1](../closure_transport_v1/README.md)，协议绑定原哈希。A/B 数学相同，仅 B 增加指南。参考、任务角色和旧目标证明不进入求解输入。 | Mathematical content, six development goals, author references, and guidance reuse [closure_transport_v1](../closure_transport_v1/README.md) byte for byte, bound by protocol hashes. A/B share mathematics; only B adds guidance. References, task roles, and existing target proofs stay outside solver inputs. |
| 本次只有离线契约验收：六份 namespace theorem 参考、一个全限定名 theorem 正例，以及 `def`、错误目标、新公理、额外导入和孤立证明项五个反例，共 12 个固定槽位，每槽只检查一次。它们都是作者控制，不是新模型生成；不能把旧 `def` 人工改写计为模型成功。 | This is offline conformance acceptance only: six namespace-theorem references, one fully qualified theorem positive, and five negatives covering `def`, a wrong goal, a new axiom, an extra import, and a bare proof term. Each of twelve fixed slots runs once. These are author controls, not model generations; manually rewriting old `def` output does not create model success. |
| `def` 反例可能先通过 Lean 编译，再被本项目的 theorem 声明约定拒绝。声明格式不合约与逻辑错误必须分开；检查器与旧实验都保持原样，不追溯重评分。 | A `def` control may compile in Lean and then fail the project's theorem-declaration convention. Contract nonconformance and logical invalidity remain distinct. The checker and old experiments are unchanged, without retrospective rescoring. |
| 新入口只生成离线求解消息和执行本地沙箱检查；没有 API、模型选择、密钥参数或付费额度。它不使旧付费调用器自动支持 v2。真实模型遵守率和指南效果仍未测量。 | The new entry point only emits offline solver messages and performs local sandbox checks. It provides no API, model selection, credential argument, or paid allowance, and does not upgrade frozen paid controllers to v2. Model compliance and guidance effects remain unmeasured. |
| 固定材料先提交再验收；预约、完整源码、JSON 响应、核验结果及日志绑定。中断记录不能重发。报告可离线重算，原始材料仍需保留。 | Commit fixed material before acceptance. Bind reservations, complete source, JSON responses, verification results, and logs. Interrupted slots cannot be resent. Reports replay offline and still require the raw evidence. |

```bash
python3 scripts/check_theorem_contract.py prepare data/theorem-contract-v2
python3 scripts/check_theorem_contract.py input data/theorem-contract-v2 --task c03 --guide
python3 scripts/check_theorem_contract.py run data/theorem-contract-v2
python3 scripts/check_theorem_contract.py report data/theorem-contract-v2
```
