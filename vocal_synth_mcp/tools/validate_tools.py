from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import NoteEvent, validate_notes


def register(mcp: FastMCP):
    @mcp.tool()
    async def validate_score(notes: list[dict], bpm: float) -> dict:
        """Check a note+lyric sequence for problems before full synthesis.

        Fast pre-check — does not invoke DiffSinger. Catches out-of-range
        notes, missing lyrics, and structural problems so the calling LLM
        can fix them before spending time on a full two-stage render.

        Args:
            notes: List of {"pitch": int (MIDI note, -1 for rest),
                "duration_beats": float, "lyric": str or null}.
            bpm: Tempo in beats per minute.
        """
        if bpm <= 0:
            raise VocalSynthMCPError(ErrorCode.INVALID_PARAMETER, f"bpm must be > 0, got {bpm}")
        note_events = [
            NoteEvent(pitch=n["pitch"], duration_beats=n["duration_beats"], lyric=n.get("lyric"))
            for n in notes
        ]
        validate_notes(note_events)
        total_beats = sum(n.duration_beats for n in note_events)
        return {
            "valid": True,
            "note_count": len(note_events),
            "sung_note_count": sum(1 for n in note_events if n.lyric),
            "total_duration_seconds": round(total_beats * 60.0 / bpm, 3),
        }
