# 实验报告 / Experiment reports

`mathlib/` 保存固定论文快照上的独立测量：摘要、四张图、分桶中位数、SCC 清单及参考计数口径的前 100 个定理。
`mathlib/` contains independent measurements on the fixed paper snapshot: a summary, four plots, bucket medians, SCCs, and the top 100 theorems under the reference-count convention.

以 `summary.json` 的快照、输入哈希、覆盖率、拟合窗口和差异为准；图号对应论文研究的问题，不能据此声称逐像素重现了原图。
Use `summary.json` for the snapshot, input hash, coverage, fit windows, and discrepancies; figure numbers identify the corresponding paper questions and do not imply pixel-exact reproduction.

完整原始导出和可查询的 SQLite 指标索引保存在成功工作流的 `fixed-mathlib-reproduction` 下载产物中，解压后可用 `maam score-index` 查询。
The full raw export and queryable SQLite metric index are retained in a successful workflow's `fixed-mathlib-reproduction` artifact; decompress the index and query it with `maam score-index`.

`monoids/` 保存精确有限枚举结果；`right_censored` 表示只能得到下界，不应读作无限覆盖。
`monoids/` contains exact finite enumerations; `right_censored` indicates a lower bound and must not be read as infinite coverage.

命令、边界约定和未完成目标见 [复现说明](../docs/REPRODUCTION.md)。
See the [reproduction guide](../docs/REPRODUCTION.md) for commands, boundary conventions, and remaining targets.
