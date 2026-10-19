"""Find the parts of a bill that matter to one reader.

Same rules as section 8 of notebooks/bill_breaker.ipynb and billbreaker/ml on the site:
split at SEC. headings, then score each section by how often the reader's terms appear.
"""

import re

SECTION_HEADING = re.compile(
    r"(?im)^\s*(?:SEC(?:TION)?\.?\s+|§\s*)(?P<no>\d+[A-Z0-9]*(?:[-–]\d+[A-Z0-9]*)?)"
    r"\.?\s*(?P<title>[^\n]{0,200})\s*$"
)

# Answer word -> extra terms to look for in the bill text.
EXPANSIONS = {
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
SKIPPED_ANSWERS = {"no", "none", "skip", "n/a", ""}


def clean_profile(profile):
    """Drop skipped answers and normalize dashes, as the notebook and site do."""
    out = {}
    for key, value in (profile or {}).items():
        text = re.sub(r"[–—]", "-", str(value or "")).strip()
        if text.lower() not in SKIPPED_ANSWERS:
            out[key] = text
    return out


def split_bill_sections(bill_text, max_chunk_words=850):
    bill_text = re.sub(r"\r\n?", "\n", str(bill_text or "")).strip()
    matches = list(SECTION_HEADING.finditer(bill_text))
    if matches:
        sections = []
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(bill_text)
            sections.append({
                "section": match.group("no"),
                "heading": match.group("title").strip(" .-:"),
                "body": bill_text[match.end():end].strip(),
            })
        return sections
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", bill_text) if p.strip()]
    sections, carry, total = [], [], 0
    for p in paragraphs:
        n = len(p.split())
        if carry and total + n > max_chunk_words:
            sections.append({"section": str(len(sections) + 1), "heading": "Unnumbered text chunk",
                             "body": "\n\n".join(carry)})
            carry, total = [], 0
        carry.append(p)
        total += n
    if carry:
        sections.append({"section": str(len(sections) + 1), "heading": "Unnumbered text chunk",
                         "body": "\n\n".join(carry)})
    return sections


def profile_terms(profile):
    terms = set()
    for key, answer in profile.items():
        low = answer.lower()
        if key in ("work", "interests"):
            terms.update(w for w in re.findall(r"[a-z][a-z\-]{3,}", low) if w not in STOPWORDS)
        if key == "military" and low.startswith("y"):
            terms.update(MILITARY_TERMS)
        for trigger, extra in EXPANSIONS.items():
            if re.search(r"(?<![a-z])" + re.escape(trigger) + r"(?![a-z])", low):
                terms.update(e.lower() for e in extra)
    if "state" in profile:
        terms.add(profile["state"].lower())
    return sorted(terms)


def rank_sections(text, profile, top_k=3):
    terms = profile_terms(profile)
    rows = []
    for s in split_bill_sections(text):
        body = (s["heading"] + " " + s["body"]).lower()
        hits = {t: len(re.findall(r"\b" + re.escape(t), body)) for t in terms}
        hits = {t: n for t, n in hits.items() if n}
        rows.append({**s, "score": sum(hits.values()), "matched_terms": sorted(hits)})
    ranked = sorted(rows, key=lambda r: -r["score"])
    return [r for r in ranked if r["score"] > 0][:top_k]
