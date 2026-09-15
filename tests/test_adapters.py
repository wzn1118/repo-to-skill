from pathlib import Path

from r2s.adapters import adapt_portable_skills
from r2s.analyzers import discover
from r2s.generator import generate


def test_client_adapters_reuse_portable_skills(tmp_path: Path) -> None:
    discovery = discover(Path(__file__).parent / "fixtures/python_cli")
    result = generate(discovery, "inspect options", tmp_path / "build", "portable")
    bundles, findings = adapt_portable_skills(
        Path(result.bundles[0]).parent, tmp_path / "adapters", "claude", "portable-agent-skills-v1",
    )
    assert not findings
    assert len(bundles) == 1
    assert (tmp_path / "adapters/claude/skills/demo/SKILL.md").is_file()
    assert (tmp_path / "adapters/claude/adapter.json").is_file()
