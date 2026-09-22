from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from semantic_gold import citation, digest, write_new

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "benchmark/repository-metadata.json"


OPTIONS = {
    "black": {
        "command": "black",
        "source": "src/black/__init__.py",
        "items": [
            ("-c", '"-c", "--code",', 1, ["-c", "--code"]),
            ("--line-length", '"--line-length",', 1, ["-l", "--line-length"]),
            ("--target-version", '"--target-version",', 1, ["-t", "--target-version"], {"shape.repeatable": True}),
            ("--pyi", '"--pyi",', 0, ["--pyi"]),
            ("--ipynb", '"--ipynb",', 0, ["--ipynb"]),
            ("--python-cell-magics", '"--python-cell-magics",', 1, ["--python-cell-magics"], {"shape.repeatable": True}),
            ("--skip-source-first-line", '"--skip-source-first-line",', 0, ["-x", "--skip-source-first-line"]),
            ("--skip-string-normalization", '"--skip-string-normalization",', 0, ["-S", "--skip-string-normalization"]),
            ("--skip-magic-trailing-comma", '"--skip-magic-trailing-comma",', 0, ["-C", "--skip-magic-trailing-comma"]),
            ("--preview", '"--preview",', 0, ["--preview"]),
            ("--unstable", '"--unstable",', 0, ["--unstable"]),
            ("--check", '"--check",', 0, ["--check"]),
            ("--diff", '"--diff",', 0, ["--diff"]),
            ("--color", '"--color/--no-color",', 0, ["--color", "--no-color"]),
            ("--line-ranges", '"--line-ranges",', 1, ["--line-ranges"], {"shape.repeatable": True}),
            ("--fast", '"--fast/--safe",', 0, ["--fast", "--safe"]),
            ("--required-version", '"--required-version",', 1, ["--required-version"]),
            ("--exclude", '"--exclude",', 1, ["--exclude"]),
            ("--extend-exclude", '"--extend-exclude",', 1, ["--extend-exclude"]),
            ("--force-exclude", '"--force-exclude",', 1, ["--force-exclude"]),
        ],
    },
    "pre-commit": {
        "command": "pre-commit",
        "source": "pre_commit/main.py",
        "items": [
            ("hook", "parser.add_argument('hook',", 1, [], {"kind": "argument", "position": 0}),
            ("--all-files", "'--all-files', '-a',", 0, ["--all-files", "-a"]),
            ("--files", "'--files', nargs='*',", "*", ["--files"]),
            ("--fail-fast", "'--fail-fast', action='store_true'", 0, ["--fail-fast"]),
            ("--hook-stage", "'--hook-stage',", 1, ["--hook-stage"]),
            ("--from-ref", "'--from-ref', '--source', '-s'", 1, ["--from-ref", "--source", "-s"]),
            ("--to-ref", "'--to-ref', '--origin', '-o'", 1, ["--to-ref", "--origin", "-o"]),
            ("--verbose", "'--verbose', '-v'", 0, ["--verbose", "-v"]),
            ("--repo", "'--repo', dest='repos'", 1, ["--repo"], {"shape.repeatable": True}),
            ("--jobs", "'-j', '--jobs', type=int", 1, ["-j", "--jobs"]),
            ("--freeze", "'--freeze', action='store_true'", 0, ["--freeze"]),
            ("--bleeding-edge", "'--bleeding-edge', action='store_true'", 0, ["--bleeding-edge"]),
            ("--overwrite", "'-f', '--overwrite'", 0, ["-f", "--overwrite"]),
            ("--install-hooks", "'--install-hooks', action='store_true'", 0, ["--install-hooks"]),
            ("--allow-missing-config", "'--allow-missing-config', action='store_true'", 0, ["--allow-missing-config"]),
            ("--hook-type", "def _add_hook_type_option", 1, ["-t", "--hook-type"], {"shape.repeatable": True}),
            ("repo", "'repo', help='Repository", 1, [], {"kind": "argument", "position": 0}),
            ("--ref", "'--ref', '--rev'", 1, ["--ref", "--rev"]),
            ("filenames", "validate_config_parser.add_argument('filenames'", "*", [], {"kind": "argument", "position": 0}),
            ("manifest-filenames", "validate_manifest_parser.add_argument('filenames'", "*", [], {"kind": "argument", "position": 0}),
        ],
    },
    "prettier": {
        "command": "prettier",
        "source": "src/cli/cli-options.evaluate.js",
        "items": [
            ("--cache", "cache: {", 0, ["--cache"]),
            ("--cache-location", "cacheLocation: {", 1, ["--cache-location"]),
            ("--cache-strategy", "cacheStrategy: {", 1, ["--cache-strategy"]),
            ("--check", "check: {", 0, ["--check", "-c"]),
            ("--color", "color: {", 0, ["--color", "--no-color"]),
            ("--config", "  config: {", 1, ["--config"]),
            ("--config-precedence", "configPrecedence: {", 1, ["--config-precedence"]),
            ("--debug-repeat", "debugRepeat: {", 1, ["--debug-repeat"]),
            ("--editorconfig", "editorconfig: {", 0, ["--editorconfig"]),
            ("--error-on-unmatched-pattern", "errorOnUnmatchedPattern: {", 0, ["--error-on-unmatched-pattern"]),
            ("--file-info", "fileInfo: {", 1, ["--file-info"]),
            ("--find-config-path", "findConfigPath: {", 1, ["--find-config-path"]),
            ("--ignore-path", "ignorePath: {", 1, ["--ignore-path"], {"shape.repeatable": True}),
            ("--ignore-unknown", "ignoreUnknown: {", 0, ["--ignore-unknown", "-u"]),
            ("--list-different", "listDifferent: {", 0, ["--list-different", "-l"]),
            ("--log-level", "logLevel: {", 1, ["--log-level"]),
            ("--support-info", "supportInfo: {", 0, ["--support-info"]),
            ("--write", "write: {", 0, ["--write", "-w"]),
            ("--stdin-filepath", "filepath: {", 1, ["--stdin-filepath"], "src/main/core-options.evaluate.js"),
            ("--parser", "parser: {", 1, ["--parser"], "src/main/core-options.evaluate.js"),
        ],
    },
    "github-cli": {
        "command": "gh",
        "items": [
            ("--shell", ("pkg/cmd/completion/completion.go", "StringEnumFlag(cmd, &shellType"), 1, ["--shell", "-s"], {"path": ["completion"]}),
            ("--host", ("pkg/cmd/config/get/get.go", "StringVarP(&opts.Hostname"), 1, ["--host", "-h"], {"path": ["config", "get"]}),
            ("--host-set", ("pkg/cmd/config/set/set.go", "StringVarP(&opts.Hostname"), 1, ["--host", "-h"], {"path": ["config", "set"]}),
            ("--shell-alias", ("pkg/cmd/alias/set/set.go", "BoolVarP(&opts.IsShell"), 0, ["--shell", "-s"], {"path": ["alias", "set"]}),
            ("--clobber", ("pkg/cmd/alias/set/set.go", "BoolVar(&opts.OverwriteExisting"), 0, ["--clobber"], {"path": ["alias", "set"]}),
            ("--all", ("pkg/cmd/alias/delete/delete.go", "BoolVar(&opts.All"), 0, ["--all"], {"path": ["alias", "delete"]}),
            ("--web", ("pkg/cmd/pr/list/list.go", '"web", "w"'), 0, ["--web", "-w"], {"path": ["pr", "list"]}),
            ("--limit", ("pkg/cmd/pr/list/list.go", '"limit", "L"'), 1, ["--limit", "-L"], {"path": ["pr", "list"]}),
            ("--state", ("pkg/cmd/pr/list/list.go", '"state", "s"'), 1, ["--state", "-s"], {"path": ["pr", "list"]}),
            ("--base", ("pkg/cmd/pr/list/list.go", '"base", "B"'), 1, ["--base", "-B"], {"path": ["pr", "list"]}),
            ("--head", ("pkg/cmd/pr/list/list.go", '"head", "H"'), 1, ["--head", "-H"], {"path": ["pr", "list"]}),
            ("--label", ("pkg/cmd/pr/list/list.go", '"label", "l"'), 1, ["--label", "-l"], {"path": ["pr", "list"]}),
            ("--author", ("pkg/cmd/pr/list/list.go", '"author", "A"'), 1, ["--author", "-A"], {"path": ["pr", "list"]}),
            ("--assignee", ("pkg/cmd/pr/list/list.go", '"assignee", "a"'), 1, ["--assignee", "-a"], {"path": ["pr", "list"]}),
            ("--search", ("pkg/cmd/pr/list/list.go", '"search", "S"'), 1, ["--search", "-S"], {"path": ["pr", "list"]}),
            ("--issue-web", ("pkg/cmd/issue/list/list.go", '"web", "w"'), 0, ["--web", "-w"], {"path": ["issue", "list"]}),
            ("--issue-limit", ("pkg/cmd/issue/list/list.go", '"limit", "L"'), 1, ["--limit", "-L"], {"path": ["issue", "list"]}),
            ("--issue-state", ("pkg/cmd/issue/list/list.go", '"state", "s"'), 1, ["--state", "-s"], {"path": ["issue", "list"]}),
            ("--issue-label", ("pkg/cmd/issue/list/list.go", '"label", "l"'), 1, ["--label", "-l"], {"path": ["issue", "list"]}),
            ("--issue-author", ("pkg/cmd/issue/list/list.go", '"author", "A"'), 1, ["--author", "-A"], {"path": ["issue", "list"]}),
        ],
    },
    "fzf": {
        "command": "fzf",
        "source": "src/options.go",
        "items": [
            ("--exact", 'case "-e", "--exact":', 0, ["-e", "--exact"]),
            ("--no-exact", 'case "+e", "--no-exact":', 0, ["+e", "--no-exact"]),
            ("--extended", 'case "-x", "--extended":', 0, ["-x", "--extended"]),
            ("--no-extended", 'case "+x", "--no-extended":', 0, ["+x", "--no-extended"]),
            ("--query", 'case "-q", "--query":', 1, ["-q", "--query"]),
            ("--filter", 'case "-f", "--filter":', 1, ["-f", "--filter"]),
            ("--literal", 'case "--literal":', 0, ["--literal"]),
            ("--no-literal", 'case "--no-literal":', 0, ["--no-literal"]),
            ("--algo", 'case "--algo":', 1, ["--algo"]),
            ("--scheme", 'case "--scheme":', 1, ["--scheme"]),
            ("--bind", 'case "--bind":', 1, ["--bind"]),
            ("--delimiter", 'case "-d", "--delimiter":', 1, ["-d", "--delimiter"]),
            ("--nth", 'case "-n", "--nth":', 1, ["-n", "--nth"]),
            ("--no-sort", 'case "+s", "--no-sort":', 0, ["+s", "--no-sort"]),
            ("--tac", 'case "--tac":', 0, ["--tac"]),
            ("--ansi", 'case "--ansi":', 0, ["--ansi"]),
            ("--no-mouse", 'case "--no-mouse":', 0, ["--no-mouse"]),
            ("--reverse", 'case "--reverse":', 0, ["--reverse"]),
            ("--cycle", 'case "--cycle":', 0, ["--cycle"]),
            ("--select-1", 'case "-1", "--select-1":', 0, ["-1", "--select-1"]),
        ],
    },
    "yt-dlp": {
        "command": "yt-dlp",
        "source": "yt_dlp/options.py",
        "items": [
            ("--ignore-errors", "'-i', '--ignore-errors',", 0, ["-i", "--ignore-errors"]),
            ("--socket-timeout", "'--socket-timeout',", 1, ["--socket-timeout"]),
            ("--playlist-start", "'--playlist-start',", 1, ["--playlist-start"]),
            ("--playlist-end", "'--playlist-end',", 1, ["--playlist-end"]),
            ("--no-playlist", "'--no-playlist',", 0, ["--no-playlist"]),
            ("--yes-playlist", "'--yes-playlist',", 0, ["--yes-playlist"]),
            ("--format", "'-f', '--format',", 1, ["-f", "--format"]),
            ("--list-formats", "'-F', '--list-formats',", 0, ["-F", "--list-formats"]),
            ("--concurrent-fragments", "'-N', '--concurrent-fragments',", 1, ["-N", "--concurrent-fragments"]),
            ("--retries", "'-R', '--retries',", 1, ["-R", "--retries"]),
            ("--quiet", "'-q', '--quiet',", 0, ["-q", "--quiet"]),
            ("--simulate", "'-s', '--simulate',", 0, ["-s", "--simulate"]),
            ("--skip-download", "'--skip-download', '--no-download',", 0, ["--skip-download", "--no-download"]),
            ("--dump-json", "'-j', '--dump-json',", 0, ["-j", "--dump-json"]),
            ("--verbose", "'-v', '--verbose',", 0, ["-v", "--verbose"]),
            ("--output", "'-o', '--output',", 1, ["-o", "--output"]),
            ("--write-description", "'--write-description',", 0, ["--write-description"]),
            ("--write-info-json", "'--write-info-json',", 0, ["--write-info-json"]),
            ("--extract-audio", "'-x', '--extract-audio',", 0, ["-x", "--extract-audio"]),
            ("--audio-format", "'--audio-format', metavar", 1, ["--audio-format"]),
        ],
    },
    "eslint": {
        "command": "eslint",
        "source": "lib/options.js",
        "items": [
            ("--config", 'option: "config",', 1, ["--config", "-c"]),
            ("--inspect-config", 'option: "inspect-config",', 0, ["--inspect-config"]),
            ("--parser", 'option: "parser",', 1, ["--parser"]),
            ("--fix", 'option: "fix",', 0, ["--fix"]),
            ("--fix-dry-run", 'option: "fix-dry-run",', 0, ["--fix-dry-run"]),
            ("--ignore", 'option: "ignore",', 0, ["--ignore"]),
            ("--stdin", 'option: "stdin",', 0, ["--stdin"]),
            ("--stdin-filename", 'option: "stdin-filename",', 1, ["--stdin-filename"]),
            ("--quiet", 'option: "quiet",', 0, ["--quiet"]),
            ("--max-warnings", 'option: "max-warnings",', 1, ["--max-warnings"]),
            ("--output-file", 'option: "output-file",', 1, ["--output-file", "-o"]),
            ("--format", 'option: "format",', 1, ["--format", "-f"]),
            ("--color", 'option: "color",', 0, ["--color", "--no-color"]),
            ("--inline-config", 'option: "inline-config",', 0, ["--inline-config"]),
            ("--report-unused-disable-directives", 'option: "report-unused-disable-directives",', 0, ["--report-unused-disable-directives"]),
            ("--report-unused-disable-directives-severity", 'option: "report-unused-disable-directives-severity",', 1, ["--report-unused-disable-directives-severity"]),
            ("--cache", 'option: "cache",', 0, ["--cache"]),
            ("--cache-file", 'option: "cache-file",', 1, ["--cache-file"]),
            ("--cache-location", 'option: "cache-location",', 1, ["--cache-location"]),
            ("--cache-strategy", 'option: "cache-strategy",', 1, ["--cache-strategy"]),
        ],
    },
    "hugo": {
        "command": "hugo",
        "items": [
            ("--source", ("commands/commandeer.go", '"source", "s"'), 1, ["--source", "-s"]),
            ("--destination", ("commands/commandeer.go", '"destination", "d"'), 1, ["--destination", "-d"]),
            ("--environment", ("commands/commandeer.go", '"environment", "e"'), 1, ["--environment", "-e"]),
            ("--themesDir", ("commands/commandeer.go", '"themesDir", ""'), 1, ["--themesDir"]),
            ("--noBuildLock", ("commands/commandeer.go", '"noBuildLock", ""'), 0, ["--noBuildLock"]),
            ("--clock", ("commands/commandeer.go", '"clock", ""'), 1, ["--clock"]),
            ("--config", ("commands/commandeer.go", '"config", ""'), 1, ["--config"]),
            ("--configDir", ("commands/commandeer.go", '"configDir", "config"'), 1, ["--configDir"]),
            ("--quiet", ("commands/commandeer.go", '"quiet", false'), 0, ["--quiet"]),
            ("--renderToMemory", ("commands/commandeer.go", '"renderToMemory", "M"'), 0, ["--renderToMemory", "-M"]),
            ("--theme", ("commands/commandeer.go", '"theme", "t"'), 1, ["--theme", "-t"]),
            ("--baseURL", ("commands/commandeer.go", '"baseURL", "b"'), 1, ["--baseURL", "-b"]),
            ("--cacheDir", ("commands/commandeer.go", '"cacheDir", ""'), 1, ["--cacheDir"]),
            ("--contentDir", ("commands/commandeer.go", '"contentDir", "c"'), 1, ["--contentDir", "-c"]),
            ("--cleanDestinationDir", ("commands/commandeer.go", '"cleanDestinationDir", false'), 0, ["--cleanDestinationDir"]),
            ("--buildDrafts", ("commands/commandeer.go", '"buildDrafts", "D"'), 0, ["--buildDrafts", "-D"]),
            ("--buildFuture", ("commands/commandeer.go", '"buildFuture", "F"'), 0, ["--buildFuture", "-F"]),
            ("--buildExpired", ("commands/commandeer.go", '"buildExpired", "E"'), 0, ["--buildExpired", "-E"]),
            ("--ignoreCache", ("commands/commandeer.go", 'cmd.Flags().BoolP("ignoreCache",'), 0, ["--ignoreCache"]),
            ("--port", ("commands/server.go", '"port", "p"'), 1, ["--port", "-p"], {"path": ["server"]}),
        ],
    },
    "poetry": {
        "command": "poetry",
        "items": [
            ("--group", ("src/poetry/console/commands/add.py", '            "group",'), 1, ["--group", "-G"], {"path": ["add"]}),
            ("--dev", ("src/poetry/console/commands/add.py", '            "dev",'), 0, ["--dev", "-D"], {"path": ["add"]}),
            ("--editable", ("src/poetry/console/commands/add.py", 'option("editable",'), 0, ["--editable", "-e"], {"path": ["add"]}),
            ("--extras", ("src/poetry/console/commands/add.py", '            "extras",'), 1, ["--extras", "-E"], {"path": ["add"], "repeatable": True}),
            ("--optional", ("src/poetry/console/commands/add.py", '            "optional",'), 1, ["--optional"], {"path": ["add"]}),
            ("--python", ("src/poetry/console/commands/add.py", '            "python",'), 1, ["--python"], {"path": ["add"]}),
            ("--platform", ("src/poetry/console/commands/add.py", '            "platform",'), 1, ["--platform"], {"path": ["add"]}),
            ("--markers", ("src/poetry/console/commands/add.py", '            "markers",'), 1, ["--markers"], {"path": ["add"]}),
            ("--source", ("src/poetry/console/commands/add.py", '            "source",'), 1, ["--source"], {"path": ["add"]}),
            ("--allow-prereleases", ("src/poetry/console/commands/add.py", 'option("allow-prereleases",'), 0, ["--allow-prereleases"], {"path": ["add"]}),
            ("--dry-run-add", ("src/poetry/console/commands/add.py", '            "dry-run",'), 0, ["--dry-run"], {"path": ["add"]}),
            ("--sync", ("src/poetry/console/commands/install.py", '            "sync",'), 0, ["--sync"], {"path": ["install"]}),
            ("--no-root", ("src/poetry/console/commands/install.py", '            "no-root",'), 0, ["--no-root"], {"path": ["install"]}),
            ("--no-directory", ("src/poetry/console/commands/install.py", '            "no-directory",'), 0, ["--no-directory"], {"path": ["install"]}),
            ("--dry-run-install", ("src/poetry/console/commands/install.py", '            "dry-run",'), 0, ["--dry-run"], {"path": ["install"]}),
            ("--extras-install", ("src/poetry/console/commands/install.py", '            "extras",'), 1, ["--extras", "-E"], {"path": ["install"], "repeatable": True}),
            ("--all-extras", ("src/poetry/console/commands/install.py", 'option("all-extras",'), 0, ["--all-extras"], {"path": ["install"]}),
            ("--all-groups", ("src/poetry/console/commands/install.py", 'option("all-groups",'), 0, ["--all-groups"], {"path": ["install"]}),
            ("--only-root", ("src/poetry/console/commands/install.py", 'option("only-root",'), 0, ["--only-root"], {"path": ["install"]}),
            ("--compile", ("src/poetry/console/commands/install.py", '            "compile",'), 0, ["--compile"], {"path": ["install"]}),
        ],
    },
    "cookiecutter": {
        "command": "cookiecutter",
        "source": "cookiecutter/cli.py",
        "items": [
            ("cookiecutter", ("cookiecutter/__main__.py", "from cookiecutter.cli import main"), 0, [], {"kind": "command", "target": "cookiecutter.__main__:main"}),
            ("template", "@click.argument('template'", 1, [], {"kind": "argument", "position": 0}),
            ("extra_context", "@click.argument('extra_context'", -1, [], {"kind": "argument", "position": 1}),
            ("--no-input", "'--no-input',", 0, ["--no-input"]),
            ("--checkout", "'-c',", 1, ["-c", "--checkout"]),
            ("--directory", "'--directory',", 1, ["--directory"]),
            ("--verbose", "'-v', '--verbose'", 0, ["-v", "--verbose"]),
            ("--replay", "'--replay',", 0, ["--replay"]),
            ("--replay-file", "'--replay-file',", 1, ["--replay-file"]),
            ("--overwrite-if-exists", "'--overwrite-if-exists',", 0, ["-f", "--overwrite-if-exists"]),
            ("--skip-if-file-exists", "'--skip-if-file-exists',", 0, ["-s", "--skip-if-file-exists"]),
            ("--output-dir", "'-o',", 1, ["-o", "--output-dir"]),
            ("--config-file", "'--config-file',", 1, ["--config-file"]),
            ("--default-config", "'--default-config',", 0, ["--default-config"]),
            ("--debug-file", "'--debug-file',", 1, ["--debug-file"]),
            ("--accept-hooks", "'--accept-hooks',", 1, ["--accept-hooks"]),
            ("--list-installed", "'-l', '--list-installed'", 0, ["-l", "--list-installed"]),
            ("--keep-project-on-failure", "'--keep-project-on-failure',", 0, ["--keep-project-on-failure"]),
            ("--version", "@click.version_option", 0, ["--version", "-V"]),
            ("--help", "context_settings={", 0, ["--help", "-h"]),
        ],
    },
}


COMMITS = {
    "black": "20622e1259c29bda81831962ace1348ba1921c84",
    "pre-commit": "a9bba55a3f74068b53f4bd4d831d7e05e34eae6c",
    "prettier": "0017ecf34df0b6a0bdd156bb02fe62603d4aa682",
    "github-cli": "38316c1c4f275030e3df6666382922e75410d68b",
    "fzf": "b1be3a8be1b833ce5b92fbbac11637643d60a046",
    "yt-dlp": "bbc809a1161d3bfca51fa36f59dda35556ee85a0",
    "eslint": "24310e3a0e22b3c086ca402f88448676f2e1cfcd",
    "hugo": "a374b865f7e99cccafcbe443dcdb47552b91af3c",
    "poetry": "be56ff07db06e9b82574648433ca228e4cac549b",
    "cookiecutter": "c88fbe921c97c58b65f1883ba90a0ab53cc91b34",
}


REPOSITORIES = {
    "black": "psf/black",
    "pre-commit": "pre-commit/pre-commit",
    "prettier": "prettier/prettier",
    "github-cli": "cli/cli",
    "fzf": "junegunn/fzf",
    "yt-dlp": "yt-dlp/yt-dlp",
    "eslint": "eslint/eslint",
    "hugo": "gohugoio/hugo",
    "poetry": "python-poetry/poetry",
    "cookiecutter": "cookiecutter/cookiecutter",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_metadata() -> dict:
    return json.loads(METADATA.read_text(encoding="utf-8"))


def build_assertions(repo_id: str, snapshots: Path) -> list[dict]:
    spec = OPTIONS[repo_id]
    commit = COMMITS[repo_id]
    cached = snapshots / f"{repo_id}-{commit}" / "source"
    assertions = []
    for index, item in enumerate(spec["items"], start=1):
        name, source, arity, aliases, *extras = item
        path = extras[0].get("path", []) if extras and isinstance(extras[0], dict) else []
        fields = {"shape.arity": arity, "shape.aliases": aliases}
        if extras and isinstance(extras[0], dict):
            extra = extras[0]
            if extra.get("kind") == "command":
                fields = {"target": extra["target"]}
                kind = "command"
            elif extra.get("kind") == "argument":
                fields = {"shape.arity": arity, "position": extra["position"]}
                kind = "argument"
            else:
                kind = "option"
                if "repeatable" in extra:
                    fields["shape.repeatable"] = extra["repeatable"]
        else:
            kind = "option"
        if isinstance(source, tuple):
            relative, anchor = source
        else:
            relative = extras[0] if extras and isinstance(extras[0], str) else spec.get("source")
            anchor = source
        assertions.append({
            "id": f"{repo_id}-{index:02d}-{slug(name)}",
            "kind": kind,
            "command": spec["command"],
            "command_path": path,
            "name": name,
            "fields": fields,
            "citations": [citation(cached, relative, anchor, 9)],
            "rationale": "The expected parameter shape is independently recorded from the pinned source declaration.",
        })
    assertions.extend({
        "id": f"{repo_id}-negative-{index}",
        "kind": "option",
        "command": spec["command"],
        "command_path": [],
        "name": f"--r2s-absent-{index}",
        "expectation": "absent",
        "citations": [citation(
            cached,
            (spec["items"][0][4] if len(spec["items"][0]) > 4 and isinstance(spec["items"][0][4], str) else (spec["items"][0][1][0] if isinstance(spec["items"][0][1], tuple) else spec.get("source"))),
            (spec["items"][0][1][1] if isinstance(spec["items"][0][1], tuple) else spec["items"][0][1]),
            1,
        )],
        "rationale": "This deliberately absent option probes whether the compiler invents executable facts.",
    } for index in range(1, 3))
    return assertions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = load_metadata()
    metadata_hash = digest(METADATA.read_bytes())
    by_id = {item["id"]: item for item in metadata["repositories"]}
    repositories = []
    for repo_id in OPTIONS:
        if repo_id not in by_id or by_id[repo_id]["commit_sha"] != COMMITS[repo_id] or by_id[repo_id]["repository"] != REPOSITORIES[repo_id]:
            raise ValueError(f"SEMANTIC_GOLD_METADATA_PIN_MISMATCH: {repo_id}")
        repositories.append({
            "id": repo_id,
            "repository": REPOSITORIES[repo_id],
            "commit_sha": COMMITS[repo_id],
            "assertions": build_assertions(repo_id, args.snapshots),
        })
    payload = {
        "format": "r2s-semantic-gold-v1",
        "metadata_sha256": metadata_hash,
        "review_method": "agent-curated source anchors; retrospective comparison; not human verified",
        "tuning_scope": "frozen after v22 compiler run; no core analyzer changes were made to improve this score",
        "repositories": repositories,
    }
    write_new(args.output, payload)
    print(json.dumps({"positive": len(OPTIONS) * 20, "negative": len(OPTIONS) * 2, "output": str(args.output)}))


if __name__ == "__main__":
    main()
