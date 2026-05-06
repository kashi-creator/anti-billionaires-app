#!/usr/bin/env python3
"""
seed_placeholders.py — Phase 0B (Sovereign Society)

Seeds the empty community with 8 placeholder "Founding Voice" users + posts +
wins + deals + resources + 1 active weekly challenge + RSVPs on canonical
events. Also performs a one-time cleanup of legacy 6 Spaces / 5 Events from a
pre-rebrand seed run.

USAGE
-----
    # Standard run: cleanup legacy + seed placeholders + wire cover images
    python seed_placeholders.py

    # Idempotent — running again is a no-op (no duplicates, no errors)
    python seed_placeholders.py

    # Clean wipe — removes all placeholder users, posts, etc. AND the
    # generated images at static/img/seed/
    python seed_placeholders.py --delete

DEV LOGIN (for the manager to test in browser)
----------------------------------------------
    Email:    seed.<slug>@sovereign.placeholder
              (slugs: marcus-w, james-r, sean-t, brendan-m, kyle-h,
                      anders-l, chase-w, david-k)
    Password: ChangeBeforeLaunch_2026!

    DO NOT ship this file to a paid-traffic environment with the
    placeholders intact. Run --delete first.
"""

import argparse
import os
import secrets
import sys
from datetime import date, datetime, timedelta

import bcrypt

from app import app, db
from models import (
    Deal,
    Event,
    EventRSVP,
    Post,
    Resource,
    ResourceUpvote,
    Space,
    User,
    Win,
    WeeklyChallenge,
    ChallengeSubmission,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEV_SEED_PASSWORD = "ChangeBeforeLaunch_2026!"
SEED_EMAIL_DOMAIN = "@sovereign.placeholder"
SEED_BIO_FOOTER = "— Founding Voice (pre-launch seed account)"

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SEED_IMG_DIR = os.path.join(REPO_ROOT, "static", "img", "seed")
LEGACY_UPLOADS_DIR = os.path.join(REPO_ROOT, "static", "uploads")

LEGACY_SPACE_NAMES = [
    "The Vault",
    "Business Strategy Room",
    "Networking Lounge",
    "Investment Club",
    "Wellness & Health",
    "Creator's Corner",
]
LEGACY_EVENT_NAMES = [
    "Weekly Mastermind Call",
    "Monthly Networking Mixer",
    "Guest Speaker: AI Automation",
    "Deal Flow Friday",
    "Wellness Workshop: Peptide Protocols",
]
LEGACY_PNG_FILES = [
    "space-the-vault.png",
    "space-business-strategy.png",
    "space-networking-lounge.png",
    "space-investment-club.png",
    "space-wellness-health.png",
    "space-creators-corner.png",
]

CANONICAL_SPACE_NAMES = [
    "Sovereign Wealth",
    "Body & Iron",
    "Awake Minds",
    "Business Directory",
    "The Arsenal",
    "The Hidden Truth",
    "Family & Legacy",
    "Off Grid",
]

SPACE_SLUG = {
    "Sovereign Wealth": "sovereign-wealth",
    "Body & Iron": "body-iron",
    "Awake Minds": "awake-minds",
    "Business Directory": "business-directory",
    "The Arsenal": "arsenal",
    "The Hidden Truth": "the-hidden-truth",
    "Family & Legacy": "family-legacy",
    "Off Grid": "off-grid",
}

CANONICAL_EVENT_COVERS = {
    "Fire to Fire - St. Pete": "img/seed/event-fire-to-fire.png",
    "Sovereign Wealth Workshop": "img/seed/event-sovereign-wealth-workshop.png",
    "Brotherhood Summit": "img/seed/event-brotherhood-summit.png",
}

WIN_COVER = "img/seed/cover-win.png"
DEAL_COVER = "img/seed/cover-deal.png"


# ---------------------------------------------------------------------------
# Placeholder user definitions
# ---------------------------------------------------------------------------

USERS = [
    {
        "slug": "marcus-w",
        "name": "Marcus W.",
        "city": "Austin, TX",
        "country": "USA",
        "lat": 30.27, "lng": -97.74,
        "points": 5400, "streak": 31,
        "days_ago": 78,
        "bio": (
            "Real-estate operator out of Austin. Twelve years in multifamily, "
            "the last four building a Sun Belt portfolio one off-market deal at "
            "a time. Left the W-2 ladder at thirty-three after watching the "
            "house I grew up in get bought for cash by a fund nobody could "
            "name. Built my way out. Still building. The room I want to be in "
            "is full of operators who close — not seminar tourists, not "
            "podcast clones. Brothers who actually move. Capital allocation, "
            "discipline, fatherhood, and the long game. I'm here to give and "
            "to take. Come correct.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "james-r",
        "name": "James R.",
        "city": "Miami, FL",
        "country": "USA",
        "lat": 25.76, "lng": -80.19,
        "points": 4200, "streak": 22,
        "days_ago": 65,
        "bio": (
            "Macro investor. Twenty years watching central banks lie and "
            "calling it research. Now I run my own book — hard assets, "
            "energy, sound money. Left New York for Miami in 2021 and never "
            "looked back. The men I want around me read first-source "
            "primaries, not legacy headlines. They sit with hard truths "
            "instead of voting them away. They've earned a seat at the table "
            "by surviving cycles, not by collecting credentials. If that's "
            "you, I'm glad you're here. We've got work to do, and the window "
            "to do it in is shorter than most of us pretend.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "sean-t",
        "name": "Sean T.",
        "city": "Coeur d'Alene, ID",
        "country": "USA",
        "lat": 47.68, "lng": -116.78,
        "points": 3100, "streak": 41,
        "days_ago": 60,
        "bio": (
            "Strength and nutrition coach. Trained Division I athletes for a "
            "decade before I figured out the weakest men in the country are "
            "not the ones in the weight room — they're the ones who never "
            "stepped foot in one. I write programs, I cook for my family, "
            "and I run a small private gym in Coeur d'Alene. The body is the "
            "first empire. Get that right and the rest of your life listens. "
            "Get it wrong and nothing else you build will hold weight. I'm "
            "here to help any brother who actually wants the reps.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "brendan-m",
        "name": "Brendan M.",
        "city": "Nashville, TN",
        "country": "USA",
        "lat": 36.16, "lng": -86.78,
        "points": 1700, "streak": 18,
        "days_ago": 52,
        "bio": (
            "General contractor, third-generation builder. Custom homesteads, "
            "barns, off-grid cabins — anything with land and good bones. "
            "Spent fifteen years swinging hammers and the last six running "
            "the crew. Two boys, one dog, twelve acres outside Nashville. "
            "I joined this room because the men who want what I want are "
            "scattered across the country and most days the only ones I see "
            "in real life are at the lumber yard. We need a place to compare "
            "notes — what worked, what burned us, who's worth a referral. "
            "I'm here for that.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "kyle-h",
        "name": "Kyle H.",
        "city": "Jackson, WY",
        "country": "USA",
        "lat": 43.48, "lng": -110.76,
        "points": 820, "streak": 9,
        "days_ago": 41,
        "bio": (
            "Commodities trader. Started on the energy desk at twenty-three "
            "and never left. I read the data the press doesn't want you to "
            "see — and I trade it. Now living in Jackson with my wife, two "
            "rifles, and a satellite uplink. The thesis is simple: physical "
            "things matter again. Land, energy, food, people who can do hard "
            "work with their hands. I want a brotherhood that takes that "
            "thesis seriously and is positioned for it. Less talk, more "
            "stacking.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "anders-l",
        "name": "Anders L.",
        "city": "Bozeman, MT",
        "country": "USA",
        "lat": 45.68, "lng": -111.04,
        "points": 320, "streak": 5,
        "days_ago": 34,
        "bio": (
            "Hardware engineer. Spent a decade designing power-management "
            "silicon for companies you'd recognize, then quit to build my "
            "own — off-grid energy monitoring for cabins and small farms. "
            "Pre-revenue, post-prototype, very-much-figuring-it-out. Bozeman "
            "is good for that. Quiet, cold, full of men who solve real "
            "problems. I'm here to learn from operators ten years ahead of "
            "me and to show up for the brothers building behind me. I lift "
            "five days a week. I read every night. I hold my son before he "
            "knows what gravity is.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "chase-w",
        "name": "Chase W.",
        "city": "Asheville, NC",
        "country": "USA",
        "lat": 35.60, "lng": -82.55,
        "points": 2400, "streak": 26,
        "days_ago": 71,
        "bio": (
            "Three businesses, three kids, one wife, one mountain. Run a "
            "small landscaping company, a real-estate holding LLC, and an "
            "online education brand for fathers. The income is good. The "
            "calendar is harder. I am here because the men I knew at "
            "twenty-five are not the men I want my sons around at fifteen, "
            "and the path between then and now does not draw itself. I want "
            "brothers who treat fatherhood as the main event, not a side "
            "quest. The Society is the closest thing I've seen to that, and "
            "I'm in for the long haul.\n\n" + SEED_BIO_FOOTER
        ),
    },
    {
        "slug": "david-k",
        "name": "David K.",
        "city": "New York, NY",
        "country": "USA",
        "lat": 40.71, "lng": -74.01,
        "points": 1200, "streak": 12,
        "days_ago": 47,
        "bio": (
            "Tech founder. Two exits, one fintech I'm building now. Born and "
            "raised in Brooklyn, still here, still skeptical of every man who "
            "tells me he doesn't watch the news. I read the news so I can "
            "trade against it. The sovereign-pilled angle on tech is "
            "underrated — the same tools that are being used against us are "
            "the tools we'll use to route around them. I want builders in my "
            "circle, not commentators. If you're shipping something I should "
            "know about, send me the link. I'll tell you what's wrong with "
            "it and then I'll tell you why I'm rooting for it.\n\n" + SEED_BIO_FOOTER
        ),
    },
]


# ---------------------------------------------------------------------------
# Post seed content (16 = 8 spaces × 2)
# ---------------------------------------------------------------------------

POSTS = [
    # ---------------- Sovereign Wealth ----------------
    ("Sovereign Wealth", "marcus-w",
     "Why I rotated 30% out of brokerage accounts last quarter",
     """Pulled the trigger on a structural rotation in October. Thirty percent of liquid net worth out of taxable brokerage accounts and into a mix of self-directed IRA real-estate (Sun Belt MF), physical metals stored in two non-bank depositories, and a small allocation to a Wyoming LLC holding raw land in two states.

The trigger was not the market. It was jurisdiction. I sat down with my CPA and my estate attorney in the same room — not separately, which is how most of us do it — and asked them to tell me where my exposure was concentrated. The answer was: one custodian, one tax regime, one asset class, one country.

That is not diversification. That is theatre.

The rotation cost me about 4% in transaction friction and one-time tax events. I think it bought me ten years of optionality. Happy to walk through the structures if anyone is on the same path. The math is more straightforward than the gatekeepers want you to believe."""),

    ("Sovereign Wealth", "james-r",
     "The 'compound it forever' meme is propaganda",
     """The "just buy the index and compound it for forty years" advice is real estate ad copy for the asset management industry. Look at the actual inflation-adjusted return on the S&P from 1971 — when Nixon shut the gold window — through today, deflated by the M2 money supply rather than the official CPI.

The compounded "real" return over a fifty-year window collapses to single digits. Most of what we have been told is "growth" is dilution math wearing a green wrapper.

This is not a doom post. It is a positioning post. If your wealth is denominated in a unit that is being printed against you, your job is not to compound — it is to convert. Hard assets, productive businesses, scarce things, and skills. The compounding only matters once the unit of account is stable.

I will share the chart in the next post. Build a portfolio that survives the unit changing. That is the entire game."""),

    # ---------------- Body & Iron ----------------
    ("Body & Iron", "sean-t",
     "12-week strength block — what hit, what didn't",
     """Just closed a twelve-week block with a small group of brothers. Squat-press-deadlift on a 4-day split, conjugate accessory work, one heavy and one dynamic day on each lift.

What hit: linear loading on the deadlift. Six pounds a week, every week, no failed reps. Boring. Brutal. Worked.

What didn't: speed work on the bench under 50% — neurologically wasted on these guys. Cut it after week three and replaced with paused close-grip. Bench moved 25 pounds in the back half of the cycle.

What I'd do differently: more sled work. The conditioning gap shows up around week eight when total tonnage spikes. A man who can't push a sled for ten minutes will not survive the back end of a real strength cycle.

If anyone wants the actual block, DM me — I'll send the spreadsheet. No charge. Just expect me to ask you what your current numbers are first."""),

    ("Body & Iron", "anders-l",
     "Rebuilt my sleep architecture in 60 days — strongest performance gain I've ever made",
     """Spent ten years optimizing training, diet, supplements, all of it. Made marginal gains.

Fixed my sleep in sixty days. Made non-marginal gains in everything.

What I changed: blackout the room (real blackout, not the curtain marketing — I taped over LEDs), 67 degrees, no screens after sundown without amber-shifting them at the OS level, and — the biggest one — a fixed wake time, weekends included. The fixed wake time was the unlock. It dragged my circadian rhythm back into alignment within two weeks.

I tracked it with a HRV strap, not because I trust the device, but because I wanted a number to argue against. The number stopped arguing back at week three.

Recovery is up. Bloodwork moved (cortisol AM down 22%). Squat is finally back over 405 at bodyweight 195. The cheapest performance enhancer is the one nobody trains. Get this dialed before you spend another dollar on a powder."""),

    # ---------------- Awake Minds ----------------
    ("Awake Minds", "david-k",
     "I read Brave New World again at 38. I missed the point at 17.",
     """Picked up Brave New World again last month. Twenty-one years since I read it in high school. I remembered it as a parable about authoritarian control. That is not the book.

The book is about voluntary surrender. Nobody in the World State is being held there at gunpoint. They are being held there by comfort, distraction, sanctioned pleasure, and the absence of any cultural permission to be unhappy about it.

Huxley got it right and Orwell got it almost-right. The future is not a boot stamping on a face. The future is a feed scrolling itself, a pill that takes the edge off, a calendar with no obligations, a man who has not had a hard conversation in two years.

Reread it. It's not a long book. Read it as instructions for what to opt out of.

I'd love to hear what other books some of you re-read at this stage of life and got something completely different from than at twenty.""" ),

    ("Awake Minds", "james-r",
     "Three stories the legacy press buried this week",
     """Three stories from this week that did not make the front page of any outlet most of us still subscribe to.

One — the Bank for International Settlements quietly published a working paper acknowledging that retail CBDC adoption faces "behavioral resistance" and recommending pilot rollouts paired with negative-rate sticks. Read it for yourself. Not a conspiracy. Their words.

Two — a federal appellate court ruled on the legal standing of asset forfeiture without conviction in a case that affects roughly half the country. Almost no coverage. The decision matters to anyone who carries cash.

Three — the WHO updated pandemic-treaty language to include cross-border lockdown coordination and the legacy outlets covered it as a procedural note. It is not procedural.

I'm not going to tell you what to think about any of this. I am going to tell you that if your news diet did not surface a single one of these three, your news diet is broken. I'll drop the source links in comments. Read the primaries."""),

    # ---------------- Business Directory ----------------
    ("Business Directory", "marcus-w",
     "How we ran a 6-man retreat without a coach or agenda",
     """Six of us — three from Texas, two from Florida, one from Idaho — rented a cabin north of Sedona for four days last month. No coach. No agenda. No trained facilitator.

Here is what we did instead.

Day one: introductions and lifts. Each man stood up after dinner and said the one thing he was not telling his wife, his business partner, or himself. Two minutes per man. The room held it. No fixing.

Day two: a long ruck. Eleven miles. Talked in pairs that rotated every two miles. By the time we got back to the cabin, every man had spoken with every other man one-on-one. That is not a coincidence — it was the format.

Day three: each man presented a problem, and the rest of us had ninety minutes to actually help him solve it. No "what would you do," no abstractions. We made decisions. People wrote checks at the table.

Day four: lifts, food, drive home.

Nothing got done by accident. The structure did the work. Happy to share the schedule for any room that wants to run their own."""),

    ("Business Directory", "chase-w",
     "Operator stack: the 5 tools I run my businesses on after killing 23 SaaS subscriptions",
     """Did a SaaS audit at the start of the year. Twenty-three active subscriptions across the three businesses. Almost all of them duplicated functionality I could get from one well-chosen tool. Killed eighteen of them. Annual savings: just under $14k. More importantly: cognitive savings.

The five I kept:

1. Notion — runs every SOP, every onboarding flow, every shared brain across the businesses. We tried Asana, ClickUp, Monday — Notion wins because it is permissive enough to let each business operate the way it actually operates.

2. Stripe — billing for the education brand. Works.

3. Google Workspace — calendar and email. Boring. Boring is the point.

4. 1Password — every credential, every API key, every shared login. Family vault for the kids' school stuff. Business vaults segregated by entity.

5. Loom — async video. Replaced 40% of meetings.

Everything else I either replaced with a script, a Notion template, or a hard conversation. Happy to walk through the cuts if anyone is mid-audit. Most of us are running too many subscriptions and too few systems."""),

    # ---------------- The Arsenal ----------------
    ("The Arsenal", "brendan-m",
     "The Notion → Obsidian migration that finally stuck",
     """Tried to migrate to Obsidian three times in three years. First two attempts failed because I was trying to recreate Notion inside Obsidian. The third stuck because I stopped doing that.

What flipped: I stopped using Obsidian as a database and started using it as a notebook. One folder per project. Daily notes file with timestamped entries. Backlinks for cross-referencing — not for organizing. The graph view is a toy, ignore it.

Three rules that made it durable:

- Every note ends with a "what next" line. Future-me reads the note and knows what to do.
- No tags. Folders only. Tags are a tax you pay forever; folders are a one-time decision.
- Sync via iCloud, not Obsidian Sync. The free path is the durable path.

Templates are in the comments — daily, project kickoff, deal evaluation, post-mortem. Take what's useful, leave the rest. The point is a system you'll still be running in five years, not a system that wins r/PKM this week."""),

    ("The Arsenal", "anders-l",
     "I built my own outreach script after every cold-email tool failed me",
     """Every B2B outreach tool I tried wanted to charge me $300/month to send 200 emails I could write better myself. Built my own. 200 lines of Python, a sqlite DB, and a Postmark account. Three weeks of wall-time, mostly because I was learning the deliverability side from zero.

Architecture, in case it helps anyone:

- Lead list lives in a single CSV, parsed once into sqlite.
- Templating layer is Jinja2. One template per campaign, one row of variables per lead.
- Send loop respects per-domain rate limits. Postmark handles the actual SMTP.
- Reply detection via a simple webhook. State machine moves the lead through "sent → opened → replied → closed."
- Everything is logged. Every state change is a row.

Open rates are higher than the SaaS tools because I am not blasting from a shared IP pool. Reply rates are higher because I am writing each campaign like a human, not pulling from a "personalization library."

It is not a product. It is a tool I run for one business. If anyone wants the code as a starting point — happy to send. Stop renting things you can own."""),

    # ---------------- The Hidden Truth ----------------
    ("The Hidden Truth", "kyle-h",
     "Excess mortality 2020-2024 — the chart they didn't show you",
     """Pulled the CDC's own all-cause mortality data for 2020 through 2024 and reorganized it the way it should have been published the first time: by age cohort, normalized against pre-pandemic five-year averages, segmented by year-quarter rather than annualized.

What jumps out is not 2020. Everyone saw 2020. What jumps out is the quarterly cohort-level excess mortality in the 25–44 age band starting Q3 2021 and persisting through Q1 2023. It is not consistent with the official narrative arc of "the pandemic ended in 2022."

I am not going to tell you what caused it. I do not know. The point of the post is that the data the agency itself published does not match the headline summary the agency itself published. You can hold both at the same time without picking a team.

Methodology in the comments. Replication-ready Python notebook for anyone who wants to run their own segmentation. Post your version. Argue with mine. That is how the room works."""),

    ("The Hidden Truth", "david-k",
     "Why I stopped reading mainstream economic forecasts",
     """Stopped reading the IMF and World Bank annual outlooks about three years ago. Started reading them again last quarter as a control experiment. The findings:

The forecasts are not predictions. They are policy advocacy dressed in regression output. The "baseline" scenario is always the scenario the issuing institution wants to see realized, and the "downside" is always the political pressure they want absorbed.

What I read instead now:

- BIS quarterly working papers — not their press releases, the actual papers. Buried in the appendices is the most honest macro analysis published in the world.
- Lyn Alden's monthly note — disciplined, mechanical, not religious about any particular outcome.
- Luke Gromen's weekly — high signal on the dollar-system stress points the legacy press misses by structural design.
- The actual Fed H.4.1 release — read the balance sheet, not the chair's commentary about it.

The pattern: read primary documents and a handful of analysts who read primary documents. Skip the institutional press releases. They were never written for you."""),

    # ---------------- Family & Legacy ----------------
    ("Family & Legacy", "chase-w",
     "How I'm teaching my 7-year-old son to handle a knife. Not metaphor.",
     """My oldest is seven. Last weekend I gave him his first real knife — a small fixed-blade with a rounded tip — and walked him through the rules.

The rules are short: blade-side away from the body, no walking with it open, the man holding it is responsible for everyone in the room. He repeated them back to me until they were boring. Then we whittled a stick for an hour.

This is not a flex post. It is a worldview post. My job as a father is to introduce real risk early, in scale he can handle, with a man he trusts at his shoulder. The alternative — keeping all sharp edges of life away from him until he is eighteen — does not produce a competent adult. It produces an anxious one.

We do this with knives, with fire, with hand tools, with money, with hard conversations. Small dose, supervised, repeatable. The dose escalates as he proves he can hold it.

If anyone has older boys and is further down this path, I would love to hear what stage seventeen looks like from the perspective of a father who started early."""),

    ("Family & Legacy", "sean-t",
     "The talk I had with my father at 35 that I should have had at 25",
     """Sat down with my father in his kitchen this fall. Asked him three questions I had been carrying for a decade and was sure he would never want to answer.

One — what did you actually believe about your own father, and when did that belief change?
Two — what did you think you would have done by now, and what did you do instead?
Three — what would you tell my sons about you that I haven't already told them?

He answered all three. We were there for four hours. The conversation moved my picture of him about two notches in a direction I had been waiting twenty years to see.

The lesson is not about my father. The lesson is that I was the one who had to ask. He was never going to volunteer it. Most of our fathers will not. They were not raised to.

If your father is alive, schedule the conversation. Bring real questions. Sit down. Most men in our generation are missing the original transmission and looking for it everywhere else. Sometimes it is just down the highway in a kitchen, waiting for you to ask."""),

    # ---------------- Off Grid ----------------
    ("Off Grid", "brendan-m",
     "First six months on 12 acres — what I underestimated",
     """We closed on twelve acres outside Nashville six months ago and moved the family out on month four. Some notes for any brother in the planning phase.

What I underestimated:

- Driveway maintenance. Half a mile of gravel does not maintain itself. Budget three weekends a year minimum.
- Internet. The "you can use Starlink anywhere" line is mostly true and partially a lie. Tree cover matters. Pole height matters. Plan the sky view before you site the office.
- Wildlife pressure on the garden. Deer fencing was a line item I cut to save $1,800. I rebuilt it for $2,400 in month five after losing every tomato.

What was easier than expected:

- Heating. The wood stove handles the whole main floor. Splitting and stacking is meditative, not punishing.
- Kids. They adapted in two weeks. The seven-year-old now identifies four bird calls and reads weather from the sky better than I do.
- Mental health. The first three weeks were hard. Months two through six have been the most settled I have felt as an adult.

Happy to answer specifics. The capex is real, the lifestyle is real, the romanticization is real, and the pay-off is bigger than the brochure."""),

    ("Off Grid", "kyle-h",
     "Solar + propane + well: the actual capex breakdown nobody publishes",
     """Built out the energy stack at the Wyoming property over the last fourteen months. Sharing the actual numbers because every other "off-grid build" post I read either skipped the line items or padded them for affiliate links.

Solar:
- 12 kW array, 4 strings, ground-mount: $18,400 hardware
- Inverters and balance of system: $7,200
- Battery (40 kWh LFP, expandable): $19,000
- Permitting and inspection (one rural county, friendly): $1,100
- Install labor (two-man crew, 9 days, brotherhood rate): $6,500
- Total solar: $52,200

Propane:
- 1,000-gal underground tank with cathodic protection: $4,800
- Trenched line + regulators: $2,200
- Fill at install (current rates): $2,400
- Total propane: $9,400

Well + pump:
- Drilling (hit at 285 ft, hard luck on this one): $14,200
- 1.5 hp submersible + pressure tank + softener: $5,400
- Trench to house and freeze protection: $3,100
- Total water: $22,700

All-in: $84,300 for full energy + water sovereignty on the parcel, before the house build.

Could have been done for ~$65k with patience and a smaller battery. Could have been $120k if I had gone retail without the brotherhood help. The middle path is the reproducible one. Ask if you want vendor names."""),
]


# ---------------------------------------------------------------------------
# Wins
# ---------------------------------------------------------------------------

WINS = [
    ("marcus-w", "First off-market deal sourced from this room",
     "Closed it last Friday. $1.4M, 4-cap on the in-place rents, plenty of "
     "meat on the bone for a 5-year hold. Sourced through a brother in this "
     "Society — DM-to-handshake-to-contract in 19 days. Six months ago I did "
     "not know this asset class existed. Today I own it. The room compounds.",
     20),
    ("sean-t", "405 raw squat at 41",
     "Hit it Saturday morning. Twenty pounds heavier than my college PR, "
     "twenty years later. Programming credit goes to the Body & Iron "
     "conversation last quarter — the linear-loading argument finally beat "
     "my conjugate ego. The body is the first empire, brothers. Reclaim it.",
     14),
    ("chase-w", "My oldest taught his younger brother to start a fire without matches",
     "He's seven. The little one is four. They were behind the woodshed for "
     "an hour. I almost intervened twice and both times I held back. They "
     "came around the corner with smoke on their hands and a grin I will "
     "remember at his wedding. That is the win. The whole win.",
     8),
    ("james-r", "Liquidated my last muni-bond position",
     "Rotated the entire muni stack into a mix of energy royalties, "
     "physical, and a small allocation to productive farmland. Seven years "
     "late on this trade. Felt like cutting an anchor I had been dragging "
     "behind a boat I no longer wanted to be on. The window to reposition "
     "is still open. Some of us are using it.",
     30),
]


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

DEALS = [
    ("marcus-w", "investment", "Sun Belt MF syndication — 2-3 LP slots open",
     "72-unit B-class in a Texas secondary market, value-add thesis on "
     "in-place rents 14% under market, 16% IRR target on a 3-year hold. "
     "Already have anchor LPs committed; opening 2-3 slots to brothers in "
     "the Society at preferred terms. Min ticket $50k. Accredited only. PM "
     "for the OM.", 12),
    ("anders-l", "partnership", "Fractional founder w/ B2B distribution chops",
     "Building a hardware product — off-grid power and water monitoring for "
     "small farms and rural homesteads. Working prototype, two paying pilot "
     "customers, no real revenue yet. Looking for a fractional founder who "
     "has actually moved B2B hardware before — equity, not cash. I'll out-"
     "engineer most of you; I will not out-distribute you. That's the gap.",
     9),
    ("brendan-m", "service", "One custom homestead build slot, Q3 in TN/NC",
     "Taking one new build project starting Q3 in the TN/NC region. Custom "
     "homestead, 3-acre minimum, owner-builder collaboration model. Brothers "
     "in the Society get 10% off the GC fee and priority on schedule. DMs "
     "only — I'll send the deck and a list of recent builds. First-come, "
     "first-served once I'm full I'm full.", 7),
    ("david-k", "hiring", "Sr. Backend Engineer — fintech (Go + Postgres)",
     "Hiring a senior backend for the fintech I'm building. Stack is Go on "
     "Postgres, event-sourced, deployed on a Kubernetes cluster I actually "
     "understand. Remote OK, US-only, equity + cash. The product is a "
     "settlement layer for SMB cross-border payments. Brothers first — I'll "
     "open it to the broader market after this room has had a chance. DM "
     "me if you or someone in your circle is the right fit.", 5),
]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

RESOURCES = [
    ("marcus-w", "book", "The Sovereign Individual — Davidson & Rees-Mogg",
     "1997 book. Predicted half of what we are living through now and "
     "framed the rest of the decade better than any other text in print. "
     "Read once, then read it again with a pen.",
     "https://www.goodreads.com/book/show/82256.The_Sovereign_Individual"),
    ("james-r", "book", "Antifragile — Nassim Taleb",
     "Concept of the book is the framework most operators in this Society "
     "are intuitively running. Putting language around it is worth the "
     "read. Skip Taleb on Twitter; read him in long form.",
     "https://www.goodreads.com/book/show/13530973-antifragile"),
    ("chase-w", "book", "Unscripted — MJ DeMarco",
     "Best single piece of writing I have read on rejecting the W-2 + "
     "401k + retire-at-65 path. Imperfect prose, perfect frame. Hand it to "
     "a brother who is on the fence about leaving his job.",
     "https://www.goodreads.com/book/show/35356378-unscripted"),
    ("anders-l", "tool", "Obsidian — local-first knowledge tool",
     "Markdown files in a folder you actually own. Plain text, syncable any "
     "way you want, no vendor lock-in. The system that finally beat Notion "
     "for me. Free for personal use.", "https://obsidian.md"),
    ("david-k", "podcast", "Acquired — Ben Gilbert + David Rosenthal",
     "Long-form business history. Three to five hours per episode, "
     "exhaustively researched, no celebrity-interview filler. The Costco "
     "episode is a master class. The TSMC episode is a national-security "
     "briefing in disguise.", "https://www.acquired.fm/"),
    ("sean-t", "article", "RFK Jr. chronic disease whitepaper",
     "Long-form sourced argument on the metabolic-health crisis and the "
     "regulatory-capture story behind it. Read the whole thing — citations "
     "and all — before you form an opinion. Your priors will move whichever "
     "side of the aisle you started on.",
     "https://childrenshealthdefense.org/defender/"),
    ("marcus-w", "template", "Deal-evaluation framework — 1-page",
     "Single-page template I use to evaluate any new investment opportunity "
     "before it gets a second meeting. Six sections: thesis, sponsor, "
     "underwriting, downside, optionality, decision. If a deal can't fit on "
     "the page, it is not ready for a check. Drop a comment and I'll send "
     "the doc.", None),
]


# ---------------------------------------------------------------------------
# Weekly Challenge
# ---------------------------------------------------------------------------

CHALLENGE = {
    "title": "7-Day Cold Plunge Discipline",
    "creator_slug": "sean-t",
    "description": (
        "Seven days. One cold plunge per day. Minimum two minutes, water "
        "at or below 50°F. No music, no phone, no audience. Just you and "
        "the water and the chair you sit in afterward.\n\n"
        "This is not about the cold. The cold is the rep. The rep is "
        "choosing discomfort on purpose, on schedule, when nothing in your "
        "environment is forcing you to. That is the muscle every sovereign "
        "man is trying to build, and the body is the cleanest gym for "
        "building it. The mind follows what the body practices.\n\n"
        "Post a daily check-in in the comments — one line, no photos "
        "required. Day, time, water temp, and one sentence on what came up. "
        "Brothers who complete all seven get the points and the next week's "
        "respect. Brothers who skip a day post that too. Honesty is the "
        "minimum standard. Discipline is the rest of the work."
    ),
    "submissions": [
        ("marcus-w", "Day 1 — 49°F, 2:10. The first thirty seconds is the whole game. Glad I didn't bring a phone in."),
        ("brendan-m", "Day 2 — 47°F, 2:30. Stock tank in the back yard, hose-fed, ice from the chest freezer. Cheap and effective."),
        ("anders-l", "Day 1 — 51°F, 2:00 even. My breathing was the worst part — clearly under-trained on that. Notes for tomorrow."),
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_password(plain: str) -> str:
    """bcrypt hash, returned as a UTF-8 string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _seed_email(slug: str) -> str:
    return f"seed.{slug}{SEED_EMAIL_DOMAIN}"


def _avatar_svg_path_relative(slug: str) -> str:
    return f"img/seed/avatar-{slug}.svg"


def _avatar_svg_disk_path(slug: str) -> str:
    return os.path.join(SEED_IMG_DIR, f"avatar-{slug}.svg")


def _initials(name: str) -> str:
    parts = [p for p in name.replace(".", "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _write_avatar_svg(slug: str, name: str) -> bool:
    """Write a gold-on-black monogram SVG. Returns True if file was created."""
    path = _avatar_svg_disk_path(slug)
    if os.path.exists(path):
        return False
    initials = _initials(name)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <circle cx="100" cy="100" r="98" fill="#0A0A0A" stroke="#D4AF37" stroke-width="2"/>
  <text x="100" y="118" text-anchor="middle"
        font-family="Georgia, 'Times New Roman', serif"
        font-size="78" font-weight="300"
        fill="#D4AF37" letter-spacing="2">{initials}</text>
</svg>
'''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return True


# ---------------------------------------------------------------------------
# Cleanup (one-time legacy purge — idempotent)
# ---------------------------------------------------------------------------

def cleanup_legacy_seed() -> dict:
    """Delete legacy 6 Spaces, 5 Events, and orphan PNG files. Idempotent."""
    deleted_spaces = 0
    deleted_events = 0
    deleted_pngs = 0

    for name in LEGACY_SPACE_NAMES:
        sp = Space.query.filter_by(name=name).first()
        if sp is not None:
            db.session.delete(sp)
            deleted_spaces += 1

    for name in LEGACY_EVENT_NAMES:
        ev = Event.query.filter_by(title=name).first()
        if ev is not None:
            db.session.delete(ev)
            deleted_events += 1

    db.session.commit()

    for fname in LEGACY_PNG_FILES:
        path = os.path.join(LEGACY_UPLOADS_DIR, fname)
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted_pngs += 1
            except OSError as e:
                print(f"  [cleanup] could not remove {path}: {e}", flush=True)

    # Verify canonical 8 exist
    missing = [n for n in CANONICAL_SPACE_NAMES if not Space.query.filter_by(name=n).first()]

    print(
        f"[CLEANUP] Legacy purge: deleted {deleted_spaces} Space(s), "
        f"{deleted_events} Event(s), {deleted_pngs} PNG file(s).",
        flush=True,
    )
    if missing:
        print(
            f"[CLEANUP] WARNING: canonical Spaces missing — {missing}. "
            f"Run `python populate_content.py` (or boot app.py) first to seed them, "
            f"then re-run this script.",
            flush=True,
        )
    else:
        print("[CLEANUP] Canonical 8 Spaces verified.", flush=True)

    return {
        "spaces": deleted_spaces,
        "events": deleted_events,
        "pngs": deleted_pngs,
        "missing_canonical": missing,
    }


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def ensure_image_dir() -> None:
    os.makedirs(SEED_IMG_DIR, exist_ok=True)


def seed_users(password_hash: str) -> dict:
    """Idempotent — creates only users that don't exist."""
    created = 0
    existing = 0
    for u in USERS:
        email = _seed_email(u["slug"])
        if User.query.filter_by(email=email).first():
            existing += 1
            continue

        # Write avatar SVG
        _write_avatar_svg(u["slug"], u["name"])

        user = User(
            email=email,
            password_hash=password_hash,
            name=u["name"],
            bio=u["bio"],
            profile_photo=_avatar_svg_path_relative(u["slug"]),
            points=u["points"],
            streak_days=u["streak"],
            last_login_date=date.today(),
            subscription_status="active",
            email_verified=True,
            city=u["city"],
            country=u["country"],
            lat=u["lat"], lng=u["lng"],
            show_on_map=True,
            referral_code=secrets.token_urlsafe(8)[:12],
            created_at=datetime.utcnow() - timedelta(days=u["days_ago"]),
        )
        db.session.add(user)
        created += 1
    db.session.commit()
    print(f"[USERS]  created {created}, already existed {existing}.", flush=True)
    return {"created": created, "existing": existing}


def _user_by_slug(slug: str) -> User:
    return User.query.filter_by(email=_seed_email(slug)).first()


def _space_by_name(name: str) -> Space:
    return Space.query.filter_by(name=name).first()


def update_space_covers() -> int:
    """Set cover_image on canonical Spaces."""
    updated = 0
    for name in CANONICAL_SPACE_NAMES:
        sp = _space_by_name(name)
        if sp is None:
            continue
        rel = f"img/seed/space-{SPACE_SLUG[name]}.png"
        if sp.cover_image != rel:
            sp.cover_image = rel
            updated += 1
    db.session.commit()
    print(f"[COVERS] {updated} canonical Space cover(s) updated.", flush=True)
    return updated


def seed_posts() -> dict:
    """Idempotent — keys on (author email + first 60 chars of content)."""
    created = 0
    existing = 0
    # Distribute backdates between 2 and 60 days ago
    span_days = 58
    today = datetime.utcnow()
    for idx, (space_name, slug, title, body) in enumerate(POSTS):
        author = _user_by_slug(slug)
        space = _space_by_name(space_name)
        if not author or not space:
            continue
        full = f"{title}\n\n{body}"
        # Cheap idempotency check: same author + same title in same space
        existing_post = (
            Post.query
            .filter_by(user_id=author.id, space_id=space.id)
            .filter(Post.content.like(f"{title}%"))
            .first()
        )
        if existing_post:
            existing += 1
            continue
        # Image rotation: 30% get a cover
        image_path = None
        if idx % 7 == 0:
            image_path = WIN_COVER
        elif idx % 11 == 0:
            image_path = DEAL_COVER

        # Backdate evenly across the window, oldest first
        days_back = 2 + int((span_days * idx) / max(1, len(POSTS) - 1))
        post = Post(
            user_id=author.id,
            content=full,
            space_id=space.id,
            image_path=image_path,
            created_at=today - timedelta(days=days_back, hours=(idx * 7) % 24),
        )
        db.session.add(post)
        created += 1
    db.session.commit()
    print(f"[POSTS]  created {created}, already existed {existing}.", flush=True)
    return {"created": created, "existing": existing}


def seed_wins() -> dict:
    created = 0
    existing = 0
    today = datetime.utcnow()
    for slug, title, desc, days_ago in WINS:
        author = _user_by_slug(slug)
        if not author:
            continue
        if Win.query.filter_by(user_id=author.id, title=title).first():
            existing += 1
            continue
        win = Win(
            user_id=author.id,
            title=title,
            description=desc,
            image_path=WIN_COVER,
            created_at=today - timedelta(days=days_ago),
        )
        db.session.add(win)
        created += 1
    db.session.commit()
    print(f"[WINS]   created {created}, already existed {existing}.", flush=True)
    return {"created": created, "existing": existing}


def seed_deals() -> dict:
    created = 0
    existing = 0
    today = datetime.utcnow()
    for slug, category, title, desc, days_ago in DEALS:
        author = _user_by_slug(slug)
        if not author:
            continue
        if Deal.query.filter_by(user_id=author.id, title=title).first():
            existing += 1
            continue
        deal = Deal(
            user_id=author.id,
            title=title,
            description=desc,
            category=category,
            image_path=DEAL_COVER,
            created_at=today - timedelta(days=days_ago),
        )
        db.session.add(deal)
        created += 1
    db.session.commit()
    print(f"[DEALS]  created {created}, already existed {existing}.", flush=True)
    return {"created": created, "existing": existing}


def seed_resources() -> dict:
    created = 0
    existing = 0
    upvoted = 0
    for slug, category, title, desc, url in RESOURCES:
        author = _user_by_slug(slug)
        if not author:
            continue
        existing_r = Resource.query.filter_by(user_id=author.id, title=title).first()
        if existing_r:
            resource = existing_r
            existing += 1
        else:
            resource = Resource(
                user_id=author.id,
                title=title,
                description=desc,
                url=url,
                category=category,
            )
            db.session.add(resource)
            db.session.flush()  # get id
            created += 1

        # Add 2 upvotes from other placeholders (rotating)
        upvoter_slugs = [u["slug"] for u in USERS if u["slug"] != slug][:3]
        for u_slug in upvoter_slugs[:2]:
            upvoter = _user_by_slug(u_slug)
            if not upvoter:
                continue
            already = ResourceUpvote.query.filter_by(
                resource_id=resource.id, user_id=upvoter.id
            ).first()
            if not already:
                db.session.add(ResourceUpvote(resource_id=resource.id, user_id=upvoter.id))
                upvoted += 1
    db.session.commit()
    print(
        f"[RES]    created {created}, already existed {existing}, +{upvoted} upvotes.",
        flush=True,
    )
    return {"created": created, "existing": existing, "upvotes_added": upvoted}


def seed_challenge() -> dict:
    creator = _user_by_slug(CHALLENGE["creator_slug"])
    if not creator:
        return {"created": 0, "existing": 0}

    existing_c = WeeklyChallenge.query.filter_by(title=CHALLENGE["title"]).first()
    if existing_c:
        challenge = existing_c
        created_flag = False
    else:
        challenge = WeeklyChallenge(
            title=CHALLENGE["title"],
            description=CHALLENGE["description"],
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            points_reward=75,
            created_by=creator.id,
        )
        db.session.add(challenge)
        db.session.flush()
        created_flag = True

    sub_added = 0
    for slug, content in CHALLENGE["submissions"]:
        u = _user_by_slug(slug)
        if not u:
            continue
        existing_sub = ChallengeSubmission.query.filter_by(
            challenge_id=challenge.id, user_id=u.id
        ).first()
        if existing_sub:
            continue
        db.session.add(
            ChallengeSubmission(
                challenge_id=challenge.id,
                user_id=u.id,
                content=content,
            )
        )
        sub_added += 1
    db.session.commit()
    state = "created" if created_flag else "existed"
    print(f"[CHAL]   challenge {state}, +{sub_added} submission(s).", flush=True)
    return {"created": int(created_flag), "submissions_added": sub_added}


def update_event_covers_and_rsvps() -> dict:
    cover_updates = 0
    rsvp_added = 0
    rsvp_user_slugs = [u["slug"] for u in USERS]
    # Each event gets 4 RSVPs (rotating sets, "going" status)
    rsvp_groups = {
        "Fire to Fire - St. Pete": ["marcus-w", "james-r", "chase-w", "david-k"],
        "Sovereign Wealth Workshop": ["marcus-w", "james-r", "kyle-h", "anders-l", "david-k"],
        "Brotherhood Summit": ["marcus-w", "sean-t", "brendan-m", "chase-w", "anders-l"],
    }

    for title, cover in CANONICAL_EVENT_COVERS.items():
        ev = Event.query.filter_by(title=title).first()
        if ev is None:
            print(f"[EVT]    WARNING: canonical event missing — {title}", flush=True)
            continue
        if ev.cover_image != cover:
            ev.cover_image = cover
            cover_updates += 1
        for slug in rsvp_groups.get(title, []):
            u = _user_by_slug(slug)
            if not u:
                continue
            existing_rsvp = EventRSVP.query.filter_by(event_id=ev.id, user_id=u.id).first()
            if existing_rsvp:
                continue
            db.session.add(EventRSVP(event_id=ev.id, user_id=u.id, status="going"))
            rsvp_added += 1
    db.session.commit()
    print(
        f"[EVT]    {cover_updates} cover(s) wired, +{rsvp_added} RSVP(s).",
        flush=True,
    )
    return {"covers_updated": cover_updates, "rsvps_added": rsvp_added}


# ---------------------------------------------------------------------------
# Delete (full wipe of placeholder content + generated images)
# ---------------------------------------------------------------------------

def delete_placeholders() -> dict:
    """Remove all seed.* users (cascade), challenge, generated images. Idempotent."""
    # Drop the active challenge first (it does not cascade through user delete
    # cleanly because creator FK has no cascade).
    challenge = WeeklyChallenge.query.filter_by(title=CHALLENGE["title"]).first()
    if challenge is not None:
        db.session.delete(challenge)

    seed_users = User.query.filter(User.email.like(f"seed.%{SEED_EMAIL_DOMAIN}")).all()
    user_count = len(seed_users)
    for u in seed_users:
        # Cascade-delete related rows that don't have built-in cascade:
        #   Wins (no cascade), Deals (no cascade), Resources (no cascade),
        #   EventRSVPs (no user cascade), ChallengeSubmissions (no user cascade)
        # The User.posts relationship has cascade="all, delete-orphan", so
        # posts go with the user.
        Win.query.filter_by(user_id=u.id).delete()
        Deal.query.filter_by(user_id=u.id).delete()
        Resource.query.filter_by(user_id=u.id).delete()
        EventRSVP.query.filter_by(user_id=u.id).delete()
        ChallengeSubmission.query.filter_by(user_id=u.id).delete()
        ResourceUpvote.query.filter_by(user_id=u.id).delete()
        db.session.delete(u)
    db.session.commit()

    # Clear cover_image on canonical Spaces + Events (back to None)
    for name in CANONICAL_SPACE_NAMES:
        sp = _space_by_name(name)
        if sp:
            sp.cover_image = None
    for title in CANONICAL_EVENT_COVERS:
        ev = Event.query.filter_by(title=title).first()
        if ev:
            ev.cover_image = None
    db.session.commit()

    # Wipe images
    images_removed = 0
    if os.path.isdir(SEED_IMG_DIR):
        for name in os.listdir(SEED_IMG_DIR):
            try:
                os.remove(os.path.join(SEED_IMG_DIR, name))
                images_removed += 1
            except OSError:
                pass

    print(
        f"[DELETE] {user_count} placeholder user(s) removed, "
        f"{images_removed} image(s) wiped, cover_image fields cleared.",
        flush=True,
    )
    return {"users_removed": user_count, "images_removed": images_removed}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_seed() -> None:
    ensure_image_dir()
    pwd_hash = _hash_password(DEV_SEED_PASSWORD)

    cleanup_legacy_seed()
    seed_users(pwd_hash)
    update_space_covers()
    seed_posts()
    seed_wins()
    seed_deals()
    seed_resources()
    seed_challenge()
    update_event_covers_and_rsvps()

    print(
        f"\n[DONE] Seed complete. Login as any:\n"
        f"  email:    seed.<slug>@sovereign.placeholder\n"
        f"  password: {DEV_SEED_PASSWORD}\n"
        f"  slugs:    {', '.join(u['slug'] for u in USERS)}\n",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Sovereign Society placeholder seeder.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Wipe all placeholder users + generated images and exit.",
    )
    args = parser.parse_args()

    with app.app_context():
        if args.delete:
            delete_placeholders()
        else:
            run_seed()


if __name__ == "__main__":
    main()
