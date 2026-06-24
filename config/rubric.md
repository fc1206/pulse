# Scoring Rubric

> **Fill this in for your product.** Replace the placeholder below with one or two sentences on what you do and the axes that define your lane. The sharper this is, the sharper every `why_tier` and digest the radar produces. (`/setup` can draft it from a short interview.)

**<YOUR PRODUCT>** = <one-line definition: what you do, for whom, across what>. The axes that define your lane: <e.g. breadth of integration, retrieve-vs-act, vertical focus — the things that decide whether a rival actually competes with you>.

## Tiers

**Tier 1 — same lane.** A prospect could plausibly say "we're choosing between this and us." Same core promise, same buyer. Include incumbent features that now do what you do.

**Tier 2 — adjacent, one pivot away.** Same promise in a different vocabulary or perimeter, or a tool that would be Tier 1 with one positioning change or 2–3 added capabilities. Watch for the pivot.

**Tier 3 — context only.** Single-feature point tools, pure infrastructure, or vertical-bounded plays that touch your space but don't compete for your buyer.

**When torn between two tiers, pick the higher (more threatening) one.** A false positive costs a minute of reading; a miss is what this radar exists to prevent.

## Clusters

Default set (edit `CLUSTERS` in `scripts/validate_merge.py` to match your market):

`direct` | `chief-of-staff` | `data-intel` | `incumbent` | `employee-assist` | `infra` | `vertical`

Rename these to the meaningful sub-groups of YOUR market (e.g. for a payments product: `processors`, `orchestration`, `fraud`, `ledger`, `incumbent`, `vertical`). Keep the enum in `validate_merge.py` in sync.

## Calibration examples (replace with your own — these are neutral stubs)

- **<A direct rival>** → Tier 1 / direct. Same product, same buyer.
- **<A wrong-vocabulary rival>** → Tier 2 / data-intel. Sells your promise in different words; the class that's easiest to miss. (Make this one real and specific — it's your canonical "don't miss this" calibration.)
- **<An agent/platform rival>** → Tier 1 / direct. Different vocabulary, same mechanics. Vocabulary never overrides mechanics.
- **<A bounded analyst tool>** → Tier 2 / data-intel.
- **<A single-feature tool>** → Tier 3 / infra or vertical.
- **<A wedge product trending toward you>** → Tier 1. Trajectory counts, not just today's perimeter.

## Source quality & evidence

Precision is about what gets *registered*, never about what gets *considered* — a low-footprint, non-US, or wrong-vocabulary company is exactly what you exist to catch, so breadth of consideration stays wide. Once considered, hold registered entries to higher evidence:

- **Prefer primary evidence:** the company's own site, its YC / Crunchbase / LinkedIn page, or a named funding announcement. Listicles and "top 10" roundups are lead generation only — use them to find names, then verify against a primary source before registering.
- **Lift the exact domain** from the funding-DB / press page rather than guessing a homepage.
- **Thin / unverifiable but plausible → `watch-unconfirmed`** in `run_meta.json` notes, not a registry row. No live evidence URL, no entry.
- **Region is not a tier signal.** Score on mechanics only.

## What does NOT belong in the registry

Pure model providers, tutorials, agencies/consultancies, open-source libraries without a company, products with no working website AND no funding/launch evidence (note them as `watch-unconfirmed` instead).
