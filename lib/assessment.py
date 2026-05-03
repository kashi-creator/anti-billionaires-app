"""Sovereign Code Self-Assessment — 8 pillars × 5 Likert questions.

Question text and pillar names are quoted verbatim from
~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_assessment_feature.md
which is the source of truth. Pillar order matches the locked landing-page
copy in project_pending_landing_edits.md — keep both in lockstep.
"""

PILLARS = [
    {
        "slug": "purpose",
        "name": "Purpose",
        "questions": [
            "I have a clear vision for what I want my life to look like in 5 years.",
            "My daily actions are aligned with my long-term goals.",
            "I know what I stand for and I don't compromise it under pressure.",
            "I wake up most days with a sense of direction and intention.",
            "I have identified my mission in life and I am actively working toward it.",
        ],
    },
    {
        "slug": "strength",
        "name": "Strength",
        "questions": [
            "I train my body consistently and hold myself to a physical standard.",
            "I am mentally resilient when things get hard or don't go my way.",
            "I do not avoid difficult situations out of fear or discomfort.",
            "I push myself beyond what is comfortable on a regular basis.",
            "My physical health reflects the level of discipline I want to bring to every area of my life.",
        ],
    },
    {
        "slug": "wealth",
        "name": "Wealth",
        "questions": [
            "I have a clear plan for building and growing my income.",
            "I understand my finances and make intentional decisions with my money.",
            "I am actively building assets or income streams outside of a single paycheck.",
            "I invest in myself — my skills, knowledge, and capabilities — as a financial strategy.",
            "I am working toward a level of financial independence that gives me real freedom.",
        ],
    },
    {
        "slug": "brotherhood",
        "name": "Brotherhood",
        "questions": [
            "I have men in my life who hold me accountable and tell me the truth.",
            "I show up for the people in my circle when they need me.",
            "I actively invest in relationships with other men who are building something.",
            "I am the kind of man others can rely on without question.",
            "I seek out environments where I am challenged by the men around me, not just comfortable.",
        ],
    },
    {
        "slug": "family",
        "name": "Family",
        "questions": [
            "I am present and intentional with the people I love most.",
            "I am actively working to provide security financially, emotionally, and physically for my family.",
            "The way I live sets an example I would be proud for my family to follow.",
            "I communicate openly and honestly with the people closest to me.",
            "I am building a legacy that will outlast me and benefit the people who come after me.",
        ],
    },
    {
        "slug": "faith",
        "name": "Faith",
        "questions": [
            "I have a relationship with a higher power that guides my decisions.",
            "My faith gives me stability and grounding when life is uncertain.",
            "I make time to nurture my spiritual life consistently.",
            "I operate from a place of trust rather than fear when facing the unknown.",
            "My beliefs are something I have chosen intentionally, not simply inherited or never questioned.",
        ],
    },
    {
        "slug": "awareness",
        "name": "Awareness",
        "questions": [
            "I actively seek out information and perspectives outside of mainstream narratives.",
            "I am aware of how the systems around me (financial, political, social) affect my life.",
            "I regularly reflect on my own blind spots and areas where I need to grow.",
            "I feel awake to what is really happening in the world around me, beyond what I am told to think.",
            "I have done meaningful work to expand my consciousness and understand myself at a deeper level.",
        ],
    },
    {
        "slug": "control",
        "name": "Control",
        "questions": [
            "I am disciplined with my time and protect it from things that don't serve me.",
            "I manage my emotions well and don't let external circumstances dictate my state.",
            "I follow through on commitments I make to myself, not just to others.",
            "I actively take care of my mental health and don't ignore what is happening internally.",
            "I have healthy outlets for stress, pressure, and difficult emotions and I use them.",
        ],
    },
]

LIKERT = [
    {"value": 1, "label": "Not at all"},
    {"value": 2, "label": "Rarely"},
    {"value": 3, "label": "Sometimes"},
    {"value": 4, "label": "Most of the time"},
    {"value": 5, "label": "Completely"},
]

PILLAR_SLUGS = [p["slug"] for p in PILLARS]
QUESTIONS_PER_PILLAR = 5
LIKERT_VALUES = {l["value"] for l in LIKERT}


def validate_answers(answers):
    """Validate a submission payload. Returns (ok, error_dict_or_none).

    Expected shape: {"purpose": [int, int, int, int, int], ...} for all 8 pillars.
    Each int must be in {1,2,3,4,5}. Returns the offending pillar/index on failure.
    """
    if not isinstance(answers, dict):
        return False, {"error": "answers must be an object"}
    for slug in PILLAR_SLUGS:
        if slug not in answers:
            return False, {"error": "missing pillar", "pillar": slug}
        arr = answers[slug]
        if not isinstance(arr, list) or len(arr) != QUESTIONS_PER_PILLAR:
            return False, {"error": "pillar requires 5 answers", "pillar": slug}
        for i, v in enumerate(arr):
            if not isinstance(v, int) or v not in LIKERT_VALUES:
                return False, {"error": "answer must be int 1-5", "pillar": slug, "question_index": i}
    return True, None


def compute_pillar_scores(answers):
    """Average each pillar's 5 answers, rounded to 1 decimal. Returns dict slug -> float."""
    scores = {}
    for slug in PILLAR_SLUGS:
        arr = answers[slug]
        scores[slug] = round(sum(arr) / len(arr), 1)
    return scores
