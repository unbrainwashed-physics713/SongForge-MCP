"""Wire format helpers for DiffSinger's .ds input files and output parsing."""
import wave
from dataclasses import dataclass

from vocal_synth_mcp_shared.constants import MAX_MIDI_NOTE, MAX_NOTES_PER_CALL, MIN_MIDI_NOTE
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError

_MIDI_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class NoteEvent:
    pitch: int          # MIDI note number, or -1 for a rest
    duration_beats: float
    lyric: str | None   # None for a rest


def midi_to_note_name(pitch: int) -> str:
    """60 -> 'C4', matching DiffSinger's note_seq note-name convention."""
    octave = pitch // 12 - 1
    return f"{_MIDI_NAMES[pitch % 12]}{octave}"


def _beats_to_seconds(beats: float, bpm: float) -> float:
    return beats * 60.0 / bpm


def validate_notes(notes: list[NoteEvent]) -> None:
    if not notes:
        raise VocalSynthMCPError(ErrorCode.MISSING_PARAMETER, "notes must contain at least one note")
    if len(notes) > MAX_NOTES_PER_CALL:
        raise VocalSynthMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"{len(notes)} notes exceeds the {MAX_NOTES_PER_CALL}-note limit per call",
        )
    if not any(n.lyric for n in notes):
        raise VocalSynthMCPError(ErrorCode.MISSING_PARAMETER, "notes must include at least one sung (non-rest) note")
    for i, note in enumerate(notes):
        if note.pitch != -1 and not (MIN_MIDI_NOTE <= note.pitch <= MAX_MIDI_NOTE):
            raise VocalSynthMCPError(
                ErrorCode.NOTE_OUT_OF_RANGE,
                f"note {i}: pitch {note.pitch} is outside the supported range "
                f"{MIN_MIDI_NOTE}-{MAX_MIDI_NOTE}",
            )
        if note.duration_beats <= 0:
            raise VocalSynthMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"note {i}: duration_beats must be > 0, got {note.duration_beats}",
            )


def build_ds_file(
    notes: list[NoteEvent], bpm: float, expressive_params: dict | None = None
) -> dict:
    """Build a DiffSinger .ds request from an explicit note+lyric sequence.

    `notes` must already carry one lyric per sung syllable — this server
    does not do text-to-syllable splitting; the calling LLM hands one
    NoteEvent per syllable (rests use lyric=None). Word/syllable -> ARPAbet
    phoneme conversion happens here via g2p_en. "SP" (silence) is used as
    the rest phoneme, matching common DiffSinger English-dictionary
    convention — confirm this against the actual chosen voicebank's
    phoneme dictionary during setup (see docs/INSTALLATION.md).
    """
    validate_notes(notes)
    if bpm <= 0:
        raise VocalSynthMCPError(ErrorCode.INVALID_PARAMETER, f"bpm must be > 0, got {bpm}")

    from g2p_en import G2p

    g2p = G2p()

    note_seq: list[str] = []
    note_dur: list[str] = []
    ph_seq: list[str] = []
    ph_num: list[str] = []

    for note in notes:
        note_seq.append("rest" if note.pitch == -1 else midi_to_note_name(note.pitch))
        note_dur.append(str(round(_beats_to_seconds(note.duration_beats, bpm), 6)))
        if note.lyric:
            phonemes = [p for p in g2p(note.lyric) if p.strip()]
            if not phonemes:
                raise VocalSynthMCPError(
                    ErrorCode.PHONEME_NOT_FOUND,
                    f"could not derive phonemes for lyric {note.lyric!r}",
                )
            ph_seq.extend(phonemes)
            ph_num.append(str(len(phonemes)))
        else:
            ph_seq.append("SP")
            ph_num.append("1")

    ds_entry: dict = {
        "text": "",
        "ph_seq": " ".join(ph_seq),
        "ph_num": " ".join(ph_num),
        "note_seq": " ".join(note_seq),
        "note_dur": " ".join(note_dur),
        "input_type": "phoneme",
    }
    if expressive_params:
        for key in ("f0_seq", "energy", "breathiness", "voicing", "tension"):
            if key in expressive_params:
                ds_entry[key] = expressive_params[key]
    return ds_entry


def parse_stage_output(stdout: str, stderr: str, stage: str) -> list[str]:
    """Extract warning lines from a DiffSinger CLI stage's output.

    DiffSinger's inference scripts print progress/warnings to stderr; lines
    mentioning "warning" or "oov" (out-of-vocabulary phoneme) are surfaced
    as diagnostics rather than silently dropped.
    """
    warnings = []
    for line in stderr.splitlines():
        if "warning" in line.lower() or "oov" in line.lower():
            warnings.append(f"[{stage}] {line.strip()}")
    return warnings


def measure_wav_duration_seconds(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()
