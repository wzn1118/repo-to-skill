# Retained diagnostic workflow runs — 2026-09-22

These runs preserve the failures that led to [v17](../2026-09-22-v17/README.md).
All six attempts retain all 36 tasks and their unchanged reference/oracle hashes. They are
structured-input experiments, not Agent trials. No attempts are pooled into a headline score.

| Artifact | Passed / selected | Conditions and retained failure |
| --- | ---: | --- |
| `default.json` | 25/36 | New Cobra positionals and fzf scalar assignment analysis; standard scan |
| `expanded.json` | 25/36 | Expanded discovery; execution preparation still used the standard scan and rejected Prettier; gh runtime not yet prepared |
| `default-final.json` | 25/36 | Source rescan now honors the bundle's known profile; standard scan still blocks Prettier/gh |
| `expanded-final.json` | 25/36 | Node symlink rejected; gh build receipt records a failed build and cannot authorize execution |
| `standard-prepared.json` | 25/36 | Correct runtime files and successful gh build receipt; standard scan still blocks Prettier/gh |
| `expanded-prepared.json` | 27/36 | gh configuration and alias tasks pass; Prettier reaches execution but exceeds the 128-open-file sandbox limit |

The sandbox remains offline, non-root and read-only for source throughout. The Node symlink was
resolved to its actual executable; symlink rejection was not disabled. The final v16 runtime files
are Node 22.14.0 and a gh binary compiled from the corpus commit, rather than the host's installed gh.

`toolchain-preparation.json` records an isolated Go 1.27.1/dependency download. The first offline
build overflowed its 512 MiB tmpfs; the second moved compiler temporary/cache files to the data disk
and hit its 240-second wall limit. The third reused that cache and passed with the same
1 CPU / 1 GiB / 240-second per-attempt limits. All three receipts are retained; preparation/build
costs are separate from task execution. Logs in these receipts are bounded tails.

The first two attempts use a preliminary compiler with an execution-scan mismatch. To reconstruct
from the published v17 source in a separate checkout, apply
`benchmark/history/2026-09-22-v16-runtime.patch`, then
`benchmark/history/2026-09-22-v16-preliminary.patch`. Apply only the first patch for the other
four attempts. Every compiler-file hash and runner hash was checked before archiving these patches.
These patches are historical records, not fixes to apply to a working installation.

中文：第一次扩大扫描后，执行前复扫仍错误使用标准预算；修复后又暴露 Node 路径、gh 构建资源及
Prettier 文件句柄限制。这里保留每次失败，没有改写旧报告或放宽任务验收。最后一次通过 27/36，
后续有界资源配置与实测见 v17。尚未验证自然语言规划、Agent 收益或全部接口语义。
