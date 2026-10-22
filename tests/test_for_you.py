from billbreaker.services import for_you


def test_the_prompt_names_each_answer_by_its_question():
    prompt = for_you._prompt("TX HB 1", "School funding", [{"event": "quick_take", "data": {"tldr": "More money"}}], {"health": "Medicaid"})
    assert "- Health coverage: Medicaid" in prompt
    assert "More money" in prompt and "<breakdown>" in prompt


def test_unknown_or_empty_answers_are_dropped():
    assert for_you.clean_profile({"age": " 65+ ", "income": "", "password": "x"}) == {"age": "65+"}
    assert for_you.clean_profile("not a dict") == {}
