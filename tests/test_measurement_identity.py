import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import public_measure
from measurement_identity import fingerprint, require_identity
from public_sources import write_json


def test_changed_compiler_cannot_be_published_as_measured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "compiler"
    (project / "src/r2s").mkdir(parents=True)
    (project / "scripts").mkdir()
    source = project / "src/r2s/core.py"
    source.write_text("version = 1")
    for name in ("public_measure.py", "public_sources.py", "measurement_identity.py"):
        (project / "scripts" / name).write_text("pass")
    expected = fingerprint(project)
    require_identity(project, expected)
    metadata = tmp_path / "metadata.json"
    write_json(metadata, {"repositories": [{"id": "sample"}]})
    monkeypatch.setattr(public_measure, "ROOT", project)

    def mutate(record: dict, work: Path, timeout: int, identity: dict) -> dict:
        source.write_text("version = 2")
        return {"id": "sample", "status": "STATIC_READY"}

    monkeypatch.setattr(public_measure, "measure", mutate)
    output = tmp_path / "report.json"
    with pytest.raises(ValueError, match="MEASUREMENT_CODE_CHANGED"):
        public_measure.run(metadata, tmp_path / "work", output, 30)
    assert not output.exists()
    with pytest.raises(ValueError, match="MEASUREMENT_INCOMPLETE"):
        public_measure.collect(metadata, tmp_path / "work", output)


def test_existing_measurement_cannot_be_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text('{"historical": true}')
    with pytest.raises(ValueError, match="MEASUREMENT_OUTPUT_EXISTS"):
        public_measure.run(tmp_path / "missing-metadata.json", tmp_path / "work", output, 30)
    assert json.loads(output.read_text()) == {"historical": True}


@pytest.mark.parametrize("script", ["public_evaluate", "public_fact_audit", "render_run_report", "create_run_manifest"])
def test_finalized_evaluation_cannot_be_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    files = {"manifest.json": b'{"sealed": true}', "ground-truth-results.json": b'{"historical": true}', "report.md": b'historical report'}
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    arguments = {
        "public_evaluate": ["--work", str(tmp_path), "--output-dir", str(tmp_path)],
        "public_fact_audit": ["--work", str(tmp_path), "--output", str(tmp_path / "fact-audit.json")],
        "render_run_report": ["--run", str(tmp_path)],
        "create_run_manifest": ["--run", str(tmp_path)],
    }
    monkeypatch.setattr(sys, "argv", [script, *arguments[script]])
    with pytest.raises(ValueError, match="OUTPUT_EXISTS|RUN_FINALIZED"):
        importlib.import_module(script).main()
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == files
