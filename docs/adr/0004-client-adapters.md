# ADR 0004: Portable Skills With Thin Client Adapters

Status: accepted

The generator always creates portable Skills first. The Codex adapter only adds the plugin manifest
and copies Skills under `skills/`. Client format changes are isolated from source analysis and
Procedure planning.
