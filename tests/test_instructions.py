from songforge_mcp.instructions import load_instructions


def test_load_instructions_returns_nonempty_text():
    text = load_instructions()
    assert len(text) > 0


def test_load_instructions_documents_the_tool_contract():
    text = load_instructions()
    assert "generate_vocal_track" in text
    assert "check_vocal_track_status" in text
    assert "split_vocal_stems" in text
    assert "advanced_settings" in text


def test_load_instructions_documents_the_polling_requirement():
    text = load_instructions()
    assert "job_id" in text
    assert "say something to the user" in text.lower() or "narrat" in text.lower()


def test_load_instructions_documents_the_real_artist_guardrail():
    text = load_instructions()
    assert "real artist" in text.lower()
