---
description: First-run onboarding. Sets this radar up end-to-end from one command, right after forking. Run this if someone just pointed you at the repo.
---

# Onboard

You are setting this competitor radar up for a new owner who may be **non-technical**. Do **everything for them in this chat** — never tell them to edit a file, run a terminal command, or read YAML. Be warm, brief, concrete. One or two questions at a time, never a wall.

## 0. Welcome + confirm this is a real setup
Tell them what they're getting: *a private competitor radar they own — it scans the web twice a week, keeps a tiered, deduped database of their competitors, and hands them a short "what changed → what to do" brief.* Say you'll ask a few quick questions and build it live, right now.

Before touching anything, set the frame in plain words — don't skip this:
- **Check the delivery reality first.** Before promising any in-repo edits, confirm the working folder is actually **writable** — not just that a repo exists. A read-only clone or sandbox can pass `git rev-parse --is-inside-work-tree` and still reject every write. Check write permission *without mutating anything* (e.g. `[ -w "$(git rev-parse --show-toplevel)" ]` — a filesystem permission test; don't create throwaway files or branches before the user has agreed to set up). Check `git remote -v` too, for autopilot in step 3. Say which case you're in, plainly, before doing any work:
  - **Writable repo:** "I'll make every change directly in your repo, on a branch you can review or undo."
  - **Read-only or no folder (sandbox, restricted clone, nothing connected):** say so honestly and recover **without a terminal** — "I can't write to your repo from this session. Connect your repo's folder (or reopen it in a writable workspace) and say 'onboard me' again — then I make every edit for you, no terminal. Want a no-save preview first? I can build the report and show it without writing anything." Never let the "edits in your repo" promise stand when writes will fail here, and never fall back to asking a non-technical user to run a push or other CLI command (it breaks the no-terminal promise).
- **This writes into their repo.** Onboarding generates config files and a **seed registry** (their first batch of competitors) *into this repository*. Confirm they want a real setup now, not just a look around. If they're only exploring, stop here and offer to walk them through it instead.
- **The repo is theirs — branch first.** Recommend they let you work on a branch (e.g. `onboarding`) so the changes are easy to review or undo. The repo is theirs to keep, edit, or discard.
- **Set expectations.** This is a **quick onboarding scan to get them started — not an exhaustive market audit.** Some metadata (founding year, HQ, funding) may come back `unknown` when no primary source confirms it; that's honest, not broken, and later scans fill gaps. And a scan you run for them here is a **one-off local scan — not the scheduled GitHub Actions autopilot** (that's the optional last step). Say "first scan" or "seed scan," never "full scan."

## 0.5 Name the target — STOP until confirmed
Before any web research, any question round, or `/setup`, establish **which company or product this radar is for**. This is the single most expensive thing to get wrong.
- **Ask, in one line:** "What's the company or product this radar is for? Give me its name and website."
- **Never infer the target** from the repo name, open files, loaded skills, or anything earlier in this session. The repo a fresh forker opens is the generic template — it tells you nothing about their company, and a guess from session context is exactly how onboarding ends up researching the wrong company. Don't volunteer a guess; ask.
- **Do not run any search, fetch, or `/setup` step until they answer.** This gate is a hard stop. Everything downstream — the competitor discovery inside `/setup` — keys off the company they name here, not anything you assumed.

## 1. Interview + configure + seed → run `/setup`
Execute the `/setup` command in full: interview them about their company, lane, and known competitors; capture their **brand** (company name, accent color); and write `config/context.md`, `config/rubric.md`, `config/queries.md`, `config/brand.json`, and a seed registry.
**`config/context.md` is the highest-leverage file** — a vague lane produces a useless brief. Push for sharpness: the exact promise a rival must threaten, the 3–5 axes that decide who competes, and the *wrong-vocabulary* competitor they're most likely to miss.

**The seed registry `/setup` writes IS their first scan.** It's a real, dated scan run (`runs/<today>/`) — verified, merged, and digested like any other scan. Don't run a second `/scan` today — that would create a duplicate same-date run, double-count the seed, and make the activity chart look like a fake ramp. One run today, labeled as the seed/first scan. The next real scan happens on the next scheduled day (Mon/Thu under autopilot), or whenever they ask you to run `/scan` again — not minutes from now.

This first scan uses **your own model access** (you, the agent, are running it), so they get a real result **without setting up any key or secret**.

## 2. Show them the payoff
Render the deliverable:
```bash
python3 scripts/render_report.py
```
`data/report.html` is their dashboard. **Surface it however the environment allows:** an IDE or **Cowork preview panel** shows the HTML automatically; on a local Mac you can `open data/report.html`. If you're in a headless / cloud session with no preview, that's fine — don't fail on `open`. Either way, walk them through the **digest** in one short paragraph: the 1–3 things worth their attention from this seed/first scan and what to do about each, and tell them the dashboard lives at `data/report.html` (and updates every scan). Be honest about scope — this is their starting set, not a finished market map; later scans deepen it. This is the moment they understand the product — make it land.

**Name the seed for what it is — proactively, before they ask.** In one line: "This is a **seed scan** — a fast first pass covering the most likely rivals, not yet the full sweep. A full `/scan` widens discovery (regional, edge, and roundup channels) and runs the status sweep that catches funding rounds and acquisitions; ask me to run one on the next scheduled day and each scan deepens it." Don't make them ask "was that the full thing?"

## 3. Autopilot — the one manual step, and it's a GUI
For the radar to run itself twice a week it needs their Anthropic API key stored as a GitHub **secret**. This is the only thing they do by hand, and it is a **graphical web page — never a terminal or text editor**:
1. Get their repo from `git remote get-url origin` and derive `<owner>/<repo>` — handle both `https://github.com/owner/repo(.git)` and `git@github.com:owner/repo.git`. **If origin is not a GitHub URL** (a local path, or they haven't pushed the repo to GitHub yet), autopilot can't run — GitHub Actions needs the repo on GitHub first. Offer to help them create it at `https://github.com/new` and push, or skip autopilot for now (they keep running `/scan` through you, key-free). Never fabricate the link from a non-GitHub origin.
2. Give them this exact deep link (GitHub's secrets GUI, name pre-filled):
   `https://github.com/<owner>/<repo>/settings/secrets/actions/new?name=ANTHROPIC_API_KEY`
   Tell them: open it → paste their key from **console.anthropic.com** (Settings → API Keys) → click **Add secret**. ~30 seconds.
3. Once they confirm it's added, **you** enable the schedule for them: uncomment the `schedule:` block at the top of `.github/workflows/scan.yml` and commit. From then on it runs Mon/Thu on its own.
- If they're not ready for autopilot, that's fine — they can run `/scan` manually anytime, key-free, through you.

## 4. Done — recap
Summarize: their radar is set up (N competitors in the seed/first scan, here's this scan's brief in one line), what happens next — if they added the key, autopilot scans Mon/Thu on its own; if not, it stays a manual `/scan` through you and the scheduled autopilot isn't running yet — and the one habit that keeps it sharp: keep `config/context.md` current as their strategy moves. Privacy note: keep the repo **private** if their competitor set is sensitive; the report is a local file, not published anywhere unless they choose to.
