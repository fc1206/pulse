---
description: First-time setup — interview the user and generate context.md, rubric.md, queries.md, and a seed registry for their market
---

Configure this radar for a new market. The machinery is generic; this command writes the *strategy brain* so the radar produces sharp, market-specific output instead of mush. Run it once, right after forking. ~15 minutes.

## 1. Interview (ask these, conversationally — one or two at a time, not a wall)

Gather enough to write a strong `config/context.md` and `config/rubric.md`:

1. **What do you do?** One or two sentences: your product, your buyer, the core promise a competitor would have to threaten to count.
2. **What defines your lane?** The 3–5 axes that decide whether a rival actually competes with you (e.g. breadth of integration, retrieve-vs-act, vertical focus, price tier, on-prem). These become your pillars.
3. **Who do you already know competes with you?** Names + domains if they have them — direct rivals, adjacent tools, and the incumbent everyone compares against. Get 3–10.
4. **What's the wrong-vocabulary version of you?** The kind of company that sells your promise in different words and is easy to miss. (This becomes the canonical "don't miss this" calibration example — the whole reason the radar exists.)
5. **Vocabulary + markets.** The category terms buyers use, and any non-US regions worth watching.
6. **Your standing reads** (optional but valuable): any market theses you already hold — consolidation, what's commoditizing, where the puck is going.
7. **Brand** (for the report they read + share): their company name, and a primary accent color if they have one (hex, or just describe it — default flame `#fc4b32`). Optional: an emoji or logo URL, and light vs dark.

If the user is unsure on the rubric axes, infer sensible ones from their product description and confirm. The lane axes (Q2) double as the competitive map's axes — write them into `config/axes.json` (`x_axis`/`y_axis` labels) so the map reads in their language.

## 2. Generate the config (write these files)

- **`config/context.md`** — fill every section from the interview: what you do, pillars (the lane axes), standing reads, the actionability bar (keep the 2–8-week framing), and current known threats (the names from Q3).
- **`config/rubric.md`** — write tier definitions relative to *their* product, and replace the cluster set with the meaningful sub-groups of their market. **If you change the clusters, update the `CLUSTERS` enum in `scripts/validate_merge.py` and the cluster list in `CLAUDE.md` to match** (they must agree or the merge will reject rows). Write real calibration examples using the competitors from Q3 — especially the wrong-vocabulary one from Q4.
- **`config/queries.md`** — replace `{competitor}`, `{category}`, `{your-product}` placeholders with their actual terms. Keep all blocks (A–I) and the two-lane structure; Block F (always-on), H (regional), and I (edge-expansion) are the recall safety net — never trim them. Leave the tuning log empty for them to grow.
- **`config/brand.json`** — set `company` to their company name, `accent` (and `accent_2` if they gave one), `logo` (emoji or image URL, if any), and `theme` (`light` default, or `dark`). This brands the report, digest, and emails — the first thing they see.
- **`config/axes.json`** — set the `x_axis`/`y_axis` `label`/`low`/`high` to their lane's two most decisive axes (from Q2) so the competitive map reads in their market's language, not the software-AI defaults. Tune the signal keyword lists if you have time; the defaults are a reasonable start.

## 3. Seed the registry (optional but recommended)

Turn the known competitors from Q3 into the first registry rows so the radar starts non-empty:
1. For each known competitor, verify a live evidence URL (web fetch/search) and score it against the rubric you just wrote. Only register ones with a real URL; note unverifiable ones as `watch-unconfirmed`.
2. Write them to `runs/<today>/candidates.json` (schema in `CLAUDE.md`) plus a `run_meta.json`.
3. Merge locally (this is an intentional local write, so set the override):
   ```bash
   RADAR_ALLOW_WRITE=1 python3 scripts/validate_merge.py --run-dir runs/<today> --runner local
   ```
4. Render: `python3 scripts/render_report.py` (optionally `RADAR_TITLE` / `RADAR_REPO` env to brand the report + links).

## 4. Verify + hand off

- Run `pip install -r requirements-dev.txt && pytest -q` — all green.
- Tell the user what was written and show the seed count. Then run `/scan` for a full sweep (you run it for them — no key needed) and `python3 scripts/render_report.py` to build the branded deliverable at `data/report.html` — show it via the environment's preview panel (IDE / Cowork), `open` it on a local Mac, or summarize the digest in chat if the session is headless. Don't fail on `open`.
- **Autopilot — the GUI-only key step.** To schedule it, they add their Anthropic key as a GitHub **secret** — a web page, never a terminal or editor. Build their exact deep link from `git remote get-url origin`:
  `https://github.com/<owner>/<repo>/settings/secrets/actions/new?name=ANTHROPIC_API_KEY`
  Tell them: open it → paste the key from console.anthropic.com → click **Add secret**. Then **you** uncomment the `schedule:` block in `.github/workflows/scan.yml` for them. (Optional secrets: `SLACK_WEBHOOK_URL`, `HEARTBEAT_URL`.)
- Remind them: `config/context.md` is the highest-leverage file — keep it current as their strategy moves, or the digest goes stale. Keep the repo **private** if their competitor set is sensitive.
