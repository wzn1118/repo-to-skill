# Repo-to-Skill Benchmark Run

**Run:** `2026-09-15-upgrade-v6`  
**High-Star Public Repositories Tested:** 36  
**Core cumulative GitHub stars:** 1,453,404  
**Compiler fingerprint:** `2e06c783eeb7e6dd9c6da79cd9360e19e7c054735d04eaa17caff87c3293c14e`

This report is a versioned static compiler run. It does not reuse runtime, model A/B, or official comparison results from another compiler fingerprint.

| Metric | Value |
| --- | ---: |
| Core outcomes | 26 STATIC_READY / 36 |
| Core REVIEW_REQUIRED | 3 |
| Core UNSUITABLE | 7 |
| Star-weighted repository coverage | 69.74% |
| Emitted executable facts | 49 |
| Hash + commit verified facts | 49 |
| Selected source facts covered | 9 / 40 |
| Generated facts awaiting full semantic review | 49 |
| Four legacy binary-name regressions corrected | 4 / 4 |

## Outcomes

| Repository | Tier | Stars | Status | Bundles |
| --- | --- | ---: | --- | ---: |
| `yt-dlp/yt-dlp` | A | 191,182 | STATIC_READY | 1 |
| `psf/black` | A | 41,842 | STATIC_READY | 2 |
| `Textualize/rich` | A | 57,363 | UNSUITABLE | 0 |
| `httpie/cli` | A | 38,512 | STATIC_READY | 3 |
| `python-poetry/poetry` | A | 34,304 | STATIC_READY | 1 |
| `prettier/prettier` | A | 52,263 | STATIC_READY | 1 |
| `vitejs/vite` | A | 82,823 | STATIC_READY | 3 |
| `webpack/webpack` | A | 65,948 | REVIEW_REQUIRED | 0 |
| `microsoft/TypeScript` | A | 111,047 | REVIEW_REQUIRED | 0 |
| `cli/cli` | A | 46,279 | STATIC_READY | 1 |
| `gohugoio/hugo` | A | 89,819 | STATIC_READY | 1 |
| `junegunn/fzf` | A | 82,984 | STATIC_READY | 1 |
| `jqlang/jq` | A | 35,598 | UNSUITABLE | 0 |
| `koalaman/shellcheck` | A | 40,036 | UNSUITABLE | 0 |
| `nektos/act` | A | 72,004 | STATIC_READY | 1 |
| `pnpm/pnpm` | A | 36,524 | REVIEW_REQUIRED | 4 |
| `pytest-dev/pytest` | B | 14,506 | STATIC_READY | 2 |
| `pre-commit/pre-commit` | B | 15,572 | STATIC_READY | 1 |
| `cookiecutter/cookiecutter` | B | 25,087 | STATIC_READY | 1 |
| `pallets/click` | B | 17,665 | UNSUITABLE | 0 |
| `eslint/eslint` | B | 27,506 | STATIC_READY | 1 |
| `npm/cli` | B | 10,114 | STATIC_READY | 3 |
| `goreleaser/goreleaser` | B | 16,048 | STATIC_READY | 1 |
| `charmbracelet/gum` | B | 24,371 | STATIC_READY | 1 |
| `FiloSottile/age` | B | 23,579 | STATIC_READY | 4 |
| `mikefarah/yq` | B | 15,956 | STATIC_READY | 1 |
| `hadolint/hadolint` | B | 12,402 | UNSUITABLE | 0 |
| `direnv/direnv` | B | 15,445 | STATIC_READY | 1 |
| `charmbracelet/vhs` | B | 20,901 | STATIC_READY | 1 |
| `pypa/pipx` | B | 12,963 | STATIC_READY | 1 |
| `pypa/pip` | B | 10,286 | STATIC_READY | 2 |
| `python/mypy` | B | 20,640 | STATIC_READY | 5 |
| `simonw/llm` | B | 12,505 | STATIC_READY | 1 |
| `so-fancy/diff-so-fancy` | B | 18,087 | UNSUITABLE | 0 |
| `go-task/task` | B | 16,142 | STATIC_READY | 1 |
| `pyenv/pyenv` | B | 45,101 | UNSUITABLE | 0 |
| `astral-sh/ruff` | A | 49,630 | REVIEW_REQUIRED | 0 |
| `sharkdp/bat` | A | 60,453 | REVIEW_REQUIRED | 0 |
| `BurntSushi/ripgrep` | A | 68,263 | UNSUITABLE | 0 |
| `sharkdp/fd` | A | 44,405 | REVIEW_REQUIRED | 0 |
| `starship/starship` | A | 59,899 | UNSUITABLE | 0 |
| `astral-sh/uv` | A | 89,816 | REVIEW_REQUIRED | 0 |
| `pypa/virtualenv` | C | 5,044 | STATIC_READY | 1 |
| `watchexec/watchexec` | C | 7,186 | UNSUITABLE | 0 |
| `bats-core/bats-core` | C | 6,258 | UNSUITABLE | 0 |

## Limits

This run measures static discovery and generation only. `STATIC_READY` is not semantic correctness, runtime readiness, or agent task uplift. The ground truth remains agent-curated with zero human sign-offs; unreviewed facts are not counted as correct.
The targeted name check covers the four known Go module-suffix regressions only. Its error count is not an estimate of hallucination rate. Test/helper entrypoints are filtered by exact repository path components; role inference and Go binary-name inference remain conservative heuristics.

Raw artifacts: [`results.json`](results.json), [`ground-truth-results.json`](ground-truth-results.json), [`fact-audit.json`](fact-audit.json), [`official-comparison.json`](official-comparison.json).
