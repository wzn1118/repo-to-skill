# ADR 0006: Conservative Multi-Language Static Adapters

Status: accepted

Python uses its native AST. JavaScript/TypeScript initially trusts only package bin metadata and an
in-policy target file. Go uses a comment/string-aware lexical adapter until a pinned native Go AST
helper is available. Lower-fidelity adapters may omit facts but must not compensate by guessing.

All adapters emit the same Evidence and Claim types. Command ownership conflicts are resolved after
all analyzers run, and output-name collisions are checked again by the Generator. No adapter may
introduce assumed flags such as `--help` without explicit evidence.
