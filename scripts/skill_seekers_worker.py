from __future__ import annotations

import hashlib
import json
from pathlib import Path

from skill_seekers.cli.codebase_scraper import analyze_codebase


def main() -> None:
    output = Path("/tmp/generated")
    analyze_codebase(directory=Path("/source"), output_dir=output, depth="deep", enhance_level=0, skill_name="evaluated-tool")
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and not path.is_symlink():
            contents = path.read_bytes()
            files[path.relative_to(output).as_posix()] = {"bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
    record = {"status": "GENERATED" if (output / "SKILL.md").is_file() else "NO_SKILL", "files": files,
              "skill_markdown": (output / "SKILL.md").read_text() if (output / "SKILL.md").is_file() else None}
    print("R2S_RESULT=" + json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
