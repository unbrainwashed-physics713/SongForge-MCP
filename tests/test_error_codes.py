import pytest

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def test_error_carries_code_and_message():
    err = VocalSynthMCPError(ErrorCode.NOTE_OUT_OF_RANGE, "pitch 200 is not a valid MIDI note")
    assert err.code == ErrorCode.NOTE_OUT_OF_RANGE
    assert err.message == "pitch 200 is not a valid MIDI note"


def test_error_string_includes_code_name_and_value():
    err = VocalSynthMCPError(ErrorCode.VOICEBANK_NOT_FOUND, "unknown voicebank 'nope'")
    assert str(err) == "[VOICEBANK_NOT_FOUND (3006)] unknown voicebank 'nope'"


def test_error_codes_are_unique():
    values = [code.value for code in ErrorCode]
    assert len(values) == len(set(values))
