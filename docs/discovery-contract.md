# Strict discovery contract / 严格发现契约

The serialized Discovery IR retains version `1.2.0`. The new reader enforces
`strict-discovery-1.2-revision-2`; **this is not completion of the planned IR v2 command graph**.
The boundary, its schema and the compiler cache now derive from the same implementation.

## What is checked

`DiscoveryIR.from_dict`, loading a discovery run, writing discovery and generating a bundle
all use the strict Pydantic boundary in `r2s.discovery_contract`.

- Required fields remain required on input even when internal dataclasses have constructor defaults.
  Unknown fields are rejected, including fields nested inside claims and source locations.
- Booleans, numbers, enums, relative source paths, hashes, Git OIDs and confidence bounds are checked.
  Duplicate JSON keys, non-finite numbers and excessive nesting are rejected. File loading is bounded.
- Claim values have separate entrypoint, option and license contracts. The predicate must match
  the payload; options have an explicit command owner. Unknown payload keys are not accepted.
- IDs and inventory paths must be unique. References must resolve. An evidence source must match
  its inventory hash, blob and snapshot commit. Claim values must have a matching evidence witness.
- A capability has one entrypoint and cannot borrow an option from another command.

The full nested JSON Schema is exported with:

```bash
r2s schema export --output discovery.schema.json
```

The checked-in [schema](../schemas/discovery.schema.json) is compared with that export in tests.
JSON Schema expresses field constraints; referential and source/claim consistency additionally
require the runtime validator. A schema-only validator is not equivalent to the full reader.

These checks establish structural and internal consistency. They do **not** independently
authenticate an upstream source or prove that a string in source defines executable CLI behavior.
Evidence payloads still have extractor-specific dictionaries; a fully typed, versioned command
graph, byte ranges and cross-file semantics remain future IR v2 work.
Discovery 1.2 does not attest the original analyzer binary. Reusing old IR does not rerun repaired
extraction rules; perform fresh discovery to benefit from analyzer fixes.

## Explicit import of historical 1.2 data

Historical files are not rewritten during load. The reader rejects invalid records and does not
silently infer missing security fields. Use a new output directory for an explicit migration:

```bash
r2s migrate old-run/discovery.json --output migrated-runs
r2s migrate old-run/run_<id> --output migrated-runs
```

The migration only merges **identical** Evidence records sharing an ID. Conflicting records,
unknown versions, absent required fields and unresolved references remain errors. Directory input
also undergoes envelope and available SQLite index checks; standalone JSON has no such envelope.
Old flat formats and future schema versions require a supported importer or fresh discovery.

The new run contains `migration.json` with the original file hash, target IR hash, rule version,
removed IDs and the new run ID. The original commit remains pinned. A blocking
`MIGRATION_REVIEW_REQUIRED` finding ensures generation cannot inherit a historical readiness result.
The report itself is informational and unsigned. Repeating the same import checks the existing
result and leaves it unchanged.

The [historical import measurement](../benchmark/runs/2026-09-15-upgrade-v6/discovery-migration.json)
checks the 42 discovery JSON files retained by upgrade-v5. Of these, 37 pass directly; pytest,
pip, httpie, Vite and pnpm require identical-evidence deduplication. All five migrate to
`REVIEW_REQUIRED`; all 42 original files remain byte-identical. This is not a 42-repository
semantic success rate and does not replace the 45-repository public benchmark.

## Compilation identity and write behavior

`compiler.lock.json` binds the full discovery digest, normalized goal, target, selected capability
IDs, full/delta scope and compiler identity. The compiler identity includes package source/resource
hashes, installed dependency versions, Python runtime/platform and the actual client profile.
A short displayed ID does not replace the full request digest; collisions or altered locks fail.

Generation checks this request before use, renders into a temporary directory and compares the
compiler identity again before publication. `generation.lock.json` records that identity and all
generated file hashes. Repeating generation re-renders and compares the bytes without overwriting
existing output. Modified or unmanaged generated files are rejected. Direct SDK calls also receive
a generation lock; they do not acquire a fictitious discovery parent ID.

Files are staged, and the generation lock is published last. A reservation prevents concurrent
writers from entering the same compilation. Interrupted or incomplete publication fails closed;
automatic crash recovery and a transactional background job service remain open work. This is not
a cross-process code signature or an attestation of loaded Python modules. Do not modify the compiler
installation while it is running; restart the process after upgrades.

## 中文说明

本次升级保留 `1.2.0` 的序列化结构，强化 JSON 读写与编译入口的严格校验，**没有把 IR v2、
命令图和跨文件分析标记为完成**。字段、类型、枚举、路径、摘要、引用和命令归属均进行检查；
不再把缺失的状态字段自动补成可信值，也不接受重复 JSON key 或未知字段。

`r2s migrate` 只合并同 ID 且内容完全相同的 Evidence，不推测缺失事实，不改写历史文件，
不继承旧的 READY 结论。实际核验了旧版本保留的 42 份发现结果：37 份直接通过，5 份需迁移，
迁移结果全部保留 `REVIEW_REQUIRED`。源文件字节和固定 commit 均保持不变。

缓存身份现在包含真实源码、依赖、运行时、客户端配置及完整/增量范围。生成前后校验身份，
重复生成比对文件，不覆盖用户修改。结构自洽、源码语义正确、运行成功和 Agent 效果仍是不同门槛；
这些改动不提供零幻觉或任务提升结论。
