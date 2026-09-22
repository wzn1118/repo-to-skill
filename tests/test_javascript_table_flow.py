import json
import re
from pathlib import Path

import pytest

from r2s import javascript_table_rules as rules
from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, validate_path
from r2s.workflows import InvocationRequest, WorkflowRequest, bind_invocation

pytest.importorskip("tree_sitter_javascript")


def renamed(rule: str, name: str, replacements: dict[str, str] | None = None) -> str:
    source = getattr(rules, rule)
    source = re.sub(r"function(\*)? [a-zA-Z]+\(", lambda matched: "function" + (matched.group(1) or "") + " " + name + "(", source, count=1)
    for original, replacement in (replacements or {}).items():
        source = re.sub(re.escape(original) + r"\b", replacement, source)
    return re.sub(r"__([A-Za-z][A-Za-z0-9_]*)", r"bound_\1", source)


def repository(root: Path) -> dict[str, str]:
    files = {
        "LICENSE": "MIT",
        "package.json": json.dumps({"name": "sample", "bin": "entry.cjs", "dependencies": {"minimist": "1.2.8", "vnopts": "2.0.0", "dashify": "2.0.0", "camelcase": "8.0.0"}}),
        "entry.cjs": 'import("./app/start.js").then(function(module){return module.launch();});',
        "app/start.js": 'import Context from "./state.js"; async function launch(rawArguments = process.argv.slice(2)) {const logger={}; const context=new Context({rawArguments, logger}); await context.init();} export {launch};',
        "app/state.js": 'import {decode,initial} from "./decode.js"; import {context} from "./context.js"; class Context {constructor({rawArguments,logger}) {this.rawArguments=rawArguments; this.logger=logger;}'
        + renamed("CONTEXT_INIT", "init", {"__parse": "decode", "__push": "push", "__positional": "inputs", "__initial": "initial"}).replace("async function init", "async init")
        + renamed("CONTEXT_PUSH", "push", {"__provider": "context"}).replace("async function push", "async push")
        + '} export default Context;',
        "app/decode.js": 'import camel from "camelcase"; import options from "./options.js"; import wrapped from "./wrapper.js"; import normalize from "./normalize.js"; import {baseContext} from "./context.js"; const {detailedOptions: initialOptions}=baseContext();'
        + renamed("PICK_FIELDS", "selectFields")
        + renamed("ARGUMENT_PARSER", "decode", {"__create": "options", "__minimist": "wrapped", "__normalize": "normalize", "__camel": "camel", "__pick": "selectFields"})
        + renamed("INITIAL_PARSER", "initial", {"__parse": "decode", "__detailed": "initialOptions"}) + 'export {decode,initial};',
        "app/options.js": 'export default ' + renamed("MINIMIST_OPTIONS", "settings", {"__literal_special": '"plugin"'}),
        "app/wrapper.js": 'import parse from "minimist"; const empty=null; export default ' + renamed("MINIMIST_WRAPPER", "wrapped", {"__minimist": "parse", "__placeholder": "empty"}),
        "app/normalize.js": 'import normalizer from "../lib/values.js"; const FlagSchema={}; const descriptor={}; export default ' + renamed("CLI_NORMALIZER", "convert", {"__normalize": "normalizer"}),
        "lib/values.js": 'import * as schemaLibrary from "vnopts"; let warned; export default ' + renamed("VALUE_NORMALIZER", "normalize", {"__library": "schemaLibrary", "__create": "listSchemas", "__warned": "warned"})
        + renamed("SCHEMA_LIST", "listSchemas", {"__library": "schemaLibrary", "__convert": "makeSchema"})
        + renamed("SCHEMA_FACTORY", "makeSchema", {"__library": "schemaLibrary"}),
        "app/context.js": 'import dash from "dashify"; import declarations from "./declarations.js"; import {normalizeSettings,support,supportInfo} from "../lib/api.js"; const categories={};'
        + 'const detailed=normalizeSettings(declarations).map((item)=>describe(item));'
        + renamed("DETAIL_NORMALIZER", "describe", {"__dashify": "dash", "__categories": "categories"})
        + renamed("API_CONVERTER", "asCLI", {"__normalize": "describe", "__categories": "categories"})
        + renamed("CONTEXT_OPTIONS", "toContext", {"__cli": "detailed", "__convert": "asCLI"})
        + renamed("CONTEXT_PROVIDER", "context", {"__getSupport": "support", "__convert": "toContext"})
        + renamed("BASE_CONTEXT", "baseContext", {"__getSupport": "supportInfo", "__convert": "toContext"}) + 'export {context,baseContext};',
        "lib/api.js": 'import {supportInfo,normalizeSettings} from "./support.js";'
        + renamed("PLUGIN_WRAPPER", "wrap") + 'const support=wrap(supportInfo,0); export {support,normalizeSettings,supportInfo};',
        "lib/support.js": 'import core from "./core.js";'
        + renamed("TABLE_NORMALIZER", "normalizeSettings")
        + renamed("COLLECT_CHOICES", "extendChoices")
        + renamed("SUPPORT_PROVIDER", "supportInfo", {"__normalize": "normalizeSettings", "__core": "core", "__literal_extended": '"engine"', "__collect": "extendChoices"}) + 'export {normalizeSettings,supportInfo};',
        "app/declarations.js": 'const declarations={write:{type:"boolean",alias:"w"},config:{type:"path",exception:(value)=>value===false}}; export default declarations;',
        "lib/core.js": 'const values={engine:{type:"choice",choices:[{value:"json"},{value:"csv"}],exception:(value)=>typeof value==="string"},sourcePath:{type:"path",cliName:"stdin-name"},arrayField:{type:"path",array:true}}; export default values;',
    }
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return files


def test_parser_consumes_both_tables_and_positional_source_with_renamed_symbols(tmp_path):
    root = tmp_path / "source"
    repository(root)
    discovery = parse_discovery(discover(root).to_dict())
    options = {claim.object.get("option"): claim for claim in discovery.claims if claim.predicate == "supports_option"}
    assert set(options) == {"--write", "--config", "--engine", "--stdin-name", "--array-field"}
    assert options["--engine"].object["semantics"]["choices"] == ("json", "csv")
    assert options["--config"].object["shape"]["unknown_reasons"] == ()
    assert options["--write"].object["shape"]["aliases"] == ("--write", "-w")
    assert "array_arity_not_modeled" in options["--array-field"].object["shape"]["unknown_reasons"]
    sites = [evidence for evidence in discovery.evidence if evidence.id in options["--engine"].evidence_ids]
    assert {"entry.cjs", "app/decode.js", "lib/values.js", "lib/core.js", "lib/support.js", "app/options.js", "package.json"} <= {item.source.path for item in sites}
    request = InvocationRequest(command="sample", parameters={"--write": [], "inputs": ["input.txt"]}, expected_observation="Updated contents")
    assert bind_invocation(discovery.claims, request, "user_input").arguments == ("--write", "input.txt")
    build = generate(discovery, "write input", tmp_path / "build", "portable", workflow=WorkflowRequest(title="write input", steps=[request]))
    assert not validate_path(Path(build.bundles[0]))


@pytest.mark.parametrize(("filename", "before", "after"), [
    ("entry.cjs", 'return module.launch()', 'return module.notCalled()'),
    ("app/start.js", 'await context.init()', 'await unrelated.init()'),
    ("app/start.js", 'await context.init()', 'context=other; await context.init()'),
    ("app/start.js", 'const logger={}', 'rawArguments=[]; const logger={}'),
    ("app/start.js", 'const logger={}', 'rawArguments.splice(0); const logger={}'),
    ("app/start.js", 'await context.init()', 'context.rawArguments=[]; await context.init()'),
    ("app/start.js", 'const context=new Context', 'if(enabled){} const Context=fake; const context=new Context'),
    ("app/state.js", 'this.inputs = bound_argv._', 'this.inputs = []'),
    ("app/decode.js", 'bound_normalized._', '[]'),
    ("app/decode.js", 'bound_object[bound_key]', '"wrong"'),
    ("app/decode.js", 'initialOptions,', 'unrelatedOptions,'),
    ("app/options.js", 'bound_names.push(name)', 'bound_names.push("invented")'),
    ("app/wrapper.js", '"minimist"', '"fake-minimist"'),
    ("app/wrapper.js", '[, bound_value]', '[bound_value]'),
    ("app/context.js", 'bound_next.value = ""', 'bound_next.value = ","'),
    ("app/state.js", 'async init()', 'async *init()'),
    ("lib/api.js", 'wrap(supportInfo,0)', 'wrap(other,0)'),
    ("app/context.js", 'normalizeSettings(declarations)', 'unrelated(declarations)'),
    ("app/context.js", 'dash(bound_option.name)', 'other(bound_option.name)'),
    ("app/context.js", 'dash(bound_option.name)', 'dash(bound_option.description)'),
    ("lib/support.js", '...bound_original', '...unrelated'),
    ("lib/support.js", 'core)', 'unknown)'),
    ("lib/support.js", 'new Set', 'new MutableSet'),
    ("lib/values.js", 'schema.validate', 'schema.other'),
    ("lib/values.js", '"vnopts"', '"unproven-vnopts"'),
    ("lib/values.js", 'name: "_"', 'name: "not_positional"'),
])
def test_mutated_dataflow_cannot_emit_parameters(tmp_path, filename, before, after):
    files = repository(tmp_path)
    if filename == "lib/values.js" and before == 'schema.validate':
        before, after = 'bound_schema.validate', 'bound_schema.other'
    assert before in files[filename]
    (tmp_path / filename).write_text(files[filename].replace(before, after))
    assert not any(item.predicate in {"supports_option", "supports_argument"} for item in discover(tmp_path).claims)


@pytest.mark.parametrize("value", ["file:../fake", "workspace:*", "npm:fake@1", "https://example.invalid/archive", ""])
def test_non_registry_framework_dependencies_do_not_define_semantics(tmp_path, value):
    repository(tmp_path)
    manifest = json.loads((tmp_path / "package.json").read_text())
    manifest["dependencies"]["minimist"] = value
    (tmp_path / "package.json").write_text(json.dumps(manifest))
    assert not any(item.predicate == "supports_option" for item in discover(tmp_path).claims)


def test_custom_exception_keeps_parameter_unbindable(tmp_path):
    files = repository(tmp_path)
    path = tmp_path / "app/declarations.js"
    path.write_text(files["app/declarations.js"].replace("value===false", "arbitrary(value)"))
    discovery = discover(tmp_path)
    request = InvocationRequest(command="sample", parameters={"--config": ["style.json"]}, expected_observation="Configuration applied")
    with pytest.raises(ValueError, match="PARAMETER_SEMANTICS_UNKNOWN"):
        bind_invocation(discovery.claims, request, "user_input")


def test_unrelated_entry_import_does_not_reach_declarative_parameters(tmp_path):
    repository(tmp_path)
    (tmp_path / "entry.cjs").write_text('import "./app/start.js";')
    assert not any(item.predicate == "supports_option" for item in discover(tmp_path).claims)


def test_alias_collisions_do_not_choose_an_arbitrary_owner(tmp_path):
    files = repository(tmp_path)
    path = tmp_path / "lib/core.js"
    path.write_text(files["lib/core.js"].replace('cliName:"stdin-name"', 'cliName:"config"'))
    discovery = discover(tmp_path)
    assert not any(item.predicate == "supports_option" for item in discovery.claims)
    assert any(item.code == "JS_OPTION_FLOW_ALIAS_COLLISION" for item in discovery.findings)


def test_updating_unrelated_context_field_does_not_rebind_the_context(tmp_path):
    files = repository(tmp_path)
    path = tmp_path / "app/start.js"
    path.write_text(files["app/start.js"].replace('await context.init()', 'context.logger={}; await context.init()'))
    assert any(item.object.get("option") == "--engine" for item in discover(tmp_path).claims)


def test_changed_literal_table_does_not_reuse_stale_symbol_cache(tmp_path):
    files = repository(tmp_path)
    first = discover(tmp_path)
    path = tmp_path / "lib/core.js"
    path.write_text(files["lib/core.js"].replace('value:"csv"', 'value:"xml"'))
    second = discover(tmp_path)
    before = next(item for item in first.claims if item.object.get("option") == "--engine")
    after = next(item for item in second.claims if item.object.get("option") == "--engine")
    assert before.object["semantics"]["choices"] == ("json", "csv")
    assert after.object["semantics"]["choices"] == ("json", "xml")
    assert before.evidence_ids != after.evidence_ids
