import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.workflows import InvocationRequest, bind_invocation

pytest.importorskip("tree_sitter_go")


def test_cobra_children_remain_scoped_and_conditional_registration_unknown(tmp_path):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "go.mod").write_text("module example.org/demo\n")
    (tmp_path / "main.go").write_text('''package main
import "github.com/spf13/cobra"
func main(){ root := newRoot(); root.Execute() }
func newRoot() *cobra.Command {
 cmd := &cobra.Command{Use: "demo"}
 cmd.AddCommand(newExport())
 if enabled { cmd.AddCommand(newHidden()) }
 cmd.PersistentFlags().Bool("verbose", false, "Verbose")
 return cmd
}
func newExport() *cobra.Command {
 cmd := &cobra.Command{Use: "export"}
 cmd.Flags().String("output", "", "Output")
 cmd.MarkFlagRequired("output")
 return cmd
}
func newHidden() *cobra.Command {
 cmd := &cobra.Command{Use: "hidden"}
 return cmd
}
''')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    assert {item.path for item in discovery.commands} == {(), ("export",)}
    output = next(claim for claim in discovery.claims if claim.object.get("option") == "--output")
    assert output.object.get("command_path") == ("export",)
    assert output.object.get("shape", {}).get("required") is True
    assert output.object.get("semantics", {}).get("default") == ""
    assert output.object.get("semantics", {}).get("value_type") == "str"
    assert output.id not in next(item for item in discovery.commands if not item.path).option_claim_ids


@pytest.mark.parametrize(("use", "validator", "accepted"), [
    ("set <key> <value>", "cli.ExactArgs(2)", True),
    ("set <key> <value>", "cli.ExactArgs(1)", False),
    ("set <key> <value>", "other.ExactArgs(2)", False),
    ("set -s <shell>", "cli.ExactArgs(2)", False),
    ("set [<key>]", "cli.ExactArgs(1)", False),
    ("set <key> <key>", "cli.ExactArgs(2)", False),
    ("set <key>", "checkArgs", False),
])
def test_positionals_require_matching_cobra_validator(tmp_path, use, validator, accepted):
    (tmp_path / "LICENSE").write_text("MIT")
    (tmp_path / "go.mod").write_text("module example.org/demo\n")
    (tmp_path / "main.go").write_text('''package main
import cli "github.com/spf13/cobra"
func main(){ root := newRoot(); root.Execute() }
func newRoot() *cli.Command {
 cmd := &cli.Command{Use: "demo"}
 cmd.AddCommand(newSet())
 return cmd
}
func newSet() *cli.Command {
 cmd := &cli.Command{Use: "''' + use + '''", Args: ''' + validator + '''}
 return cmd
}
''')
    discovery = parse_discovery(discover(tmp_path).to_dict())
    arguments = [claim for claim in discovery.claims if claim.predicate == "supports_argument"]
    assert bool(arguments) is accepted
    if not accepted:
        return
    request = InvocationRequest(command="demo", path=["set"], parameters={"value": ["hello world"], "key": ["message"]}, expected_observation="Value saved")
    step = bind_invocation(discovery.claims, request, "user_input")
    assert step.arguments == ("set", "message", "hello world")
    assert all(claim.object.get("command_path") == ("set",) for claim in arguments)
    with pytest.raises(ValueError, match="PARAMETER_REQUIRED"):
        bind_invocation(discovery.claims, request.model_copy(update={"parameters": {"key": ["message"]}}), "user_input")
    code = (tmp_path / "main.go").read_text()
    (tmp_path / "main.go").write_text(code.replace('Args: cli.ExactArgs(2)}', 'Args: cli.ExactArgs(2)}\n cmd.Args = cli.NoArgs'))
    assert not any(claim.predicate == "supports_argument" for claim in discover(tmp_path).claims)
