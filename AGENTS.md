# Agent guide — Pulse

**If a human just pointed you at this repo to set it up:** run the onboarding runbook — read `.claude/commands/onboard.md` and follow it top to bottom. It configures the radar end-to-end (interview → first scan → branded report → optional autopilot) **entirely in chat**. Make every file edit yourself; never ask the user to edit files, run a terminal, or read YAML. The user may be non-technical — the chat is their interface.

## Routing
- **First-run setup** → `.claude/commands/onboard.md` (orchestrates everything below)
- Configure for a market → `.claude/commands/setup.md`
- Run one scan cycle → `.claude/commands/scan.md`

## Rules
- The system of record (`data/registry.csv`, `data/SCANLOG.md`, `data/state.json`, `data/DIGEST.md`, the `data/LANDSCAPE.md` changelog) is written **only by the scripts** — never hand-edit it.
- Full hard rules, output schemas, and key files: see `CLAUDE.md`.
- The deliverable is `data/report.html` (rendered by `scripts/render_report.py`) — branded from `config/brand.json`.
