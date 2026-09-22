import json

import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery

pytest.importorskip("tree_sitter")


def test_commander_import_binding_and_positionals(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "bin": "cli.js"}))
    (tmp_path / "cli.js").write_text('''import {Command as CLI} from "commander";
const program = new CLI();
program.argument("<files...>", "Input files");
program.option("-w, --write", "Write output");
program.requiredOption("--output <file>", "Output path");
database.option("--fake", "Not a CLI");
program.parse();
program.option("--late", "Unreachable for this parse");
''')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    assert {claim.object.get("option") for claim in discovery.claims if claim.predicate == "supports_option"} == {"-w", "--write", "--output"}
    positionals = [claim for claim in discovery.claims if claim.predicate == "supports_argument"]
    assert positionals[0].object.get("argument") == "files"
    assert positionals[0].object.get("shape", {}).get("arity") == "+"


def test_go_switch_requires_arguments_from_reachable_entrypoint(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "go.mod").write_text("module example.org/demo\n")
    (tmp_path / "main.go").write_text('''package main
import "os"
func main(){ parse(os.Args[1:]) }
func parse(args []string){
 for index:=0; index<len(args); index++ {
  arg:=args[index]
  switch arg { case "--exact": exact=true; case "--dynamic": configure(); case "--no-sort": opts.Sort=0; case "--advance": index=1; case "--consume": opts.Sort=0; index++ }
 }
}
func unused(args []string){ for index:=0; index<len(args); index++ { arg:=args[index]; switch arg {case "--fake": exact=true} } }
''')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    options = {claim.object.get("option"): claim.object.get("shape") for claim in discovery.claims if claim.predicate == "supports_option"}
    assert options["--exact"]["arity"] == 0
    assert options["--dynamic"]["arity"] == "unknown"
    assert options["--no-sort"]["arity"] == 0
    assert options["--advance"]["arity"] == "unknown"
    assert options["--consume"]["arity"] == "unknown"
    assert "--fake" not in options


def test_javascript_option_tables_require_real_normalization_not_comment(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "bin": "cli.js"}))
    (tmp_path / "cli.js").write_text('''import options from "./options.js";
// name: option.cliName ?? dashify(option.name)
normalizeOptionSettings(options);
''')
    (tmp_path / "options.js").write_text('const options={imaginary:{type:"boolean"}}; export default options;')
    discovery = discover(tmp_path)
    assert not any(claim.predicate == "supports_option" for claim in discovery.claims)


def test_disconnected_normalizer_cannot_invent_supported_options(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "package.json").write_text(json.dumps({"name": "demo", "bin": "cli.js"}))
    (tmp_path / "cli.js").write_text('''import options from "./options.js";
normalizeOptionSettings(options);
function normalizeDetailedOption(option){return {name: option.cliName ?? dashify(option.name)}}
''')
    (tmp_path / "options.js").write_text('const options={format:{type:"choice",choices:[{value:"json"},{value:"csv"}]}}; export default options;')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    assert not any(claim.predicate == "supports_option" for claim in discovery.claims)


def test_conflicting_entrypoints_cannot_leave_supported_child_parameters(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    for workspace in ("first", "second"):
        root = tmp_path / workspace
        root.mkdir()
        (root / "package.json").write_text(json.dumps({"name": "demo", "bin": "cli.js"}))
        (root / "cli.js").write_text('import {Command} from "commander"; const cli=new Command(); cli.option("--output <path>"); cli.argument("<source>"); cli.parse();')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    assert not discovery.commands
    interfaces = [claim for claim in discovery.claims if claim.predicate in {"provides_cli", "supports_argument", "supports_option"}]
    assert interfaces and all(claim.status == "conflicted" for claim in interfaces)
    assert any(finding.code == "COMMAND_CONFLICT" for finding in discovery.findings)
