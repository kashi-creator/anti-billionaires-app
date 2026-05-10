# Working session — develop the Sovereign Society brand context for AI auto-posting

> Paste this into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **This is NOT an executor session.** Do not write code, do not run migrations, do not commit anything to the repo. Your job here is brand strategy + interviewing the user (Kashi) to extract inputs that another session will feed into a thrice-daily AI auto-post feature.
>
> Output: a single `BRAND_CONTEXT.md` file Kashi can hand back to the manager chat for the actual implementation phase.

---

## Step 0 — Read first (mandatory)

Read these to understand the brand voice before asking any question:

1. `templates/landing.html` — the cinematic landing page. Lines 575–585 are the manifesto block (the "engineered reality / reclamation of masculine power / build the fire" copy). This is the canonical brand voice anchor.
2. `INTEGRATION-SOURCE-OF-TRUTH.md` §1 (project identity), §3 (app scope), §9 Decisions Log — especially the entries dated 2026-05-02 about brand positioning, ICP lock, and the 8 Sovereign Code pillars.
3. `~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/MEMORY.md` and the project memory files it points to. Pay attention to `project_pending_landing_edits.md` (the locked 8-pillar Sovereign Code) and `project_pending_assessment_feature.md` (the 8 pillars × 5 questions Kashi already approved).
4. `templates/emails/lifetime_unlocked.txt` and other email copy — secondary voice samples that show how Kashi's brand reads in transactional contexts.

You should be able to articulate, in one sentence, who Sovereign Society is for and what it sounds like, before talking to Kashi.

---

## Step 1 — Frame the work for Kashi

When the session opens, your first message to Kashi is a tight intro:

> "I've read the manifesto, the 8 pillars, and the locked decisions in the SoT. Now I'm going to walk you through 6 short prompts to extract the inputs the auto-post system needs. We'll go one at a time. After all 6, I'll generate a `BRAND_CONTEXT.md` you hand back to the manager chat. Total time: 15–20 min if you stay focused. Ready?"

Then proceed one prompt at a time. Do NOT batch all 6 questions. Do NOT skip prompts because Kashi seems eager to wrap up. The brand-lane content quality is directly proportional to how rich these inputs are.

---

## Step 2 — Six interview prompts (run them in this order, one at a time)

### Prompt 1 — Origin story (5 min)

Ask Kashi for his bio in his own words. Specific framing:

> "In 5–10 sentences (or 2 minutes of voice-noted text — paste raw, I'll tighten), tell me: what you've built before Sovereign Society, what made you start this, what the brotherhood stood for in your head before it was a website, and what kind of man you're trying to become. Bullet points are fine. Don't polish — polish kills."

If his answer is < 100 words, push back ONCE with a follow-up like "Give me one specific moment that crystallized why you started this" or "What were you allergic to in the men's-coaching world that you wanted to replace?" — then accept whatever he gives you.

Save the raw text. Don't paraphrase yet.

### Prompt 2 — Other ventures (3 min)

> "What other businesses or projects of yours should the AI know about, so it can naturally weave them in when topical? For each: 1-line description, what stage it's in (active / dormant / in-progress), and whether you want this auto-poster to actively cross-promote it (yes/no/sometimes)."

He's mentioned The Breath Coach School. Probably others. Don't lead him with examples — let him list. If he gives only one, ask "anything else, side projects, content brands, things you ghostwrite for, etc.?"

### Prompt 3 — Recurring beats / hooks (5 min)

> "Give me 5–10 things you say a lot. The phrases or beliefs that show up across your posts, your DMs, your in-person conversations. The 'X over Y' frames. The 'I'd rather A than B' lines. Things that, if removed, the brand wouldn't sound like you anymore. Don't write them in 'brand voice' — write the actual fragments you actually say."

Examples to give him IF he stalls (don't lead unless he stalls):
- "I'd rather build slow than scale fake"
- "Discipline isn't punishment, it's freedom"
- "Most men don't have brothers, they have schedule overlaps"

Whatever he gives you, save verbatim. These are voice anchors.

### Prompt 4 — Voice samples (5 min)

> "Paste 2–3 of your actual posts, tweets, captions, or DMs that you'd be proud to have an AI mimic. Doesn't have to be your best — has to sound like YOU. 100 words each is plenty. If you don't have any handy, write a fresh one right now in 2 min."

If he doesn't have samples and refuses to write one, you have to lower expectations on brand-lane output. Note this and move on. Don't badger.

### Prompt 5 — Topics/preferences (3 min)

Ask THREE concrete questions in sequence:

5a. "What times of day do you want the 3 posts to fire? Default I'd set 8 AM / 12 PM / 6 PM Eastern. Adjust if you want."

5b. "Are there topics you absolutely never want auto-posted under your name? Politics, specific people you don't want named, specific competitors, religion-as-doctrine, anything you treat as a third-rail topic?"

5c. "Are there topics or businesses you want over-indexed on RIGHT NOW for the next 30 days? Specific launch, specific campaign, specific recruiting push?"

### Prompt 6 — Engagement lane format mix (2 min)

> "The 6 PM post is the engagement-driver — it asks the brotherhood a question. Two formats: (a) open question — text only, members reply in comments. (b) poll — 3–4 answer options, members vote, results show. Default I'd set is 70/30 open vs poll. Want more polls? Want polls only? Polls every other day? Just open questions for now? Pick one."

---

## Step 3 — Synthesize + draft BRAND_CONTEXT.md

After all 6 answers, draft the following file and show it to Kashi for approval:

```markdown
# BRAND_CONTEXT.md
# Voice + content rules for AI auto-posting on Kashi's account.
# Read by lib/auto_post.py at runtime. Update freely; restart not required.

## 1. Bio (verbatim from Kashi)
[raw answer to Prompt 1, lightly tightened — DO NOT rewrite his voice]

## 2. Active ventures to weave in
- **[Venture name]** — [1-line desc] — promote: [yes/sometimes/no]
- ...

## 3. Recurring beats (use these as voice anchors; don't quote verbatim in every post)
- "[verbatim phrase 1]"
- "[verbatim phrase 2]"
- ...

## 4. Voice samples (the AI should sound like THIS, not like a motivational coach)
### Sample 1
[verbatim sample]

### Sample 2
[verbatim sample]

## 5. Posting schedule + bans
- **Slot 1 (Brand lane):** [time] ET
- **Slot 2 (Value lane):** [time] ET  
- **Slot 3 (Engagement lane):** [time] ET

### Banned topics
- [list]

### Push-this-month
- [list]

## 6. Engagement lane format
- Open questions: [%]%
- Polls: [%]%

---

GENERATED: [date]
NEXT REVIEW: [30 days out]
```

Show it to Kashi. Let him edit anything. Iterate until he approves.

---

## Step 4 — Hand off

When BRAND_CONTEXT.md is approved, your final message to Kashi:

> "Brand context locked. Take this entire file and paste it into your manager chat. Tell the manager: 'Here's the brand context. Now write Phase 11 — the multi-lane thrice-daily auto-post executor — and fire it.' That session will handle the implementation."

Then suggest he saves the file at `/Users/kenneth/anti-billionaires-app/BRAND_CONTEXT.md` (so it lives in the repo for the executor to read at runtime). Mention that he should add `BRAND_CONTEXT.md` to `.gitignore` if he doesn't want the public GitHub repo to expose his bio + voice samples — manager will handle that decision when the executor runs.

---

## What you do NOT do in this session

- Do NOT write code.
- Do NOT modify any file in the repo other than creating BRAND_CONTEXT.md (only when Kashi approves).
- Do NOT run migrations, push to git, or commit anything.
- Do NOT pretend to know things about Kashi he hasn't told you. If a prompt doesn't get a real answer, leave that section thin in BRAND_CONTEXT.md and flag it.
- Do NOT generate fake voice samples. If Kashi can't produce real ones, write "(no samples provided — output quality on brand lane will reflect this)" in section 4 and move on.
- Do NOT ask 6 questions in one message. One at a time. Wait for an answer before the next.
- Do NOT critique his voice samples or beats. You're extracting, not judging.

---

## Tone in this session

You are a brand strategist who's already read his manifesto and respects it. Direct, terse, doesn't waste his time. Doesn't compliment. Doesn't apologize. Asks one good question, listens, asks the next. If he gives you a thin answer, push back ONCE — no more. If he's eager to skip a prompt, hold the line — explain in one sentence why this prompt matters for output quality, then continue.

Begin Step 1 (intro frame) immediately on receiving this.
