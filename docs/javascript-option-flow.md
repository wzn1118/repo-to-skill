# Declarative JS option flow / JavaScript 参数流

The optional tree-sitter analyzer recognizes one bounded **normalized minimist + vnopts**
architecture. This is not arbitrary JavaScript interpretation, complete Prettier support,
or a claim that all table-shaped objects define CLI parameters.

## Evidence chain

1. Start at the package's admitted `bin` file. Follow direct local calls and literal dynamic
   imports whose callback actually calls an exported entry function. An import by itself is
   not enough to claim a CLI option. The classic entry obtains arguments from `process.argv`.
2. Resolve named/default imports, re-exports, namespace members, object properties and exported
   destructuring through scanner-admitted files. Reject cycles, overwritten/ambiguous symbols,
   unresolved wildcard exports and unbounded graphs. Limits are 128 modules, 32 symbol hops
   and 64 reachable entry scopes.
3. Verify context construction, initial subset parsing, complete argument parsing and table
   transfer. CLI/core option tables must pass the supported normalizer, CLI-name mapper,
   API-forwarding converter and context provider before reaching the actual parser.
4. Check the minimist boolean/string/default configuration and wrapper, then the vnopts schema
   list, constructors and validation path. Parameters keep declaration, import/export, parser,
   normalization and framework-dependency witnesses, with file ranges, hashes and commit pins.
5. Preserve the raw positional `_` array only when parser return and context assignment both
   support it. The positional name is the source's context property, not a README inference.

Source predicates and transformations are matched structurally with bound local identifiers;
the analyzer does not select by repository URL or helper name. The rule family is intentionally
narrow. Synthetic tests rename symbols and files, mutate data flow and remove connections.
The separately pinned Prettier snapshot tests the real implementation; matching synthetic
templates alone would not demonstrate real-project compatibility.

Structural matching preserves array holes, literal punctuation and generator/async markers;
only syntactic separators and comments can be omitted. Adversarial tests exposed overly broad
v21 matches at those boundaries. The [retained diagnostic](../benchmark/history/2026-09-22-v21-patterns.json)
records all three failures; v22 repairs them and reruns the fixed corpus and tasks.

## Supported parameter subset

- Literal boolean, integer, string/path and declared string-choice options; bounded kebab-case
  conversion or explicit CLI names; literal aliases and declaration defaults.
- For supported choices, preserve only explicit source entries. Plugin-added values and the
  wider acceptance of exception predicates are not guessed or claimed exhaustive.
- A pure exception consisting only of literal/typeof/boolean comparisons can supplement the
  proven built-in validator. Arbitrary function calls remain unknown, even if they look harmless.
- Array options, redirects, dynamic aliases/choices and unknown processing remain unbindable.
  Alias collisions do not choose an arbitrary winner. Negative-looking positional values remain
  subject to the existing ambiguity checks.
- External framework imports must correspond to declared registry-style dependencies, not
  `file:`, workspace or renamed-package specifications. This is a modeled dependency boundary,
  not cryptographic authentication of installed packages. Runtime measurements separately bind
  actual dependency inventories.

Declaration defaults do not guarantee effective runtime defaults. Conditional workflows,
cross-option constraints enforced by later application code, arbitrary plugin effects, monkey
patching and whole-program side effects are not fully modeled. The classic CLI flow does not
prove experimental-CLI compatibility. All emitted facts still need independent semantic review;
offline output checks establish only the selected tasks' observed results.

## Replaced unsafe shortcut

The previous implementation accepted a table whenever a nearby AST contained a matching name
expression and a function called `normalizeOptionSettings`. Those disconnected fragments did
not prove the table reached a CLI parser. That shortcut is removed, not retained as fallback.
A regression test now ensures disconnected normalizers cannot emit supported options.

## License and reproducibility

The structural patterns are adapted from the fixed Prettier source, not executed from it.
Its MIT notice is retained in
[`src/r2s/resources/notices/prettier.txt`](../src/r2s/resources/notices/prettier.txt) and included
in the wheel. Benchmarks keep the previous results; new compiler identities require new runs.
No target module is imported during analysis, and no model or network call is required.

## 中文说明

本轮把“附近有参数表”升级为“入口 → 导出/别名 → 表转换 → minimist → vnopts → 参数消费”的
有界源码链路。命名相似、单纯 import、孤立的转换函数都不足以生成事实；不会保留旧的宽松回退。

当前只支持明确的解析架构和参数子集，不是通用 JS 解释器。动态插件、数组/重定向、自定义处理、
后续业务代码的完整约束仍有缺口。固定源码实测、合成回归测试、源码溯源、完整语义审查和 Agent
收益分别统计，不以某一类通过替代其他门槛。
