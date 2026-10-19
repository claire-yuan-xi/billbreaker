"""Splits a bill into sections and ranks them by how much they mention the reader."""

import re

from .profile_terms import profile_terms

# "SEC. 5. TITLE", "Section 2203 ...", "§ 12 ..." at the start of a line (notebook section 8).
SECTION_HEADING = re.compile(
    r"^\s*(?:SEC(?:TION)?\.?\s+|§\s*)(?P<no>\d+[A-Z0-9]*(?:[-–]\d+[A-Z0-9]*)?)\.?\s*"
    r"(?P<title>[^\n]{0,200})\s*$",
    re.I | re.M,
)


def _words(s: str) -> int:
    return len(s.split())


def split_bill_sections(bill_text: str, max_chunk_words: int = 850) -> list[dict]:
    """Splits at SEC. headings; falls back to roughly 850-word paragraph chunks."""
    text = re.sub(r"\r\n?", "\n", bill_text or "").strip()
    matches = list(SECTION_HEADING.finditer(text))
    if matches:
        out = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            out.append(
                {
                    "section": m.group("no") or str(i + 1),
                    "heading": re.sub(r"^[\s.\-:]+|[\s.\-:]+$", "", (m.group("title") or "").strip()),
                    "body": text[m.end() : end].strip(),
                }
            )
        return out

    sections: list[dict] = []
    carry: list[str] = []
    total = 0
    for para in (p.strip() for p in re.split(r"\n{2,}", text)):
        if not para:
            continue
        if carry and total + _words(para) > max_chunk_words:
            sections.append(_chunk(len(sections), carry))
            carry, total = [], 0
        carry.append(para)
        total += _words(para)
    if carry:
        sections.append(_chunk(len(sections), carry))
    return sections


def _chunk(index: int, paragraphs: list[str]) -> dict:
    return {"section": str(index + 1), "heading": "Unnumbered text chunk", "body": "\n\n".join(paragraphs)}


def rank_sections(bill_text: str, profile: dict, top_k: int = 3) -> dict:
    """Scores every section by how often the reader's terms appear; returns the top matches."""
    terms = profile_terms(profile)
    every = split_bill_sections(bill_text)
    rows = []
    for s in every:
        body = f"{s['heading']} {s['body']}".lower()
        hits = {t: n for t in terms if (n := len(re.findall(rf"\b{re.escape(t)}", body)))}
        rows.append({**s, "score": sum(hits.values()), "matchedTerms": sorted(hits), "hits": hits})
    ranked = sorted((r for r in rows if r["score"] > 0), key=lambda r: -r["score"])[:top_k]
    return {"terms": terms, "ranked": ranked, "total": len(every)}
