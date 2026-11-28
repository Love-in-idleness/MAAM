# 数据输入格式

[English](DATA.md)

## 引用语料（Reference Corpus）

最小可用语料 JSON 如下（所有被引用的依赖必须显式声明，重复次数须为正整数）：

```json
{
  "schema_version": 1,
  "corpus_id": "your-fixed-corpus-v1",
  "length_basis": "references",
  "provenance": {"kind": "manual", "revision": "your-data-revision"},
  "nodes": [
    {"name": "Primitive", "kind": "primitive"},
    {
      "name": "YourTheorem",
      "kind": "theorem",
      "statement": "Your formal proposition",
      "signature": {"Primitive": 2},
      "body": {"Primitive": 3}
    }
  ]
}
```

- `signature` 与 `body` 为声明名到出现次数的映射（多重集而非集合）。
- `primitive` 是显式选定的展开边界，不得有出边；缺失依赖会直接报错，不会自动补为原始节点。

| 字段 | 取值 | 含义 |
| --- | --- | --- |
| `kind` | `primitive`、`axiom`、`definition`、`theorem`、`conjecture` | 节点身份 |
| `body` | 引用映射或 `null` | `theorem` 必填；`conjecture` 与 `axiom` 须为 `null` |
| `signature_tokens` | 正整数 | `length_basis = "source_tokens"` 时必填 |
| `body_tokens` | 非负整数 | `source_tokens` 模式下含证明体节点必填 |
| `statement` | 可选字符串 | 仅用于精确文本查询，不做语义解析 |
| `domain` | 可选模块标签 | 仅用于描述直接使用者 |
| `admitted` | 布尔值 | admission 污染标记，沿依赖关系传递 |

### 正确性与污染边界

- 没有证明的命题须使用 `kind: "conjecture"` 与 `body: null`。
- `body: {}` 表示已提供证明且其中没有被计数的引用（并非缺少证明），须由数据提供方保证属实。
- Python 读取 JSON 不自动附带 Lean 类型检查保证，须在 `provenance` 中独立记录核验来源。
- `admitted: true` 及名为 `sorryAx` / `Lean.sorryAx` 的节点会污染所有传递依赖者，使其退出评分对照组；但这不能防御恶意伪造 JSON。

## 大数精度处理

原始展开使用任意精度整数计算，不会构造实际展开字符串。报告输出位数、`log2` 以及不超过 3300 位时的精确十进制字符串（超出时 `exact: null`）。比值超出浮点范围时 `value` 为 `null` 但保留 `log2`，归一化直接基于对数计算以避免溢出。

## 有限证明超图（Finite Proof Hypergraph）

用于计算 `E_finite`，不把引用图伪装成完整证明搜索空间：

```json
{
  "schema_version": 1,
  "system_id": "your-finite-system",
  "statement_lengths": {"A": 2, "B": 3},
  "axioms": ["A"],
  "rules": [{"id": "derive-B", "conclusion": "B", "premises": ["A"]}]
}
```

此例中 `m(A) = 2`、`m(B) = 3 + 2 = 5`，故 `E_finite(B) = 5/3`。前提列表保留重复项，规则的逻辑有效性由调用方负责。

## 内置示例语料

- `examples/paper_simple_lemma.json`：对论文展示的内部表达式计数的人工转录，并非本地重新运行 Lean 生成。
- `examples/toy_corpus.json`：人工合成语料，用于测试压缩层级、复用与证明膨胀效应，不含真实人类兴趣标注。
