from r2s.domain import ClientProfile

PORTABLE_PROFILE = ClientProfile("portable-agent-skills-v1", "portable", "1")
CODEX_PROFILE = ClientProfile("codex-plugin-skills-2026-09", "codex", "1", "1")
CLIENT_PROFILES = {
    "portable": PORTABLE_PROFILE,
    "codex": CODEX_PROFILE,
    "claude": ClientProfile("claude-skills-v1", "claude", "1"),
    "cursor": ClientProfile("cursor-skills-v1", "cursor", "1"),
}
