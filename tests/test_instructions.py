from vocal_synth_mcp.instructions import load_instructions


def test_load_instructions_returns_nonempty_text():
    text = load_instructions()
    assert len(text) > 0


def test_load_instructions_documents_the_note_format():
    text = load_instructions()
    assert "duration_beats" in text
    assert "validate_score" in text
    assert "list_voicebanks" in text
