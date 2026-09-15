import ast

import pytest

from r2s.python_bindings import bound_option_calls


@pytest.mark.parametrize(("source", "expected"), [
    ("import argparse as ap\ndef main():\n p = ap.ArgumentParser()\n p.add_argument('--ok')", {"--ok"}),
    ("from argparse import ArgumentParser as Parser\ndef main():\n p = Parser()\n p.add_argument('--ok')", {"--ok"}),
    ("from click import option as opt\n@opt('--ok')\ndef main(): pass", {"--ok"}),
    ("import typer as ty\ndef main(value = ty.Option(None, '--ok')): pass", {"--ok"}),
    ("import argparse\ndef main():\n p = argparse.ArgumentParser()\n p = database\n p.add_argument('--fake')", set()),
    ("import argparse\ndef other():\n p = argparse.ArgumentParser()\ndef main():\n p.add_argument('--fake')", set()),
    ("import argparse\ndef main(argparse):\n p = argparse.ArgumentParser()\n p.add_argument('--fake')", set()),
    ("import argparse\ndef main():\n p = argparse.ArgumentParser()\n def unrelated():\n  p.add_argument('--fake')", set()),
    ("import argparse\ndef main():\n p = argparse.ArgumentParser()\n g = p.add_argument_group('group')\n g.add_argument('--ok')", {"--ok"}),
    ("import argparse\np = argparse.ArgumentParser()\np.add_argument('--ok')\ndef main():\n p.parse_args()", {"--ok"}),
    ("import argparse\np = argparse.ArgumentParser()\np.add_argument('--fake')\ndef main(): pass", set()),
    ("from database import option\n@option('--fake')\ndef main(): pass", set()),
])
def test_framework_and_owner_binding(source: str, expected: set[str]) -> None:
    tree = ast.parse(source)
    scope = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    flags = {
        argument.value for call in bound_option_calls(tree, scope) for argument in call.args
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        and argument.value.startswith("-")
    }
    assert flags == expected
