# AGENTS.md

Entire is already configured for this repository. Use it as intended for AI-agent work.

- Keep `.entire/` and `.codex/` tracked. They are part of the repo's AI workflow.
- Do not reinstall, re-enable, or regenerate Entire configuration unless explicitly asked.
- Use Entire checkpoints and history as the source of truth for prior AI-agent work.
- Use `entire status` to understand the current tracking state.
- Use `entire doctor` when hooks, checkpoints, or session tracking appear unhealthy.
- Use the `entire-search` Codex agent or `entire search --json` for historical questions about prior sessions, prompts, commits, or checkpoints.
- Do not use interactive `entire search`; prefer machine-readable `--json` output.
- Treat `.serena/` as local workspace metadata and keep it out of git.
