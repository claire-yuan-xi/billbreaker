"""
Reader answers to the words and phrases worth looking for in a bill.
Ported from the Colab notebook (section 8) so the site ranks sections the same way.
"""

import re

EXPANSIONS: dict[str, list[str]] = {
    "student": ["student", "college", "university", "tuition", "loan", "education", "school"],
    "retired": ["retire", "Social Security", "pension", "Medicare"],
    "65+": ["Medicare", "Social Security", "elderly", "older", "senior"],
    "45-64": ["retire", "pension"],
    "18-24": ["student", "young", "youth"],
    "under 18": ["minor", "child", "youth", "school"],
    "kids": ["child", "children", "family", "school", "parent"],
    "elderly": ["elderly", "older", "senior", "caregiver", "Medicare"],
    "medicare": ["Medicare"],
    "medicaid": ["Medicaid", "low-income"],
    "marketplace": ["health insurance", "exchange", "premium"],
    "employer": ["employer", "group health plan"],
    "va": ["veteran", "Department of Veterans Affairs"],
    "veteran": ["veteran", "armed forces", "military", "Department of Veterans Affairs"],
    "under $30k": ["low-income", "poverty", "assistance", "credit"],
    "$30-75k": ["tax", "credit", "middle-income"],
    "farm": ["agriculture", "farm", "crop", "rural"],
    "teacher": ["teacher", "school", "education"],
    "nurse": ["nurse", "hospital", "health care"],
    "environment": ["environment", "conservation", "wildlife", "pollution", "climate", "wilderness"],
    "taxes": ["tax", "Internal Revenue Code", "credit", "deduction"],
    "public lands": ["public land", "national forest", "wilderness", "Bureau of Land Management"],
}

MILITARY_TERMS = ["veteran", "armed forces", "military", "service member"]
STOPWORDS = set("just part time with work about most like public".split())
SKIPPED = {"no", "none", "skip", "n/a"}


def clean_profile(profile: dict) -> dict[str, str]:
    """Drops blank and no/none/skip answers, like the notebook does before ranking."""
    out = {}
    for key, value in profile.items():
        v = (value or "").strip()
        if v and v.lower() not in SKIPPED:
            out[key] = v
    return out


def profile_terms(profile: dict) -> list[str]:
    """The lower-cased words and phrases to look for in a bill for this reader, sorted."""
    terms: set[str] = set()
    answers = clean_profile(profile)
    for key, answer in answers.items():
        # Chips may use en dashes ("18–24"); the notebook's triggers use hyphens.
        low = re.sub("[\u2013\u2014]", "-", answer.lower())
        if key in ("work", "interests"):
            terms.update(w for w in re.findall(r"[a-z][a-z-]{3,}", low) if w not in STOPWORDS)
        if key == "military" and low.startswith("y"):
            terms.update(MILITARY_TERMS)
        for trigger, extra in EXPANSIONS.items():
            if re.search(rf"(?<![a-z]){re.escape(trigger)}(?![a-z])", low):
                terms.update(e.lower() for e in extra)
    if "state" in answers:
        terms.add(answers["state"].lower())
    return sorted(terms)
