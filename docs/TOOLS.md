# Tools

## `validate_score(notes, bpm) -> dict`

Fast pre-check for a note+lyric sequence. Does not invoke DiffSinger.

Returns `{"valid": true, "note_count": int, "sung_note_count": int, "total_duration_seconds": float}`
or raises `VocalSynthMCPError` (`NOTE_OUT_OF_RANGE`, `INVALID_PARAMETER`,
`MISSING_PARAMETER`).

## `list_voicebanks() -> dict`

Returns `{"voicebanks": [{"id", "name", "language", "min_midi_note", "max_midi_note", "license_summary"}, ...]}`.

## `synthesize_vocal(notes, bpm, voicebank, expressive_params=None) -> dict`

Renders a vocal-only WAV stem.

- `notes`: `[{"pitch": int (-1 for rest), "duration_beats": float, "lyric": str | null}]`
- `voicebank`: an id from `list_voicebanks`
- `expressive_params`: optional `{"f0_seq"/"energy"/"breathiness"/"voicing"/"tension": str}` — omit for automatic prediction

Returns `{"wav_path": str, "diagnostics": {"warnings": list[str], "requested_duration_seconds": float, "actual_duration_seconds": float}}`
or raises `VocalSynthMCPError` (`VOICEBANK_NOT_FOUND`, `NOTE_OUT_OF_RANGE`,
`DIFFSINGER_NOT_CONFIGURED`, `SUBPROCESS_TIMEOUT`, `VARIANCE_STAGE_FAILED`,
`ACOUSTIC_STAGE_FAILED`, `SYNTHESIS_FAILED`).
