import os

import numpy as np
import pytest
import soundfile as sf

from songforge_mcp.voice_reference_library import (
    RECOMMENDED_MINIMUM_SECONDS,
    get_voice_library_status,
    list_voice_clips,
    save_voice_clip,
    slugify_voice_name,
    voice_dir,
)
from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import SongForgeMCPError


def _write_tone(path, duration_seconds, samplerate=48000):
    t = np.linspace(0, duration_seconds, int(duration_seconds * samplerate), endpoint=False)
    data = 0.1 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)


def test_slugify_voice_name_produces_hyphenated_lowercase_slug():
    assert slugify_voice_name("Annika Wells") == "annika-wells"


def test_voice_dir_rejects_empty_slug():
    with pytest.raises(SongForgeMCPError):
        voice_dir("!!!")


def test_list_voice_clips_returns_empty_list_when_no_folder_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_VOICES_DIR", str(tmp_path / "reference_voices"))
    assert list_voice_clips("Nobody Yet") == []


def test_save_voice_clip_labels_with_voice_name_and_source(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_VOICES_DIR", str(tmp_path / "reference_voices"))
    source_path = tmp_path / "raw_vocals.wav"
    _write_tone(source_path, 1.0)

    dest = save_voice_clip("Annika Wells", str(source_path), "huA8H72ThSo")

    assert os.path.isfile(dest)
    assert "annika-wells" in os.path.basename(dest)
    assert "huA8H72ThSo" in os.path.basename(dest)
    assert dest in list_voice_clips("Annika Wells")


def test_get_voice_library_status_sums_duration_across_clips(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_VOICES_DIR", str(tmp_path / "reference_voices"))
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    _write_tone(source_a, 2.0)
    _write_tone(source_b, 3.0)
    save_voice_clip("Annika Wells", str(source_a), "song_one")
    save_voice_clip("Annika Wells", str(source_b), "song_two")

    status = get_voice_library_status("Annika Wells")

    assert status["clip_count"] == 2
    assert status["total_duration_seconds"] == pytest.approx(5.0, abs=0.1)
    assert status["meets_recommended_minimum"] is False
    assert status["recommended_minimum_seconds"] == RECOMMENDED_MINIMUM_SECONDS


def test_get_voice_library_status_reports_met_minimum(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_VOICES_DIR", str(tmp_path / "reference_voices"))
    monkeypatch.setattr(
        "songforge_mcp.voice_reference_library.RECOMMENDED_MINIMUM_SECONDS", 1.0
    )
    source = tmp_path / "a.wav"
    _write_tone(source, 2.0)
    save_voice_clip("Annika Wells", str(source), "song_one")

    status = get_voice_library_status("Annika Wells")
    assert status["meets_recommended_minimum"] is True
