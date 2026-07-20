---
description: Run one competitive-landscape scan cycle (search → score → merge → digest → log)
---

Run one radar cycle. Follow exactly; budgets are caps, not targets.

## 1. Plan

```bash
python3 scripts/plan_run.py
```

Gives you: `run_date`, `emphasized_blocks`, `status_targets` (~8 companies), `known_domains`, and the **coverage ledger** (`coverage` + `stale_coverage` — blocks not swept within the staleness window). Create `runs/<run_date>/`. Read `config/queries.md` and `config/rubric.md`.

## 2. Discovery sweep (≤16 WebSearch calls)

Run: 4 queries from Block F (always) + ~5 from each emphasized block + 2 wildcard queries you compose yourself (base them on the tuning log and anything notable from recent changelog entries; fill `{year}`/`{month}` with today's values).

If `plan_run.py` reported `stale_coverage`, spend at least one of your 2 wildcards on the stalest block or region listed — that's how breadth stays guaranteed run-to-run.

From results, collect candidate companies — actual companies with domains, not articles or features. Ignore anything whose normalized domain is in `known_domains`. Recognize and skip the "Known noise" list at the bottom of `config/queries.md` without spending fetch budget on it.

## 3. Verify + score (≤10 WebFetch calls)

For each net-new candidate: WebFetch its homepage (or its YC/press page if the site is JS-empty). Confirm it's real and what it does. Score per `config/rubric.md` — mechanics over vocabulary, higher tier when torn. Only Tier 1/2 candidates and notable Tier 3 (funded infra in our pillars) go in `candidates.json`. Unverifiable-but-plausible → `run_meta.json` notes as `watch-unconfirmed`.

**Metadata discipline (the registry's accuracy depends on this):** lift `founded`/`stage`/`hq` from a **primary** source, never an aggregator guess or the most salient year on the page. `founded` is the *incorporation* year — **not** the YC batch (F25 ≠ 2025), first-funding, OSS-launch, or rebrand year. Founding-year conflation is the most common data-entry error in this class of registry. No primary founding-year source → write `unknown`.

**Verify harder for Tier 1 (these are the rows that matter):** for every Tier-1 candidate, make a genuine attempt to confirm `stage`/`hq`/`founded`/funding from a primary source before writing the row — only record `unknown` after trying, never as a default. A Tier-1 row with three blank fields is a half-finished entry; spend the fetch on it.

## 4. Status sweep + field re-audit (≤8 WebSearch calls; ≤16 under the enrichment quota)

One query per `status_target` (template at the bottom of `config/queries.md`). Two jobs per target: **(a) material events** — funding round, acquisition, shutdown, pivot toward/away from the lane; **(b) field correctness** — while the primary source is open, confirm `founded`/`stage`/`hq` against it. Either a material change *or* a confirmed field error → `status_updates.json`. This is the **only correctness re-audit the registry gets** — write-once ingest means a wrong field is otherwise never caught. No change → nothing.

**Enrichment quota (thin-profile backfill):** while more than 25% of registry rows have a thin profile (`founded`, `stage`, or `hq` = `unknown`), the re-audit covers up to **16 rows per run** instead of the normal 8 — after the `status_targets`, spend the extra queries on the thinnest rows not already covered, Tier 1/2 first. Confirmed fields go in `status_updates.json` like any re-audit hit; same sourcing bar (primary source or `unknown` stands). A deep-map seed trades metadata depth for breadth on day one; this quota is how those rows earn their fields back. At ≤25% thin, the normal 8 applies.

## 5. Write outputs

`runs/<run_date>/candidates.json`, `status_updates.json` (omit if empty), `run_meta.json` — schemas in `CLAUDE.md`. Set `runner` to `github` if running in CI (the `GITHUB_ACTIONS` env var is set), else `local`.

## 6. Merge

```bash
python3 scripts/validate_merge.py --run-dir runs/<run_date> --runner <runner>
```

If it fails: fix the JSON per its errors, re-run (max 2 retries, then write `runs/<run_date>/FAILED.md` and stop). On success it updates the registry, LANDSCAPE changelog, SCANLOG, state, and writes `ESCALATION.md` if a Tier 1 appeared.

## 7. Decision digest (judgment step — read the contract first)

Read `config/context.md` + `config/digest-spec.md` + the 3 most recent entries in `data/DIGEST.md`. Apply the actionability bar to THIS run's findings. Write `runs/<run_date>/digest.md` in the spec's exact format (0–2 items, or the NO ACTIONABLE SIGNAL sentinel). Then:

```bash
python3 scripts/validate_digest.py --run-dir runs/<run_date>
```

If rejected, fix per its errors and re-run (max 2 retries; if still failing, write the errors to `runs/<run_date>/digest-FAILED.md` and continue — a missing digest must not kill the scan). The validator prepends accepted entries to `data/DIGEST.md`; never edit that file directly.

## 8. Render

```bash
python3 scripts/render_report.py
```

## 9. Learn (optional, encouraged)

If a query class clearly over/under-performed, append one dated line to the tuning log in `config/queries.md`.

## 10. Finish

- **CI (GitHub Actions):** stop here — the workflow commits, pushes, notifies Slack, and opens any escalation issue. **This is the only runner that writes `main`.**
- **Local:** do NOT commit or merge to `main`. Both `validate_merge.py` and `validate_digest.py` refuse to write unless `RADAR_ALLOW_WRITE=1` (the single-writer guard that stops parallel runners from diverging the registry — see CLAUDE.md rule 7). A local run is for testing only; let GitHub Actions produce the canonical scan. If you must reconcile, `git pull` then union through `validate_merge.py` with `RADAR_ALLOW_WRITE=1`, never `git reset`.
  **Manual-mode exception:** if the repo has NO active schedule (the `schedule:` block in `.github/workflows/scan.yml` is still commented out), there is no parallel runner to diverge from — you are the only writer, exactly like the seed scan. A pull-first `RADAR_ALLOW_WRITE=1` merge and push is sanctioned in that mode, so a no-autopilot user's manual scans genuinely persist. The moment autopilot is enabled, this exception ends and CI is the sole writer again.

Never edit `data/registry.csv`, `data/SCANLOG.md`, `data/state.json`, `data/DIGEST.md`, or the LANDSCAPE changelog by hand — only the scripts write those.
