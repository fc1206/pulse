# Pulse

> ### 🤖 New here? Tell **Claude Code**, **Codex**, or **Cowork** to *"clone https://github.com/fc1206/pulse and onboard me."*
> Cloning a public repo needs no GitHub login and works on any surface. To keep your radar, click **"Use this template"** on GitHub first and clone *your* copy instead. The agent handles the rest in chat. The only thing you ever do by hand is paste an API key into a GitHub page, and only if you want autopilot.
> *(Assistant says the repo is "private" or 404s? That's its GitHub connector, not the repo. Tell it to `clone` the URL.)*
>
> **Not technical?** Read **[USING-PULSE.md](USING-PULSE.md)**, the plain-English guide. Pulse is free. You pay only your own AI usage, about $5–15/mo on autopilot, nothing if you run it by hand.

A competitor radar you own. A small repo plus an AI agent that scans the web twice a week, keeps a deduped, tiered database of your competitors, and tells you what changed and what to do about it. Runs in Claude Code, Codex, or any assistant that can run `/scan`, and schedules itself with GitHub Actions.

_Built by the team at [Astell](https://www.astell.ai)._

Not a one-shot "analyze my competitors" prompt. Pulse accumulates across runs, dedupes by domain, flags new entrants, funding, acquisitions, and pivots, and ends each scan with a short decision digest backed by an anti-slop validator. The model only does the narrow judgment (find and score). Deterministic Python does everything that touches the record, which is why it runs on any model.

## What a scan produces

1. **`data/registry.csv`** is your competitor database. 14 fields per company, evidence-grade `what` and `why_tier`, and a required live evidence URL.
2. **`data/LANDSCAPE.md`** is the narrative read. A top-5 threat assessment, tiered cluster maps, market theses, and a dated changelog.
3. **`data/DIGEST.md`** is the decision layer. Each finding gives a signal, why it matters, and a specific dated action. The validator rejects uncited claims and lazy "monitor closely" items.

Plus a self-contained `data/report.html` dashboard and a per-run audit trail in `runs/`.

## Quick start

**The easy way (recommended).** Click "Use this template" on GitHub, open your new repo in **Claude Code** or **Codex**, and say *"onboard me"* (or run `/onboard`). The agent interviews you, maps your landscape in one deep first scan (typically 60–150 companies in a dense category, 20–60 in a leaner niche), and shows you a branded report. You add an API key later only if you want autopilot.

**Prefer to drive it yourself?**
1. **Use this template** on GitHub.
2. **Teach it your market.** Run `/setup`, a ~10-minute interview that writes `config/context.md`, `config/rubric.md`, `config/queries.md`, `config/brand.json`, and your market's `config/clusters.json` + `config/axes.json`, then runs the deep-map first scan. `config/context.md` is the highest-leverage file. The sharper the lane, the sharper the brief.
3. **From then on, `/scan` on later days.** The deep map was your first scan, so don't run a second one the same day. Each scan searches, scores against your rubric, merges into the registry, writes the digest, and renders `data/report.html`.
4. **Autopilot (optional).** Add `ANTHROPIC_API_KEY` as a repo secret (Settings → Secrets and variables → Actions), then uncomment the `schedule:` block in `.github/workflows/scan.yml`. Scheduling ships OFF so a fresh fork never fails before it has a key. Optional extras are `SLACK_WEBHOOK_URL`, `HEARTBEAT_URL`, and emailed reports via `MAIL_USER`/`MAIL_PASSWORD`/`MAIL_TO` (the send step skips quietly if any is missing).

## How it stays trustworthy

- **One canonical writer.** Only the scripts write the system of record. Both `validate_merge.py` and `validate_digest.py` refuse to write unless they run on GitHub Actions or you pass `RADAR_ALLOW_WRITE=1` for an intentional, pull-first local run. Parallel runners can't silently diverge the registry.
- **Every company needs a live evidence URL.** No URL, no entry.
- **Anti-slop digest.** The validator rejects uncited claims, banned filler phrases, and lazy actions.
- **Tested machinery.** `pip install -r requirements-dev.txt && pytest -q` (Python 3.10+).

## Notes

- Defaults (tiers, clusters, query blocks) are tuned for software and AI markets. Retarget yours by editing config only. Set your clusters in `config/clusters.json` and tune `config/rubric.md`, never Python or tests.
- Cost is roughly the model plus web-search spend of two scans a week, typically $5–15 a month on the default model (a few dollars on a cheaper one, set via a `SCAN_MODEL` repo variable).
- Requires Python 3.10+. Stock macOS ships 3.9, so install a current Python from python.org first.
- MIT licensed, provided as-is. A template to build on, not a supported product.
