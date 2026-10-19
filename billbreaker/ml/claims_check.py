"""
A cheap grounding check for the personalized explanation: every sentence should be
backed by the bill summary and the sections it was given. It flags sentences that
introduce topics, numbers or judgments the sources never mention. A heuristic, not
proof; it is there to surface lines like an invented "higher healthcare costs".
"""

import re

STOP = set(
    (
        "about above after again also although among another any are around because been before being "
        "between both but can could does doing down during each either even ever every from further have "
        "having here into it's its just least less like likely little made make many might more most much "
        "must near need never other over own perhaps quite rather really same should since some still such "
        "than that their them then there these they this those though through under until upon very want "
        "were what when where whether which while will with within without would your you're you'll yours "
        "bill bills act law means could mean affect affected affects directly indirectly overall summary "
        "what this does it the and for not was has had our out who how why all one two way "
        "you your we us here's know help helps aims life new time line way ways well also"
    ).split()
)

# Phrases a neutral, source-bound explanation should not contain.
OPINION = re.compile(
    r"\b(benefits? outweigh|is (a )?good|is (a )?bad|you should (vote|support|oppose)|we can better"
    r"|important to support|great news|unfortunately)\b",
    re.I,
)

# Topics where an invented effect would mislead a reader.
RISKY = re.compile(
    r"^(health|healthcare|medical|illness|illnesses|disease|cost|costs|price|prices|premium|premiums"
    r"|insurance|tax|taxes|fee|fees|fine|fines|penalty|penalties|expense|expenses|wage|wages|salary"
    r"|income|loan|loans|tuition|debt|benefit|benefits|funding|money|dollar|dollars|crime|immigration"
    r"|deport|lawsuit|liability)$"
)

NUMBER = re.compile(r"\d[\d,.]*")
SERIOUS = ("new-topic", "new-number", "opinion")
FLAG_LABELS = {
    "new-topic": "Effect not in the bill",
    "new-number": "Number not in the bill",
    "opinion": "Opinion",
    "weak-support": "Loosely supported",
}


def stem(word: str) -> str:
    return re.sub(r"(ies|es|s|ing|ed|ly)$", "", word, flags=re.I)


def content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if w not in STOP]


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)
    parts = (re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", s).strip() for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned))
    # Skip headings and lead-ins such as "Here's what to know:".
    return [s for s in parts if len(s.split()) >= 5 and not s.endswith(":") and re.search(r"[.!?)]$", s)]


def check_claims(explanation: str, sources: list[str], reader_words: str = "") -> dict:
    """reader_words are the reader's own answers; restating them does not count against a sentence."""
    joined = " ".join(sources)
    known = {stem(w) for w in content_words(joined) + content_words(reader_words)}
    source_numbers = set(NUMBER.findall(joined))
    claims = []
    for text in split_sentences(explanation):
        words = content_words(text)
        unsupported = list(dict.fromkeys(w for w in words if stem(w) not in known))
        support = 1 - len(unsupported) / len(set(words)) if words else 1
        flags = []
        if any(RISKY.match(w) for w in unsupported):
            flags.append("new-topic")
        elif len(unsupported) >= 5 and support < 0.3:
            flags.append("weak-support")
        if any(len(n) > 1 and n not in source_numbers for n in NUMBER.findall(text)):
            flags.append("new-number")
        if OPINION.search(text):
            flags.append("opinion")
        claims.append({"text": text, "support": max(0.0, support), "unsupported": unsupported, "flags": flags})
    return {"claims": claims, "flagged": sum(1 for c in claims if c["flags"])}


def serious_count(report: dict) -> int:
    return sum(1 for c in report["claims"] if any(f in SERIOUS for f in c["flags"]))
