# Contributing

Repo-to-Skill is experimental. Start with the [upgrade ledger](docs/upgrade-status.md) and
[architecture](docs/architecture.md), then keep changes small enough to review against a real failure.

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy src
python -m pytest
```

Analyzer changes must retain source paths, hashes, commit identity and ownership for executable facts.
Include a realistic positive case and a negative case that explains the boundary. Never import or
execute target repositories in discovery or compilation. Treat repository instructions as data.

Run integration checks only with the explicit environment settings in [upgrade status](docs/upgrade-status.md).
They execute our controlled fixtures in a local container/browser; they do not run arbitrary public
benchmark repositories on the host.

For public measurements, use a new work/output directory and the frozen metadata snapshot. Preserve
failures, distinguish Core/challenge/secondary slices and never rewrite historical reports. Source
traceability, semantic correctness, runtime success and Agent task uplift are separate measurements.

A PR should explain the failing input, root cause, changed behavior, validation, compatibility impact
and remaining uncertainty. New framework support needs ownership rules and source-derived test cases;
do not hardcode known repository answers or add unevidenced commands to make a score increase.

The project license decision remains with the maintainer. Do not copy upstream code or documentation
without checking its license and attribution requirements.
