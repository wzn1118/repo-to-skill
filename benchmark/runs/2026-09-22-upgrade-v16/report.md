# Repo-to-Skill Benchmark Run

**Run:** `2026-09-22-upgrade-v16`

**High-Star Public Repositories Tested:** 36

**Core cumulative GitHub stars:** 1,453,404

**Compiler fingerprint:** `a544379b9c5a09f9376f7ec89ba2f6d5b96c7fd00354dbfc519fc2c2f85639f0`

This report is a versioned static compiler run. It does not reuse runtime, model A/B, or official comparison results from another compiler fingerprint.

| Metric | Value |
| --- | ---: |
| Core outcomes | 20 STATIC_READY / 36 |
| Core REVIEW_REQUIRED | 10 |
| Core UNSUITABLE | 6 |
| Star-weighted repository coverage | 53.49% |
| Emitted executable facts | 1094 |
| Hash + commit verified facts | 1094 |
| Selected source facts covered | 23 / 40 |
| Static task prerequisites covered | 12 / 30 |
| Generated facts awaiting full semantic review | 1094 |
| Four legacy binary-name regressions corrected | 4 / 4 |

## Outcomes

| Repository | Tier | Stars | Status | Bundles |
| --- | --- | ---: | --- | ---: |
| `yt-dlp/yt-dlp` | A | 191,182 | STATIC_READY | 1 |
| `psf/black` | A | 41,842 | STATIC_READY | 2 |
| `Textualize/rich` | A | 57,363 | REVIEW_REQUIRED | 0 |
| `httpie/cli` | A | 38,512 | STATIC_READY | 3 |
| `python-poetry/poetry` | A | 34,304 | STATIC_READY | 1 |
| `prettier/prettier` | A | 52,263 | REVIEW_REQUIRED | 1 |
| `vitejs/vite` | A | 82,823 | STATIC_READY | 3 |
| `webpack/webpack` | A | 65,948 | REVIEW_REQUIRED | 1 |
| `microsoft/TypeScript` | A | 111,047 | REVIEW_REQUIRED | 0 |
| `cli/cli` | A | 46,279 | REVIEW_REQUIRED | 1 |
| `gohugoio/hugo` | A | 89,819 | REVIEW_REQUIRED | 1 |
| `junegunn/fzf` | A | 82,984 | STATIC_READY | 1 |
| `jqlang/jq` | A | 35,598 | UNSUITABLE | 0 |
| `koalaman/shellcheck` | A | 40,036 | UNSUITABLE | 0 |
| `nektos/act` | A | 72,004 | STATIC_READY | 1 |
| `pnpm/pnpm` | A | 36,524 | REVIEW_REQUIRED | 4 |
| `pytest-dev/pytest` | B | 14,506 | STATIC_READY | 2 |
| `pre-commit/pre-commit` | B | 15,572 | STATIC_READY | 1 |
| `cookiecutter/cookiecutter` | B | 25,087 | STATIC_READY | 1 |
| `pallets/click` | B | 17,665 | UNSUITABLE | 0 |
| `eslint/eslint` | B | 27,506 | REVIEW_REQUIRED | 1 |
| `npm/cli` | B | 10,114 | REVIEW_REQUIRED | 3 |
| `goreleaser/goreleaser` | B | 16,048 | STATIC_READY | 1 |
| `charmbracelet/gum` | B | 24,371 | STATIC_READY | 1 |
| `FiloSottile/age` | B | 23,579 | STATIC_READY | 4 |
| `mikefarah/yq` | B | 15,956 | STATIC_READY | 1 |
| `hadolint/hadolint` | B | 12,402 | UNSUITABLE | 0 |
| `direnv/direnv` | B | 15,445 | STATIC_READY | 1 |
| `charmbracelet/vhs` | B | 20,901 | STATIC_READY | 1 |
| `pypa/pipx` | B | 12,963 | STATIC_READY | 1 |
| `pypa/pip` | B | 10,286 | REVIEW_REQUIRED | 2 |
| `python/mypy` | B | 20,640 | STATIC_READY | 5 |
| `simonw/llm` | B | 12,505 | STATIC_READY | 1 |
| `so-fancy/diff-so-fancy` | B | 18,087 | UNSUITABLE | 0 |
| `go-task/task` | B | 16,142 | STATIC_READY | 1 |
| `pyenv/pyenv` | B | 45,101 | UNSUITABLE | 0 |
| `astral-sh/ruff` | A | 49,630 | REVIEW_REQUIRED | 0 |
| `sharkdp/bat` | A | 60,453 | REVIEW_REQUIRED | 0 |
| `BurntSushi/ripgrep` | A | 68,263 | UNSUITABLE | 0 |
| `sharkdp/fd` | A | 44,405 | REVIEW_REQUIRED | 0 |
| `starship/starship` | A | 59,899 | REVIEW_REQUIRED | 0 |
| `astral-sh/uv` | A | 89,816 | REVIEW_REQUIRED | 0 |
| `pypa/virtualenv` | C | 5,044 | STATIC_READY | 1 |
| `watchexec/watchexec` | C | 7,186 | UNSUITABLE | 0 |
| `bats-core/bats-core` | C | 6,258 | UNSUITABLE | 0 |

## Evaluation input

Selected facts use [`benchmark/ground-truth-facts-v2.json`](../../../benchmark/ground-truth-facts-v2.json) with SHA-256 `30c70ff5ef3e70f56e2ba7785e8ed571217c50cd61a06120abdcfcc2ded7f126`. Empty command paths denote root options; child options require the exact command path.

## Scan scope

Content admission is bounded independently from path enumeration. Partial scans retain unknown regions and require review, including in standalone bundle validation. Admitted text-file counts are not parser success or complete CLI coverage.

| Repository | Inventory entries | Admitted text files | Budget-excluded files | Complete within policy |
| --- | ---: | ---: | ---: | --- |
| `yt-dlp/yt-dlp` | 1235 | 1232 | 0 | True |
| `psf/black` | 482 | 480 | 0 | True |
| `Textualize/rich` | 553 | 532 | 2 | False |
| `httpie/cli` | 265 | 262 | 0 | True |
| `python-poetry/poetry` | 1009 | 922 | 0 | True |
| `prettier/prettier` | 9418 | 1971 | 7352 | False |
| `vitejs/vite` | 2820 | 2710 | 0 | True |
| `webpack/webpack` | 18719 | 2742 | 15699 | False |
| `microsoft/TypeScript` | 66541 | 2113 | 64412 | False |
| `cli/cli` | 1400 | 1342 | 1 | False |
| `gohugoio/hugo` | 2564 | 2310 | 1 | False |
| `junegunn/fzf` | 161 | 161 | 0 | True |
| `jqlang/jq` | 391 | 388 | 0 | True |
| `koalaman/shellcheck` | 90 | 87 | 0 | True |
| `nektos/act` | 423 | 414 | 0 | True |
| `pnpm/pnpm` | 7216 | 5412 | 1775 | False |
| `pytest-dev/pytest` | 707 | 698 | 0 | True |
| `pre-commit/pre-commit` | 203 | 197 | 0 | True |
| `cookiecutter/cookiecutter` | 329 | 316 | 0 | True |
| `pallets/click` | 177 | 175 | 0 | True |
| `eslint/eslint` | 2320 | 2118 | 142 | False |
| `npm/cli` | 4932 | 1541 | 3315 | False |
| `goreleaser/goreleaser` | 1185 | 1161 | 0 | True |
| `charmbracelet/gum` | 115 | 115 | 0 | True |
| `FiloSottile/age` | 97 | 95 | 0 | True |
| `mikefarah/yq` | 546 | 546 | 0 | True |
| `hadolint/hadolint` | 232 | 225 | 0 | True |
| `direnv/direnv` | 164 | 161 | 0 | True |
| `charmbracelet/vhs` | 284 | 283 | 0 | True |
| `pypa/pipx` | 218 | 217 | 0 | True |
| `pypa/pip` | 1067 | 971 | 1 | False |
| `python/mypy` | 1924 | 1924 | 0 | True |
| `simonw/llm` | 116 | 116 | 0 | True |
| `so-fancy/diff-so-fancy` | 73 | 72 | 0 | True |
| `go-task/task` | 913 | 899 | 0 | True |
| `pyenv/pyenv` | 1610 | 1607 | 0 | True |
| `astral-sh/ruff` | 10383 | 7644 | 2718 | False |
| `sharkdp/bat` | 911 | 895 | 0 | True |
| `BurntSushi/ripgrep` | 236 | 229 | 0 | True |
| `sharkdp/fd` | 60 | 59 | 0 | True |
| `starship/starship` | 816 | 778 | 1 | False |
| `astral-sh/uv` | 1741 | 1558 | 139 | False |
| `pypa/virtualenv` | 227 | 222 | 0 | True |
| `watchexec/watchexec` | 235 | 234 | 0 | True |
| `bats-core/bats-core` | 368 | 368 | 0 | True |

## Failures and review reasons

- `Textualize/rich`: NO_ACTIONABLE_CAPABILITY, SCAN_INCOMPLETE
- `prettier/prettier`: SCAN_INCOMPLETE
- `webpack/webpack`: SCAN_INCOMPLETE
- `microsoft/TypeScript`: COMMAND_CONFLICT, NO_ACTIONABLE_CAPABILITY, SCAN_INCOMPLETE
- `cli/cli`: SCAN_INCOMPLETE
- `gohugoio/hugo`: SCAN_INCOMPLETE
- `pnpm/pnpm`: COMMAND_CONFLICT, SCAN_INCOMPLETE
- `eslint/eslint`: SCAN_INCOMPLETE
- `npm/cli`: SCAN_INCOMPLETE
- `pypa/pip`: SCAN_INCOMPLETE
- `astral-sh/ruff`: NO_ACTIONABLE_CAPABILITY, SCAN_INCOMPLETE
- `sharkdp/bat`: LICENSE_MISSING, NO_ACTIONABLE_CAPABILITY
- `sharkdp/fd`: LICENSE_MISSING, NO_ACTIONABLE_CAPABILITY
- `starship/starship`: NO_ACTIONABLE_CAPABILITY, SCAN_INCOMPLETE
- `astral-sh/uv`: LICENSE_MISSING, NO_ACTIONABLE_CAPABILITY, SCAN_INCOMPLETE

## Limits

This run measures static discovery and generation only. `STATIC_READY` is not semantic correctness, runtime readiness, or agent task uplift. The ground truth remains agent-curated with zero human sign-offs; unreviewed facts are not counted as correct.
The targeted name check covers the four known Go module-suffix regressions only. Its error count is not an estimate of hallucination rate. Test/helper entrypoints are filtered by exact repository path components; role inference and Go binary-name inference remain conservative heuristics.

Raw artifacts: [`results.json`](results.json), [`ground-truth-results.json`](ground-truth-results.json), [`fact-audit.json`](fact-audit.json), [`official-comparison.json`](official-comparison.json).
