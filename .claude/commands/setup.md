---
description: First-time setup — interview the user, generate context.md, rubric.md, queries.md, and run the deep-map first scan for their market
---

Configure this radar for a new market. The machinery is generic; this command writes the *strategy brain* so the radar produces sharp, market-specific output instead of mush. Run it once, right after forking. ~10-minute interview, then a 20–30 minute (parallel) deep-map first scan.

## 1. Interview (ask these, conversationally — one or two at a time, not a wall)

Gather enough to write a strong `config/context.md` and `config/rubric.md`:

1. **What do you do?** One or two sentences: your product, your buyer, the core promise a competitor would have to threaten to count. **Get the company name and website here** if you don't already have them (run via `/onboard` and you will) — the competitor discovery in Q3 searches from that site, so without it, ask for it before going further; never infer the target from the repo or session context. **If they can't phrase the promise**, draft one from their site/product and read it back — "here's the promise I'd defend, correct it" — don't stall on a blank.
2. **What defines your lane?** The 3–5 axes that decide whether a rival actually competes with you (e.g. breadth of integration, retrieve-vs-act, vertical focus, price tier, on-prem). These become your pillars.
3. **Who competes with you — and it's completely fine not to know.** Finding them is what this radar *does*, so **don't ask them to supply a list cold.** Using the company name + website from Q1, do a quick discovery pass from its public site + a web search and present a **starter slate of 5–8 likely competitors** for them to confirm, correct, or strike. "I don't know" is the EXPECTED answer — propose, never wait for them to author the list.
4. **What's the wrong-vocabulary version of you?** The kind of company that sells your promise in different words and is easy to miss. (This becomes the canonical "don't miss this" calibration example — the whole reason the radar exists.)
5. **Vocabulary + markets.** The category terms buyers use, and any non-US regions worth watching.
6. **Your standing reads** (optional but valuable): any market theses you already hold — consolidation, what's commoditizing, where the puck is going.
7. **Brand** (for the report they read + share): their company name, and a primary accent color if they have one (hex, or just describe it — default flame `#fc4b32`). Optional: an emoji or logo URL, and light vs dark.

If the user is unsure on the rubric axes, the competitors, or the core promise, infer sensible ones from their product and confirm — never gate the run on them authoring it. The lane axes (Q2) double as the competitive map's axes — write them into `config/axes.json` (`x_axis`/`y_axis` labels) so the map reads in their language.

## 2. Generate the config (write these files)

- **`config/context.md`** — fill every section from the interview: what you do, pillars (the lane axes), standing reads, the actionability bar (keep the 2–8-week framing), and current known threats (the names from Q3).
- **`config/rubric.md`** — write tier definitions relative to *their* product, and replace the cluster set with the meaningful sub-groups of their market. Write real calibration examples using the competitors from Q3 — especially the wrong-vocabulary one from Q4.
- **`config/clusters.json`** — write your market's cluster names here. This is the single source the merge validates against, so the radar is retargeted by editing **config only — never any Python or test**. Keep these names in sync with `config/axes.json` (see the sync checklist in the axes bullet below).
- **`config/queries.md`** — replace `{competitor}`, `{category}`, `{your-product}` placeholders with their actual terms. Keep all blocks (A–I) and the two-lane structure; Block F (always-on), H (regional), and I (edge-expansion) are the recall safety net — never trim them. **Block F must keep BOTH an "alternatives" query AND a "vs" query** (e.g. `"{category} alternatives"` *and* `"vs {competitor}"`) — pytest asserts each channel separately, so rewrite the *subject* for the new market, never delete either. Leave the tuning log empty for them to grow.
- **`config/brand.json`** — set `product` to the radar's name (e.g. `"<Company> Radar"`) so the report title and eyebrow read in their brand, not the default "Pulse"; `company` to their company name (this also sets the report's "built by" credit); `accent` (and `accent_2` if they gave one); `logo` (emoji or image URL, if any); and `theme` (`light` default). This brands the report, digest, and emails — the first thing they see.
- **`config/axes.json`** — set the `x_axis`/`y_axis` `label`/`low`/`high` to their lane's two most decisive axes (from Q2). **Sync these three or the map is wrong — this is not optional:** (1) the cluster names in `config/clusters.json`, (2) the same names as `x_cluster_base`/`y_cluster_base` keys here, and (3) the axis signal regexes (`x_up`/`x_down`/`y_up`/`y_down`) rewritten to YOUR market's vocabulary — the defaults match the *old* software-AI market and **will mis-score yours, so do not ship them.** After editing, list the cluster names from all three places and confirm they match (this read-the-files check works headless and is the one that must pass; glance at the rendered map too only if you have a preview).

## 3. First scan — the deep map (recommended)

The first scan maps their whole landscape: the **full query battery in one pass** — typically **60–150 companies in dense software categories, 20–60 in leaner niches** (never promise "hundreds"). Set the time expectation up front: ~20–30 minutes run in parallel, closer to an hour sequentially.

1. Plan the full battery: `python3 scripts/plan_run.py --seed` — emits every block from `config/queries.md` (plan marked `"seed": true`) plus the known domains to dedupe against.
2. Run it. **If the surface supports subagents / parallel tasks,** fan out one researcher per query block in parallel and merge their candidates (dedupe by domain) before validation. **If it doesn't,** run the blocks sequentially and say so honestly — never quietly skip blocks to hit an estimate. Fold the known competitors from Q3 into the sweep; verify those first, they anchor the rubric's calibration.
3. **Acceptance standard — wider aperture, same bar, never a lower one:**
   - **Live evidence URL mandatory** (web fetch/search) — no URL, no entry; unverifiable-but-plausible → `watch-unconfirmed` in run notes.
   - Score every candidate against the rubric you just wrote — same tiers as any scheduled scan.
   - **`founded`/`stage`/`hq` = `unknown` unless stated on the evidence page — never inferred.** (`founded` is the *incorporation* year; a guessed year is a bug, `unknown` is honest.) For the handful of rivals they named in Q3, verify harder — those rows anchor the report. Thin profiles elsewhere are expected on day one; the `/scan` enrichment quota fills them in over the next weeks.
4. Write the results to `runs/<today>/candidates.json` (schema in `CLAUDE.md`) plus a `run_meta.json` whose `emphasized_blocks` lists every block the seed plan emitted — that stamps the coverage ledger for the whole battery.
5. Merge locally (this is an intentional local write, so set the override):
   ```bash
   RADAR_ALLOW_WRITE=1 python3 scripts/validate_merge.py --run-dir runs/<today> --runner local
   ```
6. **Decision digest** — this seed run IS the first scan, so give it a brief like any scan. Read `config/digest-spec.md`, write `runs/<today>/digest.md` in its exact format (the 0–2 most threatening entrants on the map, or the NO ACTIONABLE SIGNAL sentinel), then validate (same override as the merge — it writes `data/DIGEST.md`):
   ```bash
   RADAR_ALLOW_WRITE=1 python3 scripts/validate_digest.py --run-dir runs/<today>
   ```
7. Render: `python3 scripts/render_report.py` (optionally `RADAR_TITLE` / `RADAR_REPO` env to brand the report + links).

## 4. Verify + hand off

- Run `pip install -r requirements-dev.txt && pytest -q` — all green.
- Tell the user what was written and show how many companies landed on the map. The deep-map run you just merged + digested IS their first scan — **don't run a second `/scan` today** (a duplicate same-date run double-counts the seed and fakes the activity chart); the next scan is the next scheduled day, or whenever they ask. Proactively name the depth: the map is the full discovery sweep — what's thin on day one is metadata (`unknown` founded/HQ/stage wherever no source stated it); the scheduled `/scan`s enrich those profiles and run the status sweep that catches funding rounds and acquisitions — say it, don't wait for them to ask. Show the branded deliverable at `data/report.html` via the environment's preview panel (IDE / Cowork), `open` it on a local Mac, or summarize the digest in chat if the session is headless. Don't fail on `open`.
- **Autopilot — the GUI-only key step.** To schedule it, they add their Anthropic key as a GitHub **secret** — a web page, never a terminal or editor. Derive `<owner>/<repo>` from `git remote get-url origin` (handle both `https://github.com/owner/repo` and `git@github.com:owner/repo.git`). **If origin isn't a GitHub URL** (local path / not pushed yet), autopilot can't run until the repo is on GitHub — help them create it at `https://github.com/new` and push first, or skip autopilot for now (manual `/scan` through you stays available, key-free); never fabricate the link. Otherwise build their exact deep link:
  `https://github.com/<owner>/<repo>/settings/secrets/actions/new?name=ANTHROPIC_API_KEY`
  Tell them: open it → paste the key from console.anthropic.com → click **Add secret**. Then **you** uncomment the `schedule:` block in `.github/workflows/scan.yml` for them. (Optional secrets: `SLACK_WEBHOOK_URL`, `HEARTBEAT_URL`; emailed reports need all three of `MAIL_USER` / `MAIL_PASSWORD` / `MAIL_TO` — the send step skips quietly if any is missing.)
- Remind them: `config/context.md` is the highest-leverage file — keep it current as their strategy moves, or the digest goes stale. Keep the repo **private** if their competitor set is sensitive.
