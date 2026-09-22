import pytest

from r2s.javascript_patterns import function_match

pytest.importorskip("tree_sitter_javascript")


@pytest.mark.parametrize(("expected", "actual", "accepted"), [
    ('return "";', 'return ",";', False),
    ('return "";', 'return ";";', False),
    ('return ",";', 'return ";";', False),
    ('const [, __value] = source;', 'const [value] = source;', False),
    ('const [__value, ,] = source;', 'const [value] = source;', False),
    ('const [__value, ,] = source;', 'const [value, /* hole */ ,] = source;', True),
    ('return [1, 2];', 'return [1, 2,];', True),
    ('return [1, 2];', 'return [1, , 2];', False),
    ('return [1, 2];', 'return [1, 2, ,];', False),
])
def test_only_syntactic_delimiters_are_optional(expected, actual, accepted):
    from r2s.javascript_patterns import template

    assert (function_match(f'function expected() {{{expected}}}', template(f'function actual() {{{actual}}}')) is not None) is accepted
