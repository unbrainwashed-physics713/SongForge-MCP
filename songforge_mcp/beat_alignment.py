"""Beat-alignment for mixing an independently-generated instrumental
against a real, unchangeable vocal stem.

Matching an average BPM *number* between two files is not enough: two
independently generated/recorded audio streams "at the same BPM" still
drift out of phase over a multi-minute track unless their beat grids are
actually locked together - even a tiny tempo mismatch (172.3 vs 176, say)
compounds over 4 minutes into the chords landing nowhere near where the
vocal actually is in its phrasing, which alone is enough to make an
otherwise-correct instrumental sound wrong throughout. This module
time-stretches one file to the other's exact measured tempo and then
time-shifts it so their first detected beats coincide, instead of the
naive "start both at sample 0 and hope" approach used earlier.
"""
import numpy as np
import librosa
import soundfile as sf

from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError


def _measure_tempo_and_first_beat(y: np.ndarray, sr: int) -> tuple[float, float]:
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo) if not hasattr(tempo, "__len__") else float(tempo[0])
    if len(beat_frames) == 0:
        raise SongForgeMCPError(
            ErrorCode.INVALID_PARAMETER, "no beats detected in audio - cannot beat-align"
        )
    first_beat_time = float(librosa.frames_to_time(beat_frames[0], sr=sr))
    return tempo, first_beat_time


def _correct_octave_ambiguity(src_tempo: float, ref_tempo: float) -> float:
    """librosa's beat tracker can lock onto half or double a track's true
    tempo - a known, common limitation, especially at fast EDM tempos
    (150+ BPM) where its internal tempo prior biases toward ~120 BPM.
    Confirmed live: the exact same file measured 172.3 BPM when loaded at
    22050 Hz and 87.6 BPM (its true tempo's half) when loaded at 44100 Hz
    for this project's actual reference clip. Since we already have a
    trusted reference tempo to compare against, snap source_tempo to the
    same octave as reference_tempo when their ratio is suspiciously close
    to 0.5 or 2.0, rather than trusting either raw reading blindly."""
    ratio = src_tempo / ref_tempo
    if 0.45 <= ratio <= 0.55:
        return src_tempo * 2
    if 1.8 <= ratio <= 2.2:
        return src_tempo / 2
    return src_tempo


def align_to_reference_beat_grid(source_path: str, reference_path: str, output_path: str) -> dict:
    """Time-stretches `source_path` so its tempo exactly matches
    `reference_path`'s measured tempo, then shifts it so its first
    detected beat lines up with the reference's first detected beat.
    Writes the result (mono, at the reference's native sample rate) to
    `output_path`.

    `reference_path` should be a file with real, reliable rhythmic
    content (a full mix or an instrumental stem) - NOT a vocal-only stem.
    A vocal-only stem has no strong beat transients before the singer
    enters, so beat-tracking it can lock onto "where the voice starts"
    rather than the song's actual beat 1, silently producing a badly
    wrong phase offset.

    This only corrects a single global tempo/phase mismatch - it assumes
    both files are close to constant-tempo throughout (true for most
    EDM/pop backing tracks and for ACE-Step's own generations), not a
    track with real tempo changes mid-song, which would need genuine
    beat-synchronous (not single-ratio) time-warping.

    Returns the measured before/after values so the correction can be
    verified rather than trusted blindly.
    """
    ref_y, ref_sr = librosa.load(reference_path, sr=None, mono=True)
    ref_tempo, ref_first_beat = _measure_tempo_and_first_beat(ref_y, ref_sr)

    src_y, src_sr = librosa.load(source_path, sr=ref_sr, mono=True)
    src_tempo_raw, src_first_beat = _measure_tempo_and_first_beat(src_y, src_sr)
    src_tempo = _correct_octave_ambiguity(src_tempo_raw, ref_tempo)

    rate = ref_tempo / src_tempo
    stretched = librosa.effects.time_stretch(src_y, rate=rate)
    stretched_first_beat = src_first_beat / rate

    offset_samples = int(round((ref_first_beat - stretched_first_beat) * ref_sr))
    if offset_samples > 0:
        aligned = np.concatenate([np.zeros(offset_samples, dtype=stretched.dtype), stretched])
    elif offset_samples < 0:
        aligned = stretched[-offset_samples:]
    else:
        aligned = stretched

    sf.write(output_path, aligned, ref_sr)

    return {
        "reference_tempo": round(ref_tempo, 1),
        "source_tempo_before": round(src_tempo_raw, 1),
        "source_tempo_octave_corrected": round(src_tempo, 1),
        "stretch_rate": round(rate, 4),
        "reference_first_beat": round(ref_first_beat, 3),
        "source_first_beat_before": round(src_first_beat, 3),
        "offset_seconds_applied": round(offset_samples / ref_sr, 3),
        "output_path": output_path,
    }
