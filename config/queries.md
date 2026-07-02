# Query Battery

Edit freely — this file is the harness's search brain. `scripts/plan_run.py` parses block IDs from `## Block X:` headers; keep that format (one capital letter, then a colon — extra text after the colon is fine). `{competitor}`, `{category}`, `{year}`, `{month}` are placeholders you fill with your own market's terms (or let `/setup` write them for you).

**Two lanes, tuned independently so precision never costs breadth:**

- **Lane 1 — precision (Blocks A–E, G):** source-targeted queries that reliably surface real companies. Favor `site:` and named venues; lift exact domains from result pages.
- **Lane 2 — recall safety-net (Block F always-on + Block H regional + Block I edge-expansion):** the wide net that catches low-footprint, wrong-vocabulary, non-US entrants — the costly-miss class. This lane is *allowed* to be noisy; that's its job. **Never trim it for cleanliness.** **Retirement rule:** a recall query that returns only already-tracked companies is the net *holding*, not saturation — retire a Lane-2 or wildcard query only when it returns nothing in-lane at all across two consecutive runs.

**Per run:** Block F always (pick ~4) + the two emphasized blocks from `plan_run.py` (pick ~5 each) + 2 wildcards you compose + the status sweep. `plan_run.py` emits a coverage ledger and flags any block gone stale; fold the stalest into a wildcard. Breadth is guaranteed by cadence + the ledger, not per-run volume.

**Tuning log (append one dated lesson per run):**
- (empty — add lessons as you learn which query classes over/under-perform for your market)

## Block A: category vocabulary — Lane 1

- {category} startup {year}
- {category} platform new company
- "{category}" software competitors

## Block B: data vocabulary — Lane 1

- conversational BI startup {year}
- AI data analyst startup
- enterprise data intelligence platform
- "chat with your data" startup

## Block C: workflow / assistant vocabulary — Lane 1

- AI assistant for {category} teams
- AI agent for {category} startup
- proactive AI tool {category}

## Block D: agent / platform vocabulary — Lane 1

- {category} AI agent platform startup
- "all your tools" {category} assistant
- multiplayer AI agents {category}

## Block E: architectural primitives — Lane 1

- "{category}" graph OR layer startup
- {category} memory layer enterprise
- {category} context platform funding

## Block F: lookalikes + alternatives + ego (Lane 2 — ALWAYS RUN)

- {competitor} alternatives {year}
- {competitor} competitors {year}
- "vs {competitor}" comparison page
- best {category} tools {year}
- {your-product} alternative   ← ego search; anyone comparing against you

## Block G: funding + launch venues — Lane 1 (source-targeted)

- site:producthunt.com {category}
- site:producthunt.com/products {category}   ← product pages persist after launch feeds rotate; a company that launches once gets exactly one window in the feeds
- site:news.ycombinator.com Show HN {category}
- {category} seed OR "series A" raised {month} {year}
- {category} acquisition OR acquired {year}

## Block H: geographic / non-US (Lane 2 — recall; rotate one region per run)

A wrong-vocabulary, no-funding, non-US company is invisible to generic + US-funding search. Rotate the region across runs.

- {category} startup Australia OR New Zealand {year}
- {category} startup India OR Singapore {year}
- {category} startup Europe OR UK OR Germany {year}
- {category} startup Israel {year}
- LinkedIn "launched globally" OR "now live" {category} (no funding/press)   ← catches social-only launches

## Block I: edge-expansion (Lane 2 — recall; harvest the competitor sets others publish)

Every player maps its own rivals. Compare-list directories and competitors' own `/alternatives` pages name companies your keyword queries never reach. **Tailor the sources to your category** — the lines below default to SaaS directories, but agencies and dev shops live on Clutch and Behance, AI tools on theresanaiforthat, open source on GitHub/awesome-lists: swap in the directories your market actually uses (`/setup` should rewrite these for you).

- site:g2.com {competitor} OR {category} alternatives OR compare
- site:capterra.com OR site:sourceforge.net {category} alternatives {year}
- "alternatives to" {competitor} (-site:g2.com)
- {competitor}/alternatives OR /vs — fetch the competitor's own comparison page and harvest every rival it names
- crunchbase OR tracxn "similar companies" {category}
- {category} self-hosted OR "private cloud" OR on-prem OR "in your VPC"   ← deployment-model axis; established players who sell on *how it deploys* are invisible to feature vocabulary
- site:theresanaiforthat.com OR "AI tools directory" {category} alternatives   ← directories index companies whose launch window has closed

## Status sweep (every run)

For each of the ~8 round-robin targets from `plan_run.py`:
- `"{name}" funding OR acquired OR acquisition OR shutdown OR pivot {year}`

Material changes (new round, acquisition, death, repositioning) → `status_updates.json`.

**Re-find probe (1 per run):** pick one tracked Tier-1 (rotate); read its live homepage vocabulary, then check whether at least one battery query would still surface it today. If none would, add a query in its *current* vocabulary to the matching block and log it in the tuning log. Companies reposition after you register them — this catches the drift before it becomes a silent recall hole.

## Known noise — skip fast (NOT a block; do not re-evaluate unless trajectory changes)

(Add confirmed out-of-lane tools here as you find them, so you stop re-litigating them each run.)
