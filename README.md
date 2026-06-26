# Pulse

> ### 🤖 Just forked this? Open it in **Claude Code**, **Codex**, or **Cowork** and say *"onboard me"* (or run `/onboard`).
> The agent sets everything up **in chat** — a 10-minute interview, your first scan, and a branded report — and makes every file edit for you. The only thing you ever do by hand is paste an API key into a GitHub web page, and only if you want it to run on autopilot. **No terminal, no YAML.**
>
> **Not technical?** Read **[USING-PULSE.md](USING-PULSE.md)** — the plain-English guide: what you get, the 15-minute setup, and what it costs *you* (it's free; you pay only your own AI usage, ~$5–15/mo on autopilot or nothing if you run it by hand).

**Keep your finger on your market's pulse.** A competitor radar you **own** — a small repo + an AI agent that scans the web on a schedule, maintains a deduped, tiered database of your competitors, and tells you **what changed and what to do about it**. Runs in Claude Code, Codex, or any assistant that can run the `/scan` command; schedules itself twice a week with GitHub Actions for a few dollars a month.

_Built by the team at [Astell](https://astell.space)._

Not a one-shot "analyze my competitors" prompt and not an API wrapper — a *maintained system*: it accumulates across runs, dedupes by domain, flags new entrants / funding / acquisitions / pivots, and writes a sharp, anti-slop decision digest. Built to run on any model, because the model only does the narrow judgment (find + score) and deterministic Python does everything else.

## What a scan produces

1. **`data/registry.csv`** — your competitor database. 14 fields per company, with paragraph-grade `what` / `why_tier` / `notes` and a required live evidence URL.
2. **`data/LANDSCAPE.md`** — the narrative read: a top-5 threat assessment, tiered cluster maps, market theses, and a dated changelog.
3. **`data/DIGEST.md`** — the decision layer: per finding, Signal → Why it matters → a specific, dated Action, with an anti-slop validator that rejects uncited claims and lazy "monitor closely" actions.

Plus a self-contained `data/report.html` dashboard and a per-run audit trail in `runs/`.

## Quick start

**The easy way (recommended):** "Use this template" on GitHub → open your new repo in **Claude Code** or **Codex** → say *"onboard me"* (or run `/onboard`). The agent interviews you, runs your first scan, and shows you a branded report — all in chat, no files touched. You only add an API key (one GitHub web page) when you want it to run on autopilot.

**Prefer to drive it yourself?**
1. **Use this template** (fork on GitHub).
2. **Teach it your market** — run `/setup` (a ~10-min interview that writes `config/context.md`, `config/rubric.md`, `config/queries.md`, `config/brand.json`, and a seed registry) or fill those files in by hand. `config/context.md` is the highest-leverage file: the sharper the lane, the sharper the brief.
3. **Run a scan:** `/scan` — searches, scores against your rubric, merges into the registry, writes the digest, and renders `data/report.html`.
4. **Autopilot (optional):** add `ANTHROPIC_API_KEY` as a repo secret (Settings → Secrets and variables → Actions), then **uncomment the `schedule:` block** in `.github/workflows/scan.yml`. **Scheduling ships OFF** so a fresh fork never fails before it has a key. Optional: `SLACK_WEBHOOK_URL`, `HEARTBEAT_URL`.

## How it stays trustworthy

- **One canonical writer.** Only the scripts write the system of record, and `validate_merge.py` refuses to write unless it's the canonical runner (GitHub Actions) or you pass `RADAR_ALLOW_WRITE=1` for an intentional, pull-first local run. This prevents parallel runners from silently diverging the registry.
- **Every company needs a live evidence URL** — no URL, no entry.
- **Anti-slop digest** — the validator rejects uncited claims, banned filler phrases, and lazy actions.
- **Tested machinery** — `pip install -r requirements-dev.txt && pytest -q`.

## Notes

- Defaults (tiers, clusters, query blocks) are tuned for software / AI markets. Adjust `config/rubric.md` (and the `CLUSTERS` enum in `scripts/validate_merge.py`) for yours.
- Cost is roughly the model + web-search spend of two scans a week — typically single-digit dollars a month.
- MIT licensed, provided as-is. This is a template to build on, not a supported product.
