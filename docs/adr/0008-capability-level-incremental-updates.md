# ADR 0008: Capability-Level Incremental Updates

## Status

Accepted on 2026-09-01.

## Decision

`r2s update` compares two complete Discovery Runs rather than diffing generated Markdown. Each
Capability receives a logical key and a dependency fingerprint derived from its supported Claims
and complete referenced Evidence. Inventory changes are reported separately.

Repository-wide policy state has its own fingerprint covering schema version, scan policy,
language/type classification, Findings, and license Claims/Evidence. A policy change invalidates
all surviving Capabilities even when their command-specific Evidence is unchanged.

Local Snapshot locators remain privacy-preserving and do not store absolute paths. Updating a local
run therefore requires an explicit `--repo`. Public GitHub locators can be converted back to their
HTTPS source, while the previous requested ref is reused unless `--ref` overrides it.

When `--goal` is supplied, the Planner first applies normal goal selection and then intersects that
selection with added or changed Capabilities. Generated output is an explicit `capability_delta`,
not a complete replacement. Codex delta plugins use a distinct `-delta` manifest name and every
filtered compilation writes `generation-scope.json`.

## Consequences

Changes to unreferenced files such as README content create a new content-addressed Discovery Run
and appear in the drift report, but do not rebuild Skills. Changes to a Capability's Evidence
rebuild that Capability. License or other global policy drift rebuilds every surviving Capability.

Removed Capabilities are reported but have no new bundle to compile. Producing a complete updated
installation by safely reusing unchanged bundles remains a later phase; delta plugins must not be
installed as silent replacements for full plugins.
