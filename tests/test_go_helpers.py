from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.workflows import InvocationRequest, bind_invocation

pytest.importorskip("tree_sitter_go")

HELPER = '''package flags
import (
 "fmt"
 "strings"
 cli "github.com/spf13/cobra"
 "github.com/spf13/pflag"
)
func Register(command *cli.Command, destination *string, label, short, fallback string, allowed []string, help string) *pflag.Flag {
 *destination = fallback
 value := &Choice{storage:destination, allowed:allowed}
 flag := command.Flags().VarPF(value, label, short, help)
 _ = command.RegisterFlagCompletionFunc(label, func(command *cli.Command, args []string, prefix string) ([]string, cli.ShellCompDirective) {
  return allowed, cli.ShellCompDirectiveNoFileComp
 })
 return flag
}
type Choice struct {storage *string; allowed []string}
func (receiver *Choice) Set(input string) error {
 if !contains(input, receiver.allowed) { return fmt.Errorf("expected %s", format(receiver.allowed)) }
 *receiver.storage = input
 return nil
}
func (receiver *Choice) String() string {return *receiver.storage}
func (receiver *Choice) Type() string {return "string"}
func contains(input string, allowed []string) bool {
 for _, item := range allowed { if strings.EqualFold(item,input) { return true } }
 return false
}
func format(allowed []string) string { return fmt.Sprintf("{%s}", strings.Join(allowed, "|")) }
'''


def repository(root: Path, helper: str = HELPER, invocation: str = 'flags.Register(cmd, &output, "format", "f", "json", []string{"json","csv"}, "Output format")') -> None:
    (root / "LICENSE").write_text("MIT")
    (root / "go.mod").write_text("module example.org/demo\n")
    (root / "main.go").write_text('''package main
import (
 "github.com/spf13/cobra"
 "example.org/demo/flags"
)
func main(){cmd:=newRoot(); cmd.Execute()}
func newRoot() *cobra.Command {
 cmd:=&cobra.Command{Use:"demo"}
 cmd.AddCommand(newExport())
 return cmd
}
func newExport() *cobra.Command {
 var output string
 cmd:=&cobra.Command{Use:"export"}
 ''' + invocation + '''
 return cmd
}
''')
    (root / "flags").mkdir()
    (root / "flags/options.go").write_text(helper)


def test_local_enum_helper_binds_literal_values_and_retains_validation_chain(tmp_path):
    repository(tmp_path)
    discovery = parse_discovery(discover(tmp_path).to_dict())
    claim = next(item for item in discovery.claims if item.object.get("option") == "--format")
    assert claim.object.get("command_path") == ("export",)
    assert claim.object["semantics"]["choices"] == ("json", "csv")
    sources = [item for item in discovery.evidence if item.id in claim.evidence_ids and item.kind == "go.enum_validation"]
    assert {item.normalized_value["symbol"] for item in sources} == {"Register", "Choice", "Set", "String", "Type", "contains", "format"}
    assert all(item.source.end_line >= item.source.start_line for item in sources)
    request = InvocationRequest(command="demo", path=["export"], parameters={"--format": ["csv"]}, expected_observation="CSV content")
    assert bind_invocation(discovery.claims, request, "user_input").arguments == ("export", "--format", "csv")
    with pytest.raises(ValueError, match="PARAMETER_CHOICE_MISMATCH"):
        bind_invocation(discovery.claims, request.model_copy(update={"parameters": {"--format": ["xml"]}}), "user_input")
    assert bind_invocation(discovery.claims, request.model_copy(update={"parameters": {"--format": ["CSV"]}}), "user_input").arguments[-1] == "CSV"
    with pytest.raises(ValueError, match="PARAMETER_CHOICE_ALPHABET_UNSUPPORTED"):
        bind_invocation(discovery.claims, request.model_copy(update={"parameters": {"--format": ["cſv"]}}), "user_input")


def test_method_in_another_file_prevents_assuming_value_arity(tmp_path):
    repository(tmp_path)
    (tmp_path / "flags/bool.go").write_text('package flags\nfunc (receiver *Choice) IsBoolFlag() bool {return true}\n')
    assert not any(item.object.get("option") == "--format" for item in discover(tmp_path).claims)


def test_enum_helper_keeps_required_flag_binding(tmp_path):
    repository(tmp_path, invocation='flags.Register(cmd, &output, "format", "f", "json", []string{"json","csv"}, "Format"); cmd.MarkFlagRequired("format")')
    discovery = discover(tmp_path)
    claim = next(item for item in discovery.claims if item.object.get("option") == "--format")
    assert any(item.kind == "go.required_flag" and item.id in claim.evidence_ids for item in discovery.evidence)
    request = InvocationRequest(command="demo", path=["export"], parameters={}, expected_observation="CSV content")
    with pytest.raises(ValueError, match="PARAMETER_REQUIRED"):
        bind_invocation(discovery.claims, request, "user_input")


def test_three_competing_function_definitions_do_not_restore_a_binding(tmp_path):
    repository(tmp_path, HELPER + '\nfunc contains(input string, allowed []string) bool {return true}\nfunc contains(input string, allowed []string) bool {return true}\n')
    assert not any(item.object.get("option") == "--format" for item in discover(tmp_path).claims)


@pytest.mark.parametrize(("before", "after"), [
    ('*receiver.storage = input', '*receiver.storage = "forced"'),
    ('return nil', 'configure(); return nil'),
    ('strings.EqualFold(item,input)', 'customCheck(item,input)'),
    ('return "string"', 'return "bool"'),
    ('command.Flags().VarPF', 'other.Flags().VarPF'),
    ('return flag', 'flag.NoOptDefVal="yes"; return flag'),
    ('"github.com/spf13/cobra"', '"example.org/fake/cobra"'),
    ('type Choice struct', 'func (receiver *Choice) IsBoolFlag() bool {return true}\ntype Choice struct'),
    ('type Choice struct', 'func (receiver Choice) IsBoolFlag() bool {return true}\ntype Choice struct'),
])
def test_unknown_or_mutated_helper_cannot_supply_supported_option(tmp_path, before, after):
    repository(tmp_path, HELPER.replace(before, after))
    assert not any(item.object.get("option") == "--format" for item in discover(tmp_path).claims)


@pytest.mark.parametrize("invocation", [
    'flags.Register(other, &output, "format", "f", "json", []string{"json"}, "Format")',
    'flags.Register(cmd, &output, "format", "f", "json", choices(), "Format")',
    'if enabled { flags.Register(cmd, &output, "format", "f", "json", []string{"json"}, "Format") }',
])
def test_enum_requires_literal_choices_correct_owner_and_unconditional_call(tmp_path, invocation):
    repository(tmp_path, invocation=invocation)
    assert not any(item.object.get("option") == "--format" for item in discover(tmp_path).claims)
