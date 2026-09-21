import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery

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
