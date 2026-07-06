# Digest Spec — the anti-slop contract

The digest answers one question: **given this run's findings, what should we do differently?** It is derived against `config/context.md` and structurally enforced by `scripts/validate_digest.py` (the only writer of `data/DIGEST.md`).

## Process

1. After a successful merge, read: `config/context.md`, this run's findings (candidates, status updates, scan notes), and the 3 most recent entries in `data/DIGEST.md` (novelty check).
2. Apply the actionability bar from the context file. Most findings are registry-worthy but NOT digest-worthy. That's correct.
3. Write `runs/<date>/digest.md`, then run `python3 scripts/validate_digest.py --run-dir runs/<date>`. Fix and retry on failure (max 2). Non-CI runs need `RADAR_ALLOW_WRITE=1` for BOTH `validate_merge.py` and `validate_digest.py` — neither writes without it.

## Format (exact)

```
## YYYY-MM-DD — digest (runner)

### 1. <sharp, specific headline — a claim, not a topic>
**Signal:** <the fact, with an http link or a (registry-domain)>
**Why it matters:** <tie to a specific pillar, standing read, or actionable lane from config/context.md>
**Action:** <imperative, concrete, 2–8-week-shaped, names a deliverable or decision>
```

(If `config/brand.json` sets `why_label`, that exact label replaces `**Why it matters:**` above — the validator lints for the branded label, so use it verbatim.)

0–2 items. Zero findings → a single line after the header: `NO ACTIONABLE SIGNAL — <one honest line on why this run's findings don't clear the bar>`. This outcome is respected; forced items are not. The sentinel is the EXPECTED output when nothing clears the bar — a digest history that never fires it is a calibration smell, not a success.

## Hard rules (linted)

- Every item carries a citation: an http link or a registry domain.
- Actions start with a doing-verb and a deliverable. Banned action-openers: monitor, watch, consider, keep, continue, stay, track, explore.
- No re-issuing a prior digest's action without stating what NEW evidence changed.
- Banned phrases (entry rejected): rapidly evolving, ever-changing, landscape is shifting, it's worth noting, stay vigilant, keep an eye, monitor closely, monitor the situation, double down, in conclusion, game-chang, cutting-edge, synerg, best-in-class, world-class, delve, underscores the, highlights the importance, top of mind going forward, actionable insights.
- Entry ≤ 6000 chars. Specificity beats coverage — one sharp item beats two mushy ones.

## Action ledger

Every accepted item's `**Action:**` line is logged to `data/ACTIONS.md` by `scripts/validate_digest.py` (the ledger's only writer — never hand-edit) as `<entry-date>.<item-n> | open | due <YYYY-MM-DD or -> | <excerpt>`. The due date is parsed from a literal "by YYYY-MM-DD" in the action text, so write deadlines that way. Close the loop when an action is acted on (or consciously dropped):

- `RADAR_ALLOW_WRITE=1 python3 scripts/validate_digest.py --resolve <id> --status done|dropped|deferred [--note "..."]`
- `RADAR_ALLOW_WRITE=1 python3 scripts/validate_digest.py --backfill` re-extracts from all of `data/DIGEST.md`, idempotently.

These are local, human-run commands — they always need the `RADAR_ALLOW_WRITE=1` override (the write gate refuses otherwise).

Unresolved rows are unconsumed intelligence — review them before writing the next digest.

## Quality test before submitting

Read each Action and ask: could you assign this to a person today, and would they know what done looks like? If no, cut or sharpen it.
