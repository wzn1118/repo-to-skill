from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(python: Path, work: Path, wheel: Path) -> dict:
    work.mkdir(parents=True, exist_ok=False)
    environment = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    environment["PYTHONNOUSERSITE"] = "1"
    records = []

    def invoke(arguments: list[str], allowed: tuple[int, ...] = (0,)) -> str:
        process = subprocess.run(
            [str(python), "-I", *arguments], cwd=work, env=environment,
            capture_output=True, text=True, timeout=60, check=False,
        )
        if process.returncode not in allowed:
            raise ValueError(f"WHEEL_CHECK_FAILED: {arguments[:3]}: {process.returncode}: {process.stderr[:1000]}")
        return process.stdout

    def cli(name: str, arguments: list[str], allowed: tuple[int, ...] = (0,)) -> str:
        output = invoke(["-m", "r2s", *arguments], allowed)
        records.append(name)
        return output

    origin = json.loads(invoke(["-c", "import json, pathlib, r2s, sys; print(json.dumps({'package': r2s.__file__, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))"]))
    package = Path(origin["package"]).resolve()
    prefix = Path(origin["prefix"]).resolve()
    configuration = (prefix / "pyvenv.cfg").read_text().lower()
    if prefix == Path(origin["base_prefix"]).resolve() or not package.is_relative_to(prefix) or "include-system-site-packages = false" not in configuration:
        raise ValueError("WHEEL_PACKAGE_NOT_FROM_ISOLATED_VENV")
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            if entry.filename.startswith("r2s/") and not entry.is_dir():
                installed = package.parent.parent / entry.filename
                if not installed.resolve().is_relative_to(prefix) or installed.read_bytes() != archive.read(entry):
                    raise ValueError("WHEEL_INSTALLED_CONTENT_MISMATCH")
    dependencies = json.loads(invoke(["-c", "import importlib.metadata as metadata, json; print(json.dumps({item.metadata['Name']: item.version for item in metadata.distributions()}))"]))
    fixture = ROOT / "tests/fixtures/python_cli"
    version = cli("version", ["--version"]).strip()
    inspected = json.loads(cli("inspect + scan scope", ["inspect", str(fixture), "--output", str(work / "runs"), "--json"]))
    assert inspected["capabilities"] == 1 and inspected["scan"]["complete_within_policy"]
    run = Path(inspected["run_root"])
    built = json.loads(cli("build codex", ["build", str(run), "--goal", "use demo", "--target", "codex", "--output", str(work / "runs")]))
    assert built["readiness"] == "STATIC_READY"
    plugin = Path(built["root"])
    validated = json.loads(cli("validate", ["validate", str(plugin)]))
    assert validated["readiness"] == "STATIC_READY" and not validated["findings"]
    cli("install preview", ["install", str(plugin), "--destination", str(work / "installation")])
    assert not (work / "installation").exists()
    schema = json.loads(cli("schema equality", ["schema", "export"]))
    assert schema == json.loads((ROOT / "schemas/discovery.schema.json").read_text())
    cli("migrate", ["migrate", str(run / "discovery.json"), "--output", str(work / "migrated")])
    report = {
        "format": "r2s-wheel-verification-v1", "status": "passed", "version": version,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "package_import": "wheel contents match installed package inside virtualenv; isolated Python mode; system site-packages disabled",
        "dependency_mode": "virtualenv dependencies; installation method must be recorded by the caller",
        "dependencies": dependencies, "checks": records,
        "scope": "controlled fixture CLI checks on Linux; not target repository execution or native client loading",
    }
    (work / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    verify(args.python.absolute(), args.work.resolve(), args.wheel.resolve())


if __name__ == "__main__":
    main()
