# Digest Spec — the anti-slop contract

The digest answers one question: **given this run's findings, what should we do differently?** It is derived against `config/context.md` and structurally enforced by `scripts/validate_digest.py` (the only writer of `data/DIGEST.md`).

## Process

1. After a successful merge, read: `config/context.md`, this run's findings (candidates, status updates, scan notes), and the 3 most recent entries in `data/DIGEST.md` (novelty check).
2. Apply the actionability bar from the context file. Most findings are registry-worthy but NOT digest-worthy. That's correct.
3. Write `runs/<date>/digest.md`, then run `python3 scripts/validate_digest.py --run-dir runs/<date>`. Fix and retry on failure (max 2).

## Format (exact)

```
## YYYY-MM-DD — digest (runner)

### 1. <sharp, specific headline — a claim, not a topic>
**Signal:** <the fact, with an http link or a (registry-domain)>
**Why it matters:** <tie to a specific pillar, standing read, or actionable lane from config/context.md>
**Action:** <imperative, concrete, 2–8-week-shaped, names a deliverable or decision>
```

0–5 items. Zero findings → a single line after the header: `NO ACTIONABLE SIGNAL — <one honest line on why this run's findings don't clear the bar>`. This outcome is respected; forced items are not.

## Hard rules (linted)

- Every item carries a citation: an http link or a registry domain.
- Actions start with a doing-verb and a deliverable. Banned action-openers: monitor, watch, consider, keep, continue, stay, track, explore.
- No re-issuing a prior digest's action without stating what NEW evidence changed.
- Banned phrases (entry rejected): rapidly evolving, ever-changing, landscape is shifting, it's worth noting, stay vigilant, keep an eye, monitor closely, monitor the situation, double down, in conclusion, game-chang, cutting-edge, synerg, best-in-class, world-class, delve, underscores the, highlights the importance, top of mind going forward, actionable insights.
- Entry ≤ 6000 chars. Specificity beats coverage — two sharp items beat five mushy ones.

## Quality test before submitting

Read each Action and ask: could you assign this to a person today, and would they know what done looks like? If no, cut or sharpen it.
