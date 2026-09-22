# Source-backed parameter validation / 源码参数校验

Discovery IR 1.6 can describe two bounded validation rules. They come from parsed
implementation, not helper names, README prose or a repository allowlist. This is
partial parameter semantics, not a proof that every generated operation is correct.

| Rule | Required source structure | Binding behavior |
| --- | --- | --- |
| `python_regex` | A Click string option uses a resolved nullable callback. Its only successful path calls a resolved helper that compiles the supplied value through the standard `re` module. The error path raises `click.BadParameter`. | Compile the user-supplied pattern with the compiler's Python runtime; reject invalid patterns before generating an invocation. |
| `ascii_case_insensitive_choices` | A local Cobra helper registers a string-backed custom value. Its `Set` method rejects values outside a literal choice list through `strings.EqualFold`, stores the unchanged value and returns nil. `String`, `Type`, choice checking and error formatting must match the supported AST forms. | Accept the declared ASCII spellings without case sensitivity; retain the user's spelling in argv. Reject non-ASCII inputs rather than approximate Go's Unicode comparison. |

The Python rule follows resolved imports and aliases. It rejects custom option classes,
unrecognized transformations, added callback statements, shadowed imports, explicit module
attribute reassignment and repository-local standard-module impersonation. The optional
newline-to-verbose-regex helper branch is recognized, but structured argument inputs still
reject control characters. Regex acceptance is relative to the compiler's Python version;
it does not promise compatibility with a different target interpreter or pattern runtime cost.

The Go rule checks the helper, backing type, methods and local predicate/formatting functions.
Additional value methods, changed setters, dynamic choices, wrong command owners and
conditional registrations are unsupported. Literal `MarkFlagRequired` calls preserve their
own source evidence. This rule does not infer arbitrary `pflag.Value`, inherited flags,
build-tag behavior, side effects of the final command or later dynamic mutations.

Each admitted parameter retains full-line-range witnesses for its declaration and the
validation implementation. Existing generated references display `validation`, `choices`,
type and default declarations. CLI, UI and model-candidate workflows use the same binder.
No target module is imported and no target program runs during analysis.

The snapshot's source hashes and line witnesses support review; they are not a substitute
for semantic auditing. Adversarial fixtures use renamed symbols and mutated implementations.
Pinned public tasks independently check real outputs in the existing isolated runner.

## Protocol compatibility

IR 1.2–1.5 files require explicit `r2s migrate`. The original files are preserved, no validator
is invented, and migrated results remain `REVIEW_REQUIRED`. A file labeled 1.5 cannot carry
the new validation field. Invalid framework/type/choice combinations are rejected at the
strict input boundary. Re-analyze source to acquire new evidence-backed rules.
Previously generated bundles also require rebuilding under the new boundary; changing a
version field or reusing an old readiness result is not a supported bundle upgrade.

## 中文说明

本轮补上两类可追溯约束：Click 的纯正则校验回调，以及 Cobra 的本地字符串枚举包装。
识别依据是实现结构和绑定关系，不是仓库名或函数名。非法正则、枚举外取值、未建模的
自定义行为会阻止调用生成；Go 枚举只支持有证据的 ASCII 子集，保留大小写输入。

声明、必填标记、回调、底层编译函数、枚举类型及校验方法均保留源码证据。
静态识别不会执行目标代码，也不等同于完整语义正确性或 Agent 收益验证。
旧 IR 显式迁移后仍需审核；应重新分析源码来获得新增语义。
