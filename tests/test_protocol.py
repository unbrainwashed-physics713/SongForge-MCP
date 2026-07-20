import wave

import pytest

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import (
    NoteEvent,
    build_ds_file,
    measure_wav_duration_seconds,
    midi_to_note_name,
    parse_stage_output,
    validate_notes,
)


def test_midi_to_note_name_middle_c():
    assert midi_to_note_name(60) == "C4"


def test_midi_to_note_name_sharp():
    assert midi_to_note_name(61) == "C#4"


def test_validate_notes_rejects_empty_list():
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes([])
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_notes_rejects_all_rests():
    notes = [NoteEvent(pitch=-1, duration_beats=1.0, lyric=None)]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_notes_rejects_out_of_range_pitch():
    notes = [NoteEvent(pitch=200, duration_beats=1.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_validate_notes_rejects_zero_duration():
    notes = [NoteEvent(pitch=60, duration_beats=0.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_notes_rejects_rest_with_lyric():
    notes = [NoteEvent(pitch=-1, duration_beats=1.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_notes_rejects_pitched_note_without_lyric():
    notes = [
        NoteEvent(pitch=60, duration_beats=1.0, lyric="hi"),
        NoteEvent(pitch=62, duration_beats=1.0, lyric=None),
    ]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_notes_accepts_a_valid_sequence():
    notes = [
        NoteEvent(pitch=60, duration_beats=1.0, lyric="hel"),
        NoteEvent(pitch=-1, duration_beats=0.5, lyric=None),
        NoteEvent(pitch=62, duration_beats=1.0, lyric="lo"),
    ]
    validate_notes(notes)  # must not raise


def test_build_ds_file_produces_matching_length_sequences():
    notes = [
        NoteEvent(pitch=60, duration_beats=1.0, lyric="hi"),
        NoteEvent(pitch=-1, duration_beats=1.0, lyric=None),
    ]
    ds = build_ds_file(notes, bpm=120.0)
    note_seq = ds["note_seq"].split()
    note_dur = ds["note_dur"].split()
    assert note_seq == ["C4", "rest"]
    assert len(note_dur) == 2
    # 1 beat at 120bpm = 0.5s
    assert float(note_dur[0]) == pytest.approx(0.5)


def test_build_ds_file_rejects_non_positive_bpm():
    notes = [NoteEvent(pitch=60, duration_beats=1.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        build_ds_file(notes, bpm=0.0)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_build_ds_file_includes_optional_expressive_params():
    notes = [NoteEvent(pitch=60, duration_beats=1.0, lyric="hi")]
    ds = build_ds_file(notes, bpm=120.0, expressive_params={"f0_seq": "220 220"})
    assert ds["f0_seq"] == "220 220"


def test_parse_stage_output_extracts_warning_lines():
    stderr = "loading checkpoint...\nWarning: OOV phoneme for 'xyz'\ndone\n"
    warnings = parse_stage_output(stdout="", stderr=stderr, stage="variance")
    assert warnings == ["[variance] Warning: OOV phoneme for 'xyz'"]


def test_parse_stage_output_returns_empty_list_when_no_warnings():
    assert parse_stage_output(stdout="ok", stderr="done\n", stage="acoustic") == []


def test_measure_wav_duration_seconds(tmp_path):
    path = str(tmp_path / "test.wav")
    framerate = 44100
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * framerate)  # exactly 1 second
    assert measure_wav_duration_seconds(path) == pytest.approx(1.0)


def test_measure_wav_duration_seconds_raises_on_missing_file(tmp_path):
    path = str(tmp_path / "does_not_exist.wav")
    with pytest.raises(VocalSynthMCPError) as exc_info:
        measure_wav_duration_seconds(path)
    assert exc_info.value.code == ErrorCode.SYNTHESIS_FAILED
