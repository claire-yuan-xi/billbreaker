from billbreaker.ml.claims_check import check_claims
from billbreaker.ml.notebook_run import EXAMPLE_PROFILE, EXAMPLE_RUN
from billbreaker.ml.profile_terms import profile_terms
from billbreaker.ml.sections import rank_sections, split_bill_sections

BILL = "\n".join(
    [
        "SEC. 1. SHORT TITLE.",
        "This Act may be cited as the Test Act.",
        "SEC. 2. STUDENT LOANS.",
        "A student with loans from a college or university may defer tuition loan payments.",
        "SEC. 3. HIGHWAYS.",
        "Funds for highways.",
    ]
)


def test_profile_terms_match_the_notebook():
    assert ", ".join(profile_terms(EXAMPLE_PROFILE)) == (
        "assistance, bureau of land management, climate, college, colorado, conservation, credit, "
        "education, employer, environment, group health plan, lands, loan, loans, low-income, "
        "national forest, part-time, pollution, poverty, public land, retail, school, student, "
        "tuition, university, wilderness, wildlife, young, youth"
    )


def test_en_dash_chips_read_like_hyphens():
    assert profile_terms({"age": "18–24"}) == ["student", "young", "youth"]


def test_no_and_none_answers_are_skipped():
    assert profile_terms({"military": "No", "health": "None"}) == []


def test_splits_at_sec_headings():
    sections = split_bill_sections(BILL)
    assert [s["section"] for s in sections] == ["1", "2", "3"]
    assert sections[1]["heading"] == "STUDENT LOANS"


def test_ranks_the_section_with_the_readers_terms():
    ranked = rank_sections(BILL, {"work": "student"})["ranked"]
    assert [r["section"] for r in ranked] == ["2"]


def test_claims_check_flags_the_invented_lines():
    sources = [EXAMPLE_RUN["general"], *(s["heading"] for s in EXAMPLE_RUN["sections"])]
    report = check_claims(EXAMPLE_RUN["personalized"], sources, " ".join(EXAMPLE_PROFILE.values()))
    by_text = {c["text"]: c for c in report["claims"]}
    health = next(c for t, c in by_text.items() if "healthcare costs" in t)
    opinion = next(c for t, c in by_text.items() if "benefits outweigh" in t)
    grounded = next(c for t, c in by_text.items() if t.startswith("Identify where marine debris"))
    assert "new-topic" in health["flags"]
    assert "opinion" in opinion["flags"]
    assert grounded["flags"] == []
