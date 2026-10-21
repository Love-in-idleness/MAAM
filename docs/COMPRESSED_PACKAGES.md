# 完整源码包压缩计量 / Compressed source-package measurement

日期：2026-10-21；首版工具对已有 M1 参考证明做离线计量，不引入新理论、不重新生成证明，也不修改冻结评估器。
Date: 2026-10-21; this additive tool measures archived reference sources without new theory, model calls or changes to frozen evaluators.

用户提出的“压缩整套材料”现已成为可运行的小范围指标；它衡量既定编码下的绝对压缩字节数，暂不构造理解难度、未来价值或多个指标的综合分。
The implementable target is absolute compressed size under a fixed encoding; cognitive scores, unobserved future value and universal optimal representations remain deferred research ideas.

## 内容与边界 / Payload and boundary

工具从冻结 manifest 推导两边的模块，基线包含原证明，引入包的一边包含完整候选模块和新证明，每个模块计一次。
Module membership comes from the manifest, with the whole candidate charged once even when a declaration is unused by this particular task.

编码复用 `maam.migration.canonical`：模块名映射到原始 UTF-8 源码文本，键排序，紧凑 JSON，不改变注释、空白、名称、imports 或 Unicode。
The module-to-source JSON framing is part of the cost, including escaped newlines; it introduces no archive timestamps or filesystem metadata.

两边分别把全部材料共同序列化并压缩，主指标使用 zlib level 9、窗口 15，bzip2 level 9 仅作为另一种编码的对照，均实际解压并检查逐字节一致。
Compress the complete payload jointly, rather than summing separately compressed modules or comparing compression ratios.

| 范围 / Scope | 计入内容 / Included content | 含义 / Meaning |
| --- | --- | --- |
| `nonshared_payload` | 基线证明，或完整候选加新证明 / Baseline proof, or full candidate plus treatment proof | 固定背景源码排除后的载荷成本 / Payload with shared background excluded |
| `standalone_sources` | 上述内容加共同 `Base` / Charged modules plus shared `Base` | 本地源码整体，仍依赖外部 Lean Init 与工具链 / Joint local sources, with external Init and toolchain |

`nonshared_payload` 不是压缩条件复杂度，也不是 `C(K+X)-C(K)`；压缩通常不满足可加性，不能把共同基础从压缩结果中直接抵消。
The second scope measures the actual joint encoding with `Base`; neither scope estimates an AI's internal acquisition cost.

报告、日志、旧证档案、方法说明与运行环境二进制不进入本轮数学源码载荷，原始文件全部保留；若未来评价“学习方法包”的成本，必须另行冻结包含说明与搜索程序的载荷。
This source metric does not silently claim to include documentation, method search or historical generation resources.

## 证据绑定 / Evidence binding

首版脚本固定已有 reference JSON 与验证 receipt 的原始 SHA-256，再复用 `load_experiment`、`check_reference` 和 `compare_audits`，核对源码、目标、账本与运行来源。
The pinned archive identities are trust inputs, not signatures or fresh mathematical verification; the receipt's artifact ZIP digest is not treated as the JSON digest.

只检查状态、输入指纹和账本自洽不足以证明报告来源：修改某个审计量后重算 comparison，仍可能自洽，所以先核对独立固定的归档身份。
A regression test mutates the audit and recomputes its comparison, requiring rejection before that replacement can be measured as archived evidence.

输出记录载荷和压缩流哈希、完整模块清单、评估器与序列化器指纹、Python 与 zlib 版本；标准库没有提供的 bzip2 运行库版本保留为空。
Strict replay includes the runtime and actual compressed bytes; it reports drift instead of assuming byte-identical output across compressor versions.

## 运行与回放 / Run and replay

在仓库根目录写入一个尚不存在的输出路径：
Run from the repository root with a new output path:

```bash
python scripts/measure_compressed_reference.py --output /tmp/maam-compression-NEW.json
python scripts/measure_compressed_reference.py --check /tmp/maam-compression-NEW.json
```

已有输出不会被覆盖，改变了源码、归档、工具或运行时后，严格回放返回非零；跨环境复查应生成新的报告并并列保存。
CI creates and checks a report in its own temporary directory, so a different runtime does not rewrite or reinterpret the committed measurement.

## 2026-10-21 小范围结果 / Small offline result

[已保存报告](../results/compressed-reference-v1.json)使用 CPython 3.14.8、zlib 1.3.2，对单条历史 `kernel_mul` 开发任务做计量。
This is an engineering probe over one supplied historical witness pair, whose baseline has not been certified as sufficiently prepared.

| 范围 / Scope | 原始源码字节：基线→候选 / Raw source bytes | zlib-9 字节 / Bytes | bzip2-9 字节 / Bytes |
| --- | ---: | ---: | ---: |
| 不含共同基础 / Nonshared | 349→1345 | 203→516 | 241→567 |
| 包含共同基础 / Joint local sources | 921→1917 | 438→704 | 494→776 |

当前两种编码、两种范围都观察到完整材料变大，局部证明缩短与整包成本增加可以同时发生；这不能推出同态概念在多任务中没有价值。
The result establishes neither fair new-concept attribution nor general usefulness, transfer, AI understanding or optimal package selection.

既有严格源码缩短规则继续决定选用哪份证明，压缩字节作为独立计量结果；逐题最短的选择也不保证整体压缩包最小。
The sidecar does not change proof adoption, optimize libraries, replace archived evidence or trigger reproving old theorems.

下一步使用[证明方法说明](PROOF_METHODS.md)明确一个已有工具的接口，再在小量、已准备的基线上检查新实例；当前只完成说明与计量工具。
Reuse experiments must retain their own applicability, verification and resource evidence before making a transfer claim.
