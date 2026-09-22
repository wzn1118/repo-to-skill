import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from semantic_gold import (
    Assertion,
    Citation,
    Gold,
    Repository,
    check_assertion,
    citation,
    evaluate,
    strict_load,
    verify_sources,
)


def test_gold_requires_operational_fields_for_positive_options(tmp_path):
    with pytest.raises(ValueError, match="GOLD_OPERATIONAL_FIELDS_REQUIRED"):
        Assertion(id="a", kind="option", command="tool", command_path=[], name="--x", citations=[Citation(path="main.py", start_line=1, end_line=1, content_sha256="a" * 64, range_sha256="b" * 64)], rationale="long enough rationale")


def test_alias_claims_are_one_semantic_subject():
    assertion = Assertion(
        id="alias",
        kind="option",
        command="tool",
        command_path=[],
        name="--format",
        fields={"shape.arity": 1},
        citations=[Citation(path="main.py", start_line=1, end_line=1, content_sha256="a" * 64, range_sha256="b" * 64)],
        rationale="The long and short spellings share one declaration.",
    )
    common = {"command": "tool", "command_path": [], "shape": {"arity": 1, "aliases": ["-f", "--format"], "unknown_reasons": []}}
    facts = [
        {"id": "short", "emitted": True, "predicate": "supports_option", "status": "supported", "value": {**common, "option": "-f"}},
        {"id": "long", "emitted": True, "predicate": "supports_option", "status": "supported", "value": {**common, "option": "--format"}},
    ]
    assert check_assertion(assertion, facts)["status"] == "SELECTED_FIELDS_MATCH"


def test_strict_json_rejects_duplicates_and_nonfinite_values(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"value": 1, "value": 2}')
    with pytest.raises(ValueError, match="GOLD_DUPLICATE_JSON_KEY"):
        strict_load(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value": NaN}')
    with pytest.raises(ValueError, match="GOLD_NONFINITE_JSON"):
        strict_load(nonfinite)


def test_evaluation_requires_completed_measurement_marker():
    assertion = Assertion(
        id="negative",
        kind="option",
        command="tool",
        command_path=[],
        name="--missing",
        expectation="absent",
        citations=[Citation(path="main.py", start_line=1, end_line=1, content_sha256="a" * 64, range_sha256="b" * 64)],
        rationale="The selected source does not declare this option.",
    )
    gold = Gold(
        format="r2s-semantic-gold-v1",
        metadata_sha256="b" * 64,
        review_method="test",
        tuning_scope="test",
        repositories=[Repository(id="tool", repository="example/tool", commit_sha="a" * 40, assertions=[assertion])],
    )
    results = {"compiler_sha256": "c" * 64, "metadata_sha256": "b" * 64, "repositories": [{"id": "tool", "repository": "example/tool", "commit_sha": "a" * 40}]}
    with pytest.raises(ValueError, match="GOLD_RESULT_COMPLETION_INVALID"):
        evaluate(gold, results)


def test_gold_pins_source_bytes_and_evaluates_missing_unknown_and_negative(tmp_path):
    cached = tmp_path / ("tool-" + "a" * 40)
    source = cached / "source"
    source.mkdir(parents=True)
    content = 'parser.add_argument("--format", choices=["json", "csv"])\n'
    path = source / "main.py"
    path.write_text(content)
    digest = hashlib.sha256(content.encode()).hexdigest()
    lock = cached / "source.lock.json"
    lock.write_text(json.dumps({"repository": "example/tool", "commit_sha": "a" * 40, "files": {"main.py": {"sha256": digest}}}))
    positive = Assertion(id="positive", kind="option", command="tool", command_path=[], name="--format", fields={"semantics.choices": ["json", "csv"]}, citations=[citation(source, "main.py", "parser.add_argument", 1)], rationale="The parser declares these output formats.")
    negative = Assertion(id="negative", kind="option", command="tool", command_path=[], name="--missing", expectation="absent", citations=[citation(source, "main.py", "parser.add_argument", 1)], rationale="The selected parser has no missing flag.")
    repo = Repository(id="tool", repository="example/tool", commit_sha="a" * 40, assertions=[positive, negative])
    gold = Gold(format="r2s-semantic-gold-v1", metadata_sha256="b" * 64, review_method="manual", tuning_scope="fixed", repositories=[repo])
    verify_sources(gold, tmp_path)
    results = {"compiler_sha256": "c" * 64, "metadata_sha256": "b" * 64, "repositories": [{"id": "tool", "repository": "example/tool", "commit_sha": "a" * 40, "completed": True, "compiler_sha256": "c" * 64, "facts": [{"id": "claim", "emitted": True, "predicate": "supports_option", "status": "supported", "value": {"command": "tool", "option": "--format", "command_path": [], "semantics": {"choices": ["json"]}, "shape": {"unknown_reasons": []}}}]}]}
    report = evaluate(gold, results)
    assert report["counts"] == {"FIELD_MISMATCH": 1, "NEGATIVE_CLEAR": 1}
    assert report["field_counts"] == {"MISMATCH": 1}
