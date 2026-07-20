from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.diffsinger_client import DiffSingerClient
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import NoteEvent, build_ds_file, measure_wav_duration_seconds
from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY

_client = DiffSingerClient()


def register(mcp: FastMCP):
    @mcp.tool()
    async def synthesize_vocal(
        notes: list[dict], bpm: float, voicebank: str, expressive_params: dict | None = None
    ) -> dict:
        """Render a vocal-only WAV stem from an explicit melody + lyrics.

        This tool does not compose anything — notes and lyrics must already
        be fully decided (by the calling LLM's conversation with the user)
        before calling this. Call validate_score first to catch problems
        cheaply, and list_voicebanks to pick a valid `voicebank` id.

        Args:
            notes: List of {"pitch": int (MIDI note, -1 for rest),
                "duration_beats": float, "lyric": str or null}. One entry
                per sung syllable; rests use lyric=null.
            bpm: Tempo in beats per minute.
            voicebank: A voicebank id from list_voicebanks.
            expressive_params: Optional explicit pitch/energy/breathiness/
                tension curves. Omit to let DiffSinger's variance model
                predict them automatically.
        """
        if voicebank not in VOICEBANK_REGISTRY:
            raise VocalSynthMCPError(
                ErrorCode.VOICEBANK_NOT_FOUND,
                f"unknown voicebank {voicebank!r}. Call list_voicebanks for valid ids.",
            )
        vb = VOICEBANK_REGISTRY[voicebank]
        note_events = [
            NoteEvent(pitch=n["pitch"], duration_beats=n["duration_beats"], lyric=n.get("lyric"))
            for n in notes
        ]
        for i, note in enumerate(note_events):
            if note.pitch != -1 and not (vb.min_midi_note <= note.pitch <= vb.max_midi_note):
                raise VocalSynthMCPError(
                    ErrorCode.NOTE_OUT_OF_RANGE,
                    f"note {i}: pitch {note.pitch} is outside {voicebank}'s range "
                    f"{vb.min_midi_note}-{vb.max_midi_note}",
                )

        ds_entry = build_ds_file(note_events, bpm, expressive_params)
        result = _client.synthesize(ds_entry, experiment=vb.experiment)
        actual_duration = measure_wav_duration_seconds(result["wav_path"])
        requested_beats = sum(n.duration_beats for n in note_events)
        requested_seconds = requested_beats * 60.0 / bpm

        return {
            "wav_path": result["wav_path"],
            "diagnostics": {
                "warnings": result["warnings"],
                "requested_duration_seconds": round(requested_seconds, 3),
                "actual_duration_seconds": round(actual_duration, 3),
            },
        }
