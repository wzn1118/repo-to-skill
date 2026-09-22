from pathlib import Path

import pytest

from r2s.javascript_symbols import JavaScriptGraph
from r2s.scanner import scan
from r2s.syntax import field, text

pytest.importorskip("tree_sitter_javascript")


def graph(root: Path, files: dict[str, str], **limits) -> JavaScriptGraph:
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return JavaScriptGraph(scan(root), **limits)


def test_reexports_object_destructuring_and_aliases_keep_all_source_hops(tmp_path):
    resolver = graph(tmp_path, {
        "entry.js": 'import {renamed} from "./barrel.js"; export {renamed};',
        "barrel.js": 'import {internal as shared} from "./api.js"; export const {normalize: renamed} = shared;',
        "api.js": 'import {source as normalize} from "./core.js"; const helper={normalize}; export {helper as internal};',
        "core.js": 'export function source(value){return value;}',
    })
    resolved = resolver.exported(tmp_path / "entry.js", "renamed")
    assert resolved is not None and text(field(resolved.node, "name")) == "source"
    assert {site.path.name for site in resolved.sites} == {"entry.js", "barrel.js", "api.js", "core.js"}


def test_namespace_and_default_reexports_resolve_without_loading_modules(tmp_path):
    resolver = graph(tmp_path, {
        "entry.js": 'import * as table from "./barrel.js"; const selected=table.run; export default selected;',
        "barrel.js": 'export {default as run} from "./core.js";',
        "core.js": 'export default function main(value){return value;}\nthrow new Error("must not run");',
    })
    resolved = resolver.exported(tmp_path / "entry.js", "default")
    assert resolved is not None and text(field(resolved.node, "name")) == "main"


@pytest.mark.parametrize("source", [
    'const value={valid:1}; value.valid=2; export default value;',
    'function value(){} function value(){} function value(){} export {value as default};',
    'export function value(){} value=other; export {value as default};',
    'const value=first; const value=second; export default value;',
    'export {first as default}; export {second as default}; const first={}; const second={};',
])
def test_overwritten_or_duplicate_bindings_remain_unresolved(tmp_path, source):
    resolver = graph(tmp_path, {"entry.js": source})
    assert resolver.exported(tmp_path / "entry.js", "default") is None


def test_cycles_unscanned_imports_and_wildcard_exports_do_not_guess(tmp_path):
    resolver = graph(tmp_path, {
        "first.js": 'export {value} from "./second.js";',
        "second.js": 'export {value} from "./first.js";',
        "missing.js": 'export {value} from "./not-there.js";',
        "wildcard.js": 'export * from "./other.js";',
        "other.js": 'export const value={};',
    })
    for name in ("first.js", "missing.js", "wildcard.js"):
        assert resolver.exported(tmp_path / name, "value") is None
    assert "JS_SYMBOL_CYCLE_OR_DEPTH" in resolver.diagnostics


def test_dynamic_spreads_can_override_fields_but_prior_spreads_cannot(tmp_path):
    resolver = graph(tmp_path, {
        "entry.js": 'const good={...dynamic, chosen: "literal"}; const bad={chosen:"literal",...dynamic}; export {good,bad};',
    })
    good = resolver.select(resolver.exported(tmp_path / "entry.js", "good"), "chosen")
    assert good is not None and text(good.node) == '"literal"'
    assert resolver.select(resolver.exported(tmp_path / "entry.js", "bad"), "chosen") is None


def test_module_and_depth_limits_fail_closed(tmp_path):
    resolver = graph(tmp_path, {"first.js": 'export {value} from "./second.js";', "second.js": 'export const value={};'}, max_modules=1)
    assert resolver.exported(tmp_path / "first.js", "value") is None
    assert "JS_SYMBOL_MODULE_LIMIT_OR_UNSCANNED" in resolver.diagnostics
