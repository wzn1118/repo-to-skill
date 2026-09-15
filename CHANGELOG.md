# Changelog

## Unreleased — 2026-09-15 stabilization work

- Reject modified or malformed generated bundles using strict provenance, complete file locks and
  deterministic document re-rendering. Legacy bundles should be regenerated for the new validator;
  historical reports remain unchanged.
- Bind Python options to supported parser/framework objects and reject unrelated goals instead of
  copying them into generated descriptions.
- Separate raw bytes from committed Git blob IDs; disable repository Git filters/fsmonitor and
  reject special files before scanning.
- Correct four Go module-suffix names and exclude known nested/hidden test workspace entrypoints.
  Full binary identity and command-graph inference remain incomplete.
- Add local static UI actions, explicit Docker verification, managed Codex updates and rollback API.
  Claude/Cursor directory projections do not yet have native-client compatibility evidence.
- Publish a separate fixed-corpus upgrade run, immutable-run safeguards and comparison figures.
  Selected fact recall remains 9/40; no task uplift or zero-hallucination claim is made.

This is an experimental working release line, not Beta/1.0 acceptance. See
[upgrade status](docs/upgrade-status.md) for remaining work and verification boundaries.
