from __future__ import annotations

import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from public_sources import digest


def fingerprint(root: Path) -> dict:
    compiler = {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted((root / "src/r2s").rglob("*")) if path.is_file() and path.suffix == ".py"
    }
    harness = {
        f"scripts/{name}": digest(root / "scripts" / name)
        for name in ("public_measure.py", "public_sources.py", "measurement_identity.py")
    }
    dependencies = {}
    for name in ("pydantic", "pydantic-core", "PyYAML", "jinja2"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return {
        "compiler_files": compiler,
        "compiler_sha256": hashlib.sha256(json.dumps(compiler, sort_keys=True).encode()).hexdigest(),
        "harness_files": harness,
        "dependencies": dependencies,
    }


def require_identity(root: Path, expected: dict) -> None:
    if fingerprint(root) != expected:
        raise ValueError("MEASUREMENT_CODE_CHANGED")


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
