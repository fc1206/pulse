# Pulse

**Keep your finger on your market's pulse.** A competitor radar you **own** — a small repo + Claude that scans the web on a schedule, maintains a deduped, tiered database of your competitors, and tells you **what changed and what to do about it**. Runs in Claude Code (or any assistant that can run the `/scan` command); schedules itself twice a week with GitHub Actions for a few dollars a month.

_Built by the team at [Astell](https://astell.space)._

Not a one-shot "analyze my competitors" prompt and not an API wrapper — a *maintained system*: it accumulates across runs, dedupes by domain, flags new entrants / funding / acquisitions / pivots, and writes a sharp, anti-slop decision digest. Built to run on any model, because the model only does the narrow judgment (find + score) and deterministic Python does everything else.

## What a scan produces

1. **`data/registry.csv`** — your competitor database. 14 fields per company, with paragraph-grade `what` / `why_tier` / `notes` and a required live evidence URL.
2. **`data/LANDSCAPE.md`** — the narrative read: a top-5 threat assessment, tiered cluster maps, market theses, and a dated changelog.
3. **`data/DIGEST.md`** — the decision layer: per finding, Signal → Why it matters → a specific, dated Action, with an anti-slop validator that rejects uncited claims and lazy "monitor closely" actions.

Plus a self-contained `data/report.html` dashboard and a per-run audit trail in `runs/`.

## Quick start

1. **Use this template** (fork / "Use this template" on GitHub). Set `ANTHROPIC_API_KEY` (and optionally `SLACK_WEBHOOK_URL`, `HEARTBEAT_URL`) as repo secrets.
2. **Teach it your market.** Two options:
   - **Fast (~15 min):** run `/setup` in Claude Code. It interviews you about your product and competitors and writes `config/context.md`, `config/rubric.md`, `config/queries.md`, and a seed registry for you.
   - **Manual (~an afternoon):** fill in those three config files yourself. They are the strategy brain — the sharper they are, the sharper the output. `config/context.md` is the highest-leverage file.
3. **Run a scan:** `/scan` in Claude Code. It searches, scores against your rubric, merges into the registry, writes the digest, and renders the report.
4. **Put it on autopilot (optional):** the included GitHub Actions workflow can run the scan twice a week, commit the results, and (if configured) post the digest to Slack. **Scheduling ships OFF** so a fresh fork doesn't fail before it has a key — once `ANTHROPIC_API_KEY` is set and your first `/scan` looks good, **uncomment the `schedule:` block** at the top of `.github/workflows/scan.yml` (adjust the cron) to go live.

## How it stays trustworthy

- **One canonical writer.** Only the scripts write the system of record, and `validate_merge.py` refuses to write unless it's the canonical runner (GitHub Actions) or you pass `RADAR_ALLOW_WRITE=1` for an intentional, pull-first local run. This prevents parallel runners from silently diverging the registry.
- **Every company needs a live evidence URL** — no URL, no entry.
- **Anti-slop digest** — the validator rejects uncited claims, banned filler phrases, and lazy actions.
- **Tested machinery** — `pip install -r requirements-dev.txt && pytest -q`.

## Notes

- Defaults (tiers, clusters, query blocks) are tuned for software / AI markets. Adjust `config/rubric.md` (and the `CLUSTERS` enum in `scripts/validate_merge.py`) for yours.
- Cost is roughly the model + web-search spend of two scans a week — typically single-digit dollars a month.
- MIT licensed, provided as-is. This is a template to build on, not a supported product.
