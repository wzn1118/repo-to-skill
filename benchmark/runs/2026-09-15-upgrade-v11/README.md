# Invalid preliminary evaluation / 无效的前置评测

**Do not cite this run as a benchmark result. Use [v12](../2026-09-16-upgrade-v12/report.md).**

The raw `results.json` and original `manifest.json` are retained unchanged. Two later files,
`ground-truth-results.json` and `report.md`, do not match that manifest: an evaluator regression
rejected omitted root paths, and those files were overwritten after finalization.
`fact-audit-v2.json` is an unsealed intermediate artifact, not a repaired manifest.

All these files remain here as a failed-run audit record. See [qualification.json](qualification.json).
They are excluded from README statistics and the v10/v12 comparison.

本目录保留一次未发布评测中的失误：根参数匹配错误，且评测文件在 manifest 写入后被覆盖。
原始静态结果和原 manifest 保持不变；两个摘要不匹配的文件不具备有效评测结论。
请引用重新跑完整固定 corpus 的 v12；不要引用本目录报告中的 13/40 或 4/30。
