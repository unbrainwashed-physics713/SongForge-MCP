import os
import wave

import pytest
import soundfile as sf

from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError
from songforge_mcp_shared.protocol import (
    measure_wav_duration_seconds,
    validate_audio_file_path,
    validate_caption,
    validate_lyrics,
    validate_output_dir_audio_path,
    validate_output_format,
)


def _write_wav(path):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * 44100)


def test_validate_caption_rejects_empty():
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_caption("")
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_caption_accepts_normal_text():
    validate_caption("melodic dubstep, female vocals, dreamy, 150 BPM")  # must not raise


def test_validate_lyrics_rejects_empty():
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_lyrics("")
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_lyrics_requires_structure_tag():
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_lyrics("just some words with no structure tags at all")
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_lyrics_accepts_structured_lyrics():
    validate_lyrics("[verse]\nsome original words\n[chorus]\nmore original words")  # must not raise


def test_measure_wav_duration_seconds(tmp_path):
    path = str(tmp_path / "test.wav")
    framerate = 44100
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * framerate)
    assert measure_wav_duration_seconds(path) == pytest.approx(1.0)


def test_measure_wav_duration_seconds_handles_32bit_float_wav(tmp_path):
    """Regression test: a real ACE-Step "WAV (16-bit)" generation was
    observed actually landing on disk as 32-bit float PCM (format code
    3). The stdlib `wave` module can only read canonical integer PCM and
    raised "unknown format: 3" on this exact file shape — this is why
    measure_wav_duration_seconds reads via soundfile instead."""
    import numpy as np

    path = str(tmp_path / "float32.wav")
    samplerate = 44100
    sf.write(path, np.zeros(samplerate, dtype="float32"), samplerate, subtype="FLOAT")
    assert measure_wav_duration_seconds(path) == pytest.approx(1.0)


def test_measure_wav_duration_seconds_raises_for_missing_file():
    with pytest.raises(SongForgeMCPError) as exc_info:
        measure_wav_duration_seconds("does_not_exist.wav")
    assert exc_info.value.code == ErrorCode.SYNTHESIS_FAILED


def test_validate_audio_file_path_rejects_missing_file(tmp_path):
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_audio_file_path(str(tmp_path / "nope.wav"), param_name="audio_path")
    assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND


def test_validate_output_format_accepts_wav():
    assert validate_output_format("wav") == "wav"


def test_validate_output_format_normalizes_case():
    assert validate_output_format("WAV") == "wav"


def test_validate_output_format_rejects_unsupported_value():
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_output_format("ogg")
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_audio_file_path_rejects_bad_extension(tmp_path):
    path = tmp_path / "not_audio.txt"
    path.write_text("hello")
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_audio_file_path(str(path), param_name="audio_path")
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_audio_file_path_rejects_renamed_non_audio_file(tmp_path):
    path = tmp_path / "fake.wav"
    path.write_text("this is not really a wav file")
    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_audio_file_path(str(path), param_name="audio_path")
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_audio_file_path_accepts_real_wav_anywhere(tmp_path):
    path = tmp_path / "real.wav"
    _write_wav(path)
    resolved = validate_audio_file_path(str(path), param_name="audio_path")
    assert os.path.isfile(resolved)


def test_validate_output_dir_audio_path_accepts_file_inside_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path))
    path = tmp_path / "render.wav"
    _write_wav(path)
    resolved = validate_output_dir_audio_path(str(path), param_name="audio_path")
    assert os.path.isfile(resolved)


def test_validate_output_dir_audio_path_rejects_file_outside_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "renders"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    outside_dir = tmp_path / "elsewhere"
    outside_dir.mkdir()
    path = outside_dir / "sneaky.wav"
    _write_wav(path)

    with pytest.raises(SongForgeMCPError) as exc_info:
        validate_output_dir_audio_path(str(path), param_name="audio_path")
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER
