# Strict discovery contract / 严格发现契约

The serialized Discovery IR is version `1.4.0`. It adds explicit parameter keyword declarations
to the scoped command graph; **this is not completion of the planned IR v2 CLI graph**.
The boundary, its schema and the compiler cache derive from the same implementation.

## What is checked

`DiscoveryIR.from_dict`, loading a discovery run, writing discovery and generating a bundle
all use the strict Pydantic boundary in `r2s.discovery_contract`.

- Required fields remain required on input even when internal dataclasses have constructor defaults.
  Unknown fields are rejected, including fields nested inside claims and source locations.
- Booleans, numbers, enums, relative source paths, hashes, Git OIDs and confidence bounds are checked.
  Duplicate JSON keys, non-finite numbers and excessive nesting are rejected. File loading is bounded.
- Claim values have separate entrypoint, subcommand, option and license contracts. The predicate
  must match the payload; options have an explicit command path when scoped. Unknown payload keys
  are not accepted.
- Option `semantics` has strict framework, scope and optional literal fields. The entire value must
  match source evidence. Omitted fields stay unknown; no effective defaults or runtime behavior are inferred.
- IDs and inventory paths must be unique. References must resolve. An evidence source must match
  its inventory hash, blob and snapshot commit. Claim values must have a matching evidence witness.
- `CommandSpec` is reconstructed from supported claims. Every child has its parent declaration and
  evidence chain; each option belongs to exactly one recorded path. Generated references preserve
  this ownership rather than flattening child flags onto the root command.
- A capability has one entrypoint and cannot borrow options or subcommands from another command.

The full nested JSON Schema is exported with:

```bash
r2s schema export --output discovery.schema.json
```

The checked-in [schema](../schemas/discovery.schema.json) is compared with that export in tests.
JSON Schema expresses field constraints; referential and source/claim consistency additionally
require the runtime validator. A schema-only validator is not equivalent to the full reader.

These checks establish structural and internal consistency. They do **not** independently
authenticate an upstream source or prove that a string in source defines executable CLI behavior.
Evidence payloads still have extractor-specific dictionaries; byte ranges, parameter/argument
semantics beyond explicit keywords, option inheritance and complete cross-file command semantics remain future IR v2 work.
Discovery 1.4 does not attest the original analyzer binary. Reusing any prior IR does not rerun
repaired extraction rules; perform fresh discovery to benefit from analyzer fixes.

## Explicit import of historical 1.2/1.3 data

Historical files are not rewritten during load. The reader rejects invalid records and does not
silently infer missing security fields. Use a new output directory for an explicit migration:

```bash
r2s migrate old-run/discovery.json --output migrated-runs
r2s migrate old-run/run_<id> --output migrated-runs
```

The migration only merges **identical** Evidence records sharing an ID. A 1.2 option has no child
path, so it imports only as a root option and receives a blocking review finding; migration never
guesses subcommand ownership. Conflicting records, unknown versions, absent required fields and
unresolved references remain errors. Directory input also undergoes envelope and available SQLite
index checks; standalone JSON has no such envelope. Old flat formats and future schema versions
require a supported importer or fresh discovery.
Version 1.3 imports its existing command graph without inventing parameter fields; it also requires review.

The new run contains `migration.json` with the original file hash, target IR hash, rule version,
removed IDs and the new run ID. The original commit remains pinned. A blocking
`MIGRATION_REVIEW_REQUIRED` finding ensures generation cannot inherit a historical readiness result.
The report itself is informational and unsigned. Repeating the same import checks the existing
result and leaves it unchanged.

The [current import measurement](../benchmark/runs/2026-09-16-upgrade-v13/migration-verification.json)
checks all 45 discovery JSON files retained by upgrade-v12. All require explicit 1.3 → 1.4
migration and remain `REVIEW_REQUIRED`; all original bytes and source commits are preserved.
A retained 1.3 directory envelope also passes its split-artifact and SQLite checks before import.
This is structural migration evidence, not semantic validation or fresh source discovery.
The [older 42-file measurement](../benchmark/runs/2026-09-15-upgrade-v6/discovery-migration.json)
used the previous 1.2 reader and is retained separately; its 37 direct passes do not apply to 1.4.

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

本次升级将序列化 IR 升级到 `1.4.0`，增加严格类型化的显式参数声明，**没有把完整
IR v2、参数语义或跨语言命令图标记为完成**。子命令、父命令和选项归属必须共享证据链；生成物不会
将子命令选项扁平到根命令。字段、类型、枚举、路径、摘要和引用仍全部校验，不接受重复 JSON key 或未知字段。

`r2s migrate` 只合并同 ID 且内容完全相同的 Evidence；1.2 的选项只能迁为根选项并保持审核阻塞，
不推测子命令归属，不改写历史文件，也不继承旧的 READY 结论。当前核验 v12 保留的全部 45 份 1.3 发现结果，
均显式迁为 1.4 并保留 `REVIEW_REQUIRED`，不补猜参数语义；另核验一个带拆分产物和 SQLite 索引的历史目录。
源文件字节和固定 commit 均保持不变。旧版 42 份检查使用旧 reader，不能移作本版成绩。

缓存身份现在包含真实源码、依赖、运行时、客户端配置及完整/增量范围。生成前后校验身份，
重复生成比对文件，不覆盖用户修改。结构自洽、源码语义正确、运行成功和 Agent 效果仍是不同门槛；
这些改动不提供零幻觉或任务提升结论。
