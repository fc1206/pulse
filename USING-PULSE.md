# Pulse — your own competitor radar

*A free, open-source product. This is the plain-English guide to what it is, how you set it up, and what it costs **you**.*

---

## What it is

Pulse is a competitor radar you **own**. It watches your market, keeps a tidy, tiered database of every competitor, and twice a week hands you a short brief: **what changed, and what to do about it.**

It isn't a website you log into or a subscription you pay us for. It's a small project that lives in **your** GitHub account and is run by an AI assistant you already use (Claude Code, Codex, or Cowork — if you have one of those, there's nothing else to install). You talk to it in plain English; it does all the technical work for you. No code to write, no spreadsheets to maintain. Works on Mac and Linux (on Windows, ask your assistant to set it up under WSL).

Think of it as hiring a junior analyst who never sleeps, never forgets a competitor, and costs a few dollars a month instead of a salary.

## What you actually get

A single, branded dashboard (a web page) that shows:

- **What changed & what to do** — the one or two things that moved this week (a new entrant, a funding round, an acquisition, a pivot) with a specific action for each — or an honest "no actionable signal" when nothing did. This is the part you read first.
- **The competitive map** — every rival placed by how broad and how active they are, so you can see who's crowding into your space.
- **A spotlight** on the most important new competitor, with their funding, stage, location, and what makes them a threat.
- **The full list** — a searchable table of every competitor, each with a live link to a source so you can trust it.

Every claim is sourced to a real link. No made-up numbers.

## Getting started (about 15 minutes of your attention, no technical skill)

1. **Get your own copy.** On the Pulse page, click **"Use this template."** One important click on that screen: **choose "Private"** — GitHub preselects Public, and your competitor list belongs in a private repo. *(You'll need a free GitHub account — like an email signup.)*
2. **Have your assistant clone *your copy* and onboard you.** In Claude Code, Codex, or Cowork, say: **"clone `<your copy's URL from step 1>` and onboard me."** Your copy is **private**, so your assistant needs your GitHub login connected — most assistants ask once, in their settings. If it says "404" or "can't find the repo," that's the signal to connect GitHub, not a problem with the repo. *(Want a look around before committing? The original at `https://github.com/fc1206/pulse` is public and clones with no login at all — but don't build your real radar there: setup stops you early, because you can't save a radar to a repo you don't own.)*
3. **Answer a few questions in the chat** — what your company does, who you compete with, what your market is called. The assistant writes everything for you, then maps your whole landscape: your first scan runs the full search battery — typically 60–150 companies in a dense category, 20–60 in a leaner niche — in about 20–30 minutes. Go get a coffee; the map is waiting when you're back.
4. **Read your first brief.** That's it — you have a working radar.

You never open a code editor, a terminal, or a settings file. The chat is the whole interface.

## The one manual step (only if you want it on autopilot)

The first scan runs for free through your AI assistant. If you want Pulse to keep scanning **on its own, twice a week**, it needs a key to your AI account. This is the **only** thing you do by hand, and it's a normal web page — never a terminal:

- The assistant gives you a **direct link** to a GitHub settings page. The secret's name is **`ANTHROPIC_API_KEY`** — the link usually pre-fills it, but if the Name box arrives empty, type exactly that.
- You paste your key (from **console.anthropic.com** → API Keys), click **Add secret**, and tell your assistant *"the key is in."* ~30 seconds.

Two things must be true before it runs on its own, and your assistant does both the moment you say the key is in: it **switches the schedule on** and **lands your setup on the main branch**. Pasting the key alone doesn't start anything — so if you added the key on your own some other day, just tell your assistant *"turn on autopilot"* and it finishes the job. After that, the radar runs itself twice a week. If you'd rather just run it by hand whenever you feel like it, you can skip this entirely.

## Using it week to week

- **On autopilot:** it scans Monday and Thursday, and each scan posts the brief as a **GitHub issue** in your repo — GitHub emails it to you automatically, so the radar comes to you without any extra setup. (Prefer Slack or a nicely formatted email? Ask your assistant to wire either — both are optional upgrades.)
- **Seeing the dashboard:** say *"open my radar report"* to your assistant — it opens `data/report.html` from your repo. (GitHub's website shows that file as code rather than as a page — your assistant is the viewer.)
- **By hand:** open your assistant and say *"run a scan"* anytime — it researches, walks you through what it found, and files the results so the record stays clean.
- **Keep it sharp:** when your strategy shifts, tell the assistant — it updates the radar's focus so the briefs stay relevant.

## What it costs *you*

**Pulse is free and open-source (MIT license).** There's no fee to us — ever. Your only cost is the AI usage, and you're in control of it.

| How you run it | What it costs |
|---|---|
| **By hand, in your AI assistant** | Nothing extra — it uses the Claude Code / Codex plan you already have. No separate key, no bill. A scan is a heavy session, so on lower-tier plans run it in an hour you weren't going to use the assistant anyway. |
| **On autopilot (twice a week)** | Your own AI-usage spend, typically **~$10–30 / month** on the default model (each scan writes its exact cost into the run's `usage.log`, so you can check rather than guess). The computer that runs it (GitHub Actions) is **free** at this volume. |

**You can dial the cost down:**
- Switch to a cheaper, faster model → roughly **a few dollars a month**.
- Scan once a week instead of twice → about **half** the cost.
- Track a smaller, sharper set of competitors → cheaper *and* more useful.

There are no per-seat fees, no minimums, and no surprise charges — you're paying your AI provider directly for the few minutes of work each scan takes, nothing more.

## Privacy

Your radar lives in **your** GitHub account, and the dashboard is a file in your own repository. Keep the repository **private** (step 1's "Private" click) and your competitor list, your strategy, and your notes stay entirely yours. Pulse never publishes anything publicly, and nothing leaves your repo unless you turn on the optional Slack or email delivery — otherwise it's files in your repo, full stop.

## In one line

> Fork it, say "onboard me," answer a few questions, and you have a private, branded, self-updating competitor radar for the price of a couple of coffees a month — or free if you just run it yourself.
