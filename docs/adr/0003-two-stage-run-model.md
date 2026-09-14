# ADR 0003: Separate Discovery and Compilation Runs

Status: accepted

Discovery is keyed by source tree and analyzer schema. Compilation is keyed by goal, target, and
client profile. SQLite records their parent-child relationship while canonical JSON remains the
portable source of truth. Changing a goal or target must not rescan source.
