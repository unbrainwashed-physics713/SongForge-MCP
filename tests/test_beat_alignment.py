import numpy as np
import pytest
import soundfile as sf

from songforge_mcp.beat_alignment import _correct_octave_ambiguity, align_to_reference_beat_grid
from songforge_mcp.audio_analysis import analyze_audio


def _write_click_track(path, bpm, samplerate=22050, duration_seconds=12.0, first_beat_offset=0.0):
    """A synthetic percussive click track at an exact BPM, with the first
    click delayed by `first_beat_offset` seconds - simulates two
    independently-generated files at slightly different tempo/phase."""
    n = int(duration_seconds * samplerate)
    audio = np.zeros(n)
    click_len = int(0.02 * samplerate)
    beat_interval = 60.0 / bpm
    rng = np.random.default_rng(0)
    beat_time = first_beat_offset
    while beat_time < duration_seconds:
        start = int(beat_time * samplerate)
        end = min(start + click_len, n)
        audio[start:end] += rng.standard_normal(end - start)
        beat_time += beat_interval
    audio = audio / np.max(np.abs(audio))
    sf.write(str(path), audio * 0.9, samplerate)


def test_align_matches_tempo_and_phase_of_reference(tmp_path):
    reference_path = tmp_path / "reference.wav"
    source_path = tmp_path / "source.wav"
    output_path = tmp_path / "aligned.wav"

    _write_click_track(reference_path, bpm=120.0, first_beat_offset=0.10)
    _write_click_track(source_path, bpm=126.0, first_beat_offset=0.35)

    result = align_to_reference_beat_grid(str(source_path), str(reference_path), str(output_path))

    assert result["reference_tempo"] == pytest.approx(120.0, abs=5.0)
    assert result["source_tempo_before"] == pytest.approx(126.0, abs=5.0)
    assert output_path.exists()

    aligned_info = analyze_audio(str(output_path))
    reference_info = analyze_audio(str(reference_path))
    assert aligned_info["bpm"] == pytest.approx(reference_info["bpm"], abs=2.0)


def test_correct_octave_ambiguity_doubles_half_tempo_reading():
    assert _correct_octave_ambiguity(86.0, 172.0) == pytest.approx(172.0)


def test_correct_octave_ambiguity_halves_double_tempo_reading():
    assert _correct_octave_ambiguity(344.0, 172.0) == pytest.approx(172.0)


def test_correct_octave_ambiguity_leaves_matching_tempo_unchanged():
    assert _correct_octave_ambiguity(171.5, 172.0) == pytest.approx(171.5)


def test_align_raises_on_beatless_audio(tmp_path):
    reference_path = tmp_path / "reference.wav"
    source_path = tmp_path / "silence.wav"
    output_path = tmp_path / "aligned.wav"

    _write_click_track(reference_path, bpm=120.0)
    sf.write(str(source_path), np.zeros(22050 * 2), 22050)

    with pytest.raises(Exception):
        align_to_reference_beat_grid(str(source_path), str(reference_path), str(output_path))
