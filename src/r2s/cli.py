from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from r2s import __version__
from r2s.core import (
    canonical_json,
    compare_discoveries,
    discover_source,
    generate,
    plan,
    readiness,
    resolve_discovery,
    schema_catalog,
    update_source,
    validate_path,
    write_discovery,
)
from r2s.generator import install_codex_plugin
from r2s.storage import compilation_root, list_runs, record_compilation, record_update
from r2s.toml_compat import TOMLDecodeError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="r2s")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect")
    inspect.add_argument("repo")
    inspect.add_argument("--ref")
    inspect.add_argument("--output", default="run-output")
    inspect.add_argument("--json", action="store_true")

    plan_command = commands.add_parser("plan")
    plan_command.add_argument("source", help="Repository path, discovery run path, or run ID")
    plan_command.add_argument("--goal", required=True)
    plan_command.add_argument("--ref")
    plan_command.add_argument("--output", default="run-output")
    plan_command.add_argument("--json", action="store_true")

    build_command = commands.add_parser("build")
    build_command.add_argument("source", help="Repository path, discovery run path, or run ID")
    build_command.add_argument("--goal", required=True)
    build_command.add_argument("--ref")
    build_command.add_argument("--target", choices=["portable", "codex"], default="portable")
    build_command.add_argument("--output", default="run-output")

    check = commands.add_parser("validate")
    check.add_argument("bundle")

    explain = commands.add_parser("explain")
    explain.add_argument("source", help="Repository path, discovery run path, or run ID")
    explain.add_argument("--output", default="run-output")
    explain.add_argument("--ref")
    explain.add_argument("--claim")

    schema = commands.add_parser("schema")
    schema.add_argument("action", choices=["export"])
    schema.add_argument("--output")

    runs = commands.add_parser("runs")
    runs.add_argument("--output", default="run-output")

    ui = commands.add_parser("ui", help="Serve a local read-only run dashboard")
    ui.add_argument("--output", default="run-output")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--open", action="store_true")

    update = commands.add_parser("update")
    update.add_argument("source", help="Existing discovery run path or run ID")
    update.add_argument("--repo", help="Required for local source updates")
    update.add_argument("--ref")
    update.add_argument("--goal")
    update.add_argument("--target", choices=["portable", "codex"], default="portable")
    update.add_argument("--output", default="run-output")

    install = commands.add_parser("install")
    install.add_argument("plugin")
    install.add_argument("--target", choices=["codex"], default="codex")
    install.add_argument("--destination", required=True)
    install.add_argument("--execute", action="store_true")
    return root


def _discovery(
    source: str,
    output_root: Path,
    ref: str | None = None,
) -> tuple[Any, Path]:
    cached, run_root = resolve_discovery(source, output_root)
    if cached is not None and run_root is not None:
        if ref is not None:
            raise ValueError("REF_NOT_ALLOWED_FOR_CACHED_RUN")
        return cached, run_root
    value = discover_source(source, output_root, ref)
    return value, write_discovery(value, output_root)


def _build_payload(result: Any) -> dict[str, Any]:
    return {
        "target": result.target,
        "root": result.root,
        "bundles": list(result.bundles),
        "readiness": result.readiness.value,
        "findings": [asdict(item) for item in result.findings],
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            discovery = discover_source(args.repo, Path(args.output), args.ref)
            run_root = write_discovery(discovery, Path(args.output))
            inspect_result = {
                "run_id": run_root.name,
                "run_root": str(run_root),
                "tree_sha256": discovery.tree_sha256,
                "snapshot": asdict(discovery.snapshot),
                "capabilities": len(discovery.capabilities),
                "languages": discovery.languages,
                "repository_types": discovery.repository_types,
                "findings": [asdict(item) for item in discovery.findings],
            }
            if args.json:
                print(canonical_json(inspect_result), end="")
            else:
                print(f"{run_root.name}: {len(discovery.capabilities)} capabilities")
        elif args.command == "plan":
            discovery, _ = _discovery(args.source, Path(args.output), args.ref)
            procedures = plan(discovery, args.goal)
            plan_value = [asdict(item) for item in procedures]
            if args.json:
                print(canonical_json(plan_value), end="")
            else:
                print("\n".join(item["title"] for item in plan_value))
        elif args.command == "build":
            discovery, discovery_root = _discovery(
                args.source,
                Path(args.output),
                args.ref,
            )
            compile_root = compilation_root(discovery_root, args.goal, args.target)
            build_result = generate(discovery, args.goal, compile_root, args.target)
            record_compilation(
                discovery_root,
                compile_root,
                args.goal,
                args.target,
                build_result.readiness.value,
            )
            print(canonical_json(_build_payload(build_result)), end="")
            return 0 if build_result.readiness.value == "STATIC_READY" else 3
        elif args.command == "validate":
            findings = validate_path(Path(args.bundle))
            status = readiness(findings)
            print(
                canonical_json(
                    {
                        "readiness": status.value,
                        "findings": [asdict(item) for item in findings],
                    }
                ),
                end="",
            )
            return 0 if not findings else 3
        elif args.command == "explain":
            discovery, _ = _discovery(args.source, Path(args.output), args.ref)
            if args.claim:
                claim = next(
                    (item for item in discovery.claims if item.id == args.claim),
                    None,
                )
                if claim is None:
                    raise ValueError(f"CLAIM_NOT_FOUND: {args.claim}")
                explain_value: dict[str, Any] = asdict(claim)
            else:
                explain_value = discovery.to_dict()
            print(canonical_json(explain_value), end="")
        elif args.command == "schema":
            content = canonical_json(schema_catalog())
            if args.output:
                Path(args.output).write_text(content, encoding="utf-8")
            else:
                print(content, end="")
        elif args.command == "runs":
            print(canonical_json(list_runs(Path(args.output))), end="")
        elif args.command == "ui":
            from r2s.ui import make_server

            server = make_server(Path(args.output), args.host, args.port)
            host, port = server.server_address[:2]
            host_text = host.decode() if isinstance(host, bytes) else host
            url = f"http://{host_text}:{port}/"
            print(url, flush=True)
            if args.open:
                import webbrowser

                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "update":
            output_root = Path(args.output)
            previous, previous_root = resolve_discovery(args.source, output_root)
            if previous is None or previous_root is None:
                raise ValueError("UPDATE_BASE_RUN_REQUIRED")
            repository = update_source(previous.snapshot, args.repo)
            requested_ref = args.ref if args.ref is not None else previous.snapshot.requested_ref
            current = discover_source(repository, output_root, requested_ref)
            current_root = write_discovery(current, output_root)
            report = compare_discoveries(
                previous,
                current,
                previous_root.name,
                current_root.name,
            )
            report_path = record_update(previous_root, current_root, report)
            payload: dict[str, Any] = {
                "old_run_id": previous_root.name,
                "new_run_id": current_root.name,
                "new_run_root": str(current_root),
                "report": report.to_dict(),
                "report_path": str(report_path),
                "build": None,
            }
            exit_code = 0
            selected_affected_ids: set[str] = set()
            if args.goal:
                goal_capability_ids = {
                    capability_id
                    for procedure in plan(current, args.goal)
                    for capability_id in procedure.capability_ids
                }
                selected_affected_ids = goal_capability_ids & set(
                    report.affected_new_capability_ids
                )
                payload["selected_affected_capability_ids"] = sorted(
                    selected_affected_ids
                )
            if args.goal and selected_affected_ids:
                compile_root = compilation_root(current_root, args.goal, args.target)
                update_result = generate(
                    current,
                    args.goal,
                    compile_root,
                    args.target,
                    selected_affected_ids,
                )
                record_compilation(
                    current_root,
                    compile_root,
                    args.goal,
                    args.target,
                    update_result.readiness.value,
                )
                payload["build"] = _build_payload(update_result)
                payload["build_scope"] = "capability_delta"
                if update_result.readiness.value != "STATIC_READY":
                    exit_code = 3
            print(canonical_json(payload), end="")
            return exit_code
        elif args.command == "install":
            target, findings, files = install_codex_plugin(
                Path(args.plugin),
                Path(args.destination),
                args.execute,
            )
            print(
                canonical_json(
                    {
                        "mode": "execute" if args.execute else "preview",
                        "target": str(target) if target else None,
                        "files": files,
                        "findings": [asdict(item) for item in findings],
                    }
                ),
                end="",
            )
            return 0 if not findings else 3
        return 0
    except (OSError, ValueError, TOMLDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
