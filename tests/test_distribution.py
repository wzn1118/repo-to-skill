import json
from pathlib import Path
from unittest.mock import patch

from r2s.analyzers import discover
from r2s.bundle_validation import bundle_digest, inventory
from r2s.distribution import install_plugin, rollback_plugin
from r2s.generator import generate


def plugin(tmp_path: Path, name: str, goal: str) -> Path:
    source = Path(__file__).parent / "fixtures/multi_cli"
    result = generate(discover(source), goal, tmp_path / name, "codex")
    assert result.root is not None
    return Path(result.root)


def test_update_and_rollback_restore_managed_bundle(tmp_path: Path) -> None:
    first = plugin(tmp_path, "first", "use alpha")
    second = plugin(tmp_path, "second", "use beta")
    destination = tmp_path / "installed"
    target, findings, _ = install_plugin(first, destination, execute=True)
    assert target is not None and not findings
    first_digest = bundle_digest(inventory(target)[0])
    _, findings, _ = install_plugin(second, destination, execute=True)
    assert findings[0].code == "INSTALL_REQUIRES_UPDATE"
    _, findings, _ = install_plugin(second, destination, execute=True, update=True)
    assert not findings
    assert (target / "skills/beta/SKILL.md").is_file()
    assert not (target / "skills/alpha").exists()
    _, findings, _ = rollback_plugin(destination, target.name, first_digest, execute=True)
    assert not findings
    assert bundle_digest(inventory(target)[0]) == first_digest


def test_receipt_failure_restores_old_installation(tmp_path: Path) -> None:
    from r2s.distribution import _write_json

    first = plugin(tmp_path, "first", "use alpha")
    second = plugin(tmp_path, "second", "use beta")
    destination = tmp_path / "installed"
    target, findings, _ = install_plugin(first, destination, execute=True)
    assert target is not None and not findings
    before = inventory(target)[0]
    receipt = destination / ".r2s" / f"{target.name}.json"
    original_receipt = receipt.read_bytes()

    def fail_receipt(path: Path, value: dict) -> None:
        if path == receipt:
            raise OSError("simulated disk failure")
        _write_json(path, value)

    with patch("r2s.distribution._write_json", side_effect=fail_receipt):
        _, findings, _ = install_plugin(second, destination, execute=True, update=True)
    assert findings[0].code == "INSTALL_IO_FAILED"
    assert inventory(target)[0] == before
    assert receipt.read_bytes() == original_receipt
    assert not list((destination / ".r2s").glob("*.transaction.json"))


def test_receipt_does_not_trust_modified_or_unmanaged_files(tmp_path: Path) -> None:
    first = plugin(tmp_path, "first", "use alpha")
    destination = tmp_path / "installed"
    target, findings, _ = install_plugin(first, destination, execute=True)
    assert target is not None and not findings
    receipt = json.loads((destination / ".r2s" / f"{target.name}.json").read_bytes())
    assert receipt["source_authenticity"] == "not_independently_authenticated"
    (target / "notes.md").write_text("User content")
    _, findings, _ = install_plugin(first, destination, execute=True, update=True)
    assert findings[0].code == "INSTALL_USER_MODIFIED"
    assert (target / "notes.md").read_text() == "User content"
