# Repo-to-Skill Compiler

Evidence-driven compiler that turns a repository snapshot into portable Agent Skills.

The current implementation supports local directories, local Git repositories, and public GitHub
HTTPS URLs. Supported static CLI discovery currently includes:

- Python entrypoints from `[project.scripts]`, Poetry scripts, and `setup.cfg`, with conservative
  argparse/Click-style option extraction.
- JavaScript/TypeScript `package.json` `bin` entrypoints and target-file verification.
- Go root and `cmd/<name>` main packages, with conservative standard flag/Cobra-style option
  extraction.

The compiler never imports, builds, or executes target repository code during discovery.

```bash
PYTHONPATH=src python -m r2s inspect tests/fixtures/python_cli --json
PYTHONPATH=src python -m r2s inspect tests/fixtures/js_cli --json
PYTHONPATH=src python -m r2s inspect tests/fixtures/go_cli --json
PYTHONPATH=src python -m r2s inspect https://github.com/owner/repo --ref main --json
PYTHONPATH=src python -m r2s build <run-id> --goal "Use the demo CLI" --target codex
PYTHONPATH=src python -m r2s update <run-id> --repo ./repo --goal "Use changed commands"
PYTHONPATH=src python -m r2s validate run-output/<run-id>/compilations/<id>/codex-plugin
PYTHONPATH=src python -m r2s runs
PYTHONPATH=src python -m r2s ui --output run-output --open
```

`inspect` writes a goal-independent Discovery Run. Reusing its run ID for multiple goals or client
targets avoids rescanning source. `build --target portable` emits one Skill per CLI entrypoint;
`build --target codex` additionally emits a skill-only plugin with
`.codex-plugin/plugin.json` and `skills/`.

Discovery Runs are content-addressed by Snapshot and complete canonical IR. Cached loads verify the
run envelope, source lock, split IR artifacts, bounded regular-file policy, and—when available—the
byte-level hashes in `runs.sqlite3`. A copied run directory remains usable with self-consistency
checks even when its original index is not present.

When a goal explicitly names one discovered command, the deterministic Planner selects that command
instead of generating unrelated Skills. Monorepo command-name conflicts and slug collisions fail
closed as `REVIEW_REQUIRED`.

`update` creates a new Discovery Run and a versioned drift report. Local runs require an explicit
`--repo` so absolute local paths are never persisted in source locks; public GitHub runs can reuse
their public locator and requested ref. With `--goal`, only added or changed Capabilities selected
by that goal are generated. This output is a `capability_delta`, not a complete replacement package;
Codex delta plugins use a separate `-delta` name.

## Local dashboard

`r2s ui` opens a small read-only dashboard at `http://127.0.0.1:8765/` by default. It shows actual
Discovery Runs, verified snapshots, capabilities, findings, compilation records, update reports,
and paginated evidence metadata. It never sends source contents elsewhere or runs repository code.
The server rejects non-loopback hosts; choose another local port with `--port`.

For Git sources, `source.lock.json` records the requested ref, resolved commit, Git object format,
dirty-worktree state, scan policy, and policy-filtered analysis tree hash. Dirty local files never
claim to be content from `HEAD`. Remote source URLs are restricted to public
`https://github.com/<owner>/<repo>` locations.

Installation is preview-only unless explicitly executed, and always requires a user-selected
destination:

```bash
PYTHONPATH=src python -m r2s install <codex-plugin> --destination ./installed-plugins
PYTHONPATH=src python -m r2s install <codex-plugin> --destination ./installed-plugins --execute
```

Formal project baseline is Python 3.12 with uv. The walking slice intentionally uses only the
standard library so it remains testable in restricted bootstrap environments.
