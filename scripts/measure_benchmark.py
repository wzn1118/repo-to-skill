from __future__ import annotations

import html
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "benchmark.svg"


@dataclass(frozen=True)
class FixtureResult:
    name: str
    languages: tuple[str, ...]
    capabilities: int
    claims: int
    evidence: int
    findings: int
    readiness: str
    bundles: int


def _measure_fixture(fixture: Path) -> FixtureResult:
    from r2s.core import discover
    from r2s.generator import generate

    discovery = discover(fixture)
    with TemporaryDirectory() as output:
        build = generate(discovery, "use the discovered command", Path(output), "portable")
    return FixtureResult(
        name=fixture.name,
        languages=tuple(discovery.languages),
        capabilities=len(discovery.capabilities),
        claims=len(discovery.claims),
        evidence=len(discovery.evidence),
        findings=len(discovery.findings),
        readiness=build.readiness.value,
        bundles=len(build.bundles),
    )


def _measure() -> tuple[FixtureResult, ...]:
    fixture_root = ROOT / "tests" / "fixtures"
    fixtures = sorted(path for path in fixture_root.iterdir() if path.is_dir())
    return tuple(_measure_fixture(fixture) for fixture in fixtures)


def _test_case_count() -> int:
    return sum(
        1
        for path in (ROOT / "tests").glob("test_*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("def test_")
    )


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _text(x: int, y: int, value: object, class_name: str = "body") -> str:
    return f'<text x="{x}" y="{y}" class="{class_name}">{_escape(value)}</text>'


def _bar_row(
    x: int,
    y: int,
    label: str,
    value: int,
    maximum: int,
    color: str,
    width: int = 350,
    value_x: int | None = None,
) -> str:
    bar_width = 0 if maximum == 0 else max(4, round(width * value / maximum))
    number_x = x + 512 if value_x is None else value_x
    return "".join(
        (
            _text(x, y, label, "body"),
            f'<rect x="{x + 142}" y="{y - 15}" width="{width}" height="18" rx="9" '
            + 'fill="#263449"/>',
            f'<rect x="{x + 142}" y="{y - 15}" width="{bar_width}" height="18" rx="9" '
            + f'fill="{color}"/>',
            _text(number_x, y, value, "number"),
        )
    )


def _render_svg(results: tuple[FixtureResult, ...]) -> str:
    readiness_labels = {
        "STATIC_READY": ("Static ready", "#49d17d"),
        "REVIEW_REQUIRED": ("Review required", "#f5b84b"),
        "UNSUITABLE": ("Unsuitable", "#ff7b72"),
    }
    readiness = Counter(result.readiness for result in results)
    languages = Counter(
        {
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "python": "Python",
            "go": "Go",
        }.get(language, language.title())
        for result in results
        for language in result.languages
    )
    totals = {
        "Evidence": sum(result.evidence for result in results),
        "Claims": sum(result.claims for result in results),
        "Capabilities": sum(result.capabilities for result in results),
        "Skill bundles": sum(result.bundles for result in results),
    }
    test_cases = _test_case_count()
    max_readiness = max(readiness.values(), default=0)
    max_language = max(languages.values(), default=0)
    max_total = max(totals.values(), default=0)
    readiness_rows = "".join(
        _bar_row(
            82,
            356 + index * 54,
            readiness_labels[key][0],
            readiness[key],
            max_readiness,
            readiness_labels[key][1],
            value_x=574,
        )
        for index, key in enumerate(("STATIC_READY", "REVIEW_REQUIRED", "UNSUITABLE"))
    )
    language_rows = "".join(
        _bar_row(
            640,
            356 + index * 48,
            key,
            value,
            max_language,
            "#66b3ff",
            300,
            1138,
        )
        for index, (key, value) in enumerate(
            sorted(languages.items(), key=lambda item: (-item[1], item[0]))
        )
    )
    total_items = list(totals.items())
    total_rows = "".join(
        _bar_row(
            82 if index % 2 == 0 else 640,
            610 + (index // 2) * 40,
            key,
            value,
            max_total,
            "#b38cff",
            250,
            574 if index % 2 == 0 else 1138,
        )
        for index, (key, value) in enumerate(total_items)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 740" role="img"
  aria-labelledby="title description">
  <title id="title">Repo-to-Skill measured benchmark snapshot</title>
  <desc id="description">Static discovery measurements from ten repository fixtures.</desc>
  <style>
    .title {{ fill: #f8fafc; font: 700 30px system-ui, sans-serif; }}
    .subtitle {{ fill: #9fb0c6; font: 400 15px system-ui, sans-serif; }}
    .panel-title {{ fill: #f8fafc; font: 700 17px system-ui, sans-serif; }}
    .body {{ fill: #cbd5e1; font: 500 14px system-ui, sans-serif; }}
    .number {{ fill: #f8fafc; font: 700 15px system-ui, sans-serif; text-anchor: end; }}
    .card-label {{ fill: #9fb0c6; font: 600 12px system-ui, sans-serif; }}
    .card-number {{ fill: #f8fafc; font: 700 28px system-ui, sans-serif; }}
    .foot {{ fill: #7f91aa; font: 400 12px system-ui, sans-serif; }}
  </style>
  <rect width="1200" height="740" rx="24" fill="#0f172a"/>
  {_text(56, 58, "Repo-to-Skill", "title")}
  {_text(
      56,
      86,
      "Measured snapshot · static discovery only · generated from in-repo fixtures",
      "subtitle",
  )}
  <g>
    <rect x="56" y="118" width="204" height="86" rx="14" fill="#17243a"/>
    {_text(76, 146, "FIXTURES", "card-label")}
    {_text(76, 184, len(results), "card-number")}
    <rect x="276" y="118" width="204" height="86" rx="14" fill="#17243a"/>
    {_text(296, 146, "TEST CASES", "card-label")}
    {_text(296, 184, test_cases, "card-number")}
    <rect x="496" y="118" width="204" height="86" rx="14" fill="#17243a"/>
    {_text(516, 146, "EVIDENCE", "card-label")}
    {_text(516, 184, totals["Evidence"], "card-number")}
    <rect x="716" y="118" width="204" height="86" rx="14" fill="#17243a"/>
    {_text(736, 146, "CAPABILITIES", "card-label")}
    {_text(736, 184, totals["Capabilities"], "card-number")}
    <rect x="936" y="118" width="204" height="86" rx="14" fill="#17243a"/>
    {_text(956, 146, "SKILL BUNDLES", "card-label")}
    {_text(956, 184, totals["Skill bundles"], "card-number")}
  </g>
  <rect x="56" y="236" width="530" height="286" rx="16" fill="#142136"/>
  {_text(82, 276, "Readiness by fixture", "panel-title")}
  {_text(82, 298, "10 controlled cases", "subtitle")}
  {readiness_rows}
  <rect x="614" y="236" width="530" height="286" rx="16" fill="#142136"/>
  {_text(640, 276, "Language adapters exercised", "panel-title")}
  {_text(640, 298, "fixture count by detected language", "subtitle")}
  {language_rows}
  <rect x="56" y="544" width="1088" height="150" rx="16" fill="#142136"/>
  {_text(82, 574, "Evidence graph totals", "panel-title")}
  {total_rows}
  {_text(82, 724, "Reproduce: PYTHONPATH=src python scripts/measure_benchmark.py", "foot")}
</svg>
'''


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    results = _measure()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(_render_svg(results), encoding="utf-8", newline="\n")
    readiness = Counter(result.readiness for result in results)
    print(
        f"fixtures={len(results)} tests={_test_case_count()} "
        f"evidence={sum(result.evidence for result in results)} "
        f"claims={sum(result.claims for result in results)} "
        f"capabilities={sum(result.capabilities for result in results)} "
        f"bundles={sum(result.bundles for result in results)} "
        f"static_ready={readiness['STATIC_READY']} "
        f"review_required={readiness['REVIEW_REQUIRED']} "
        f"unsuitable={readiness['UNSUITABLE']}"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
