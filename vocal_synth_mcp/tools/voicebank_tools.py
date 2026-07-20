from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY


def register(mcp: FastMCP):
    @mcp.tool()
    async def list_voicebanks() -> dict:
        """List available DiffSinger voicebanks and their ranges/licensing.

        Call this before synthesize_vocal to pick a voicebank id and confirm
        the melody fits its supported MIDI note range.
        """
        return {
            "voicebanks": [
                {
                    "id": vb_id,
                    "name": vb.name,
                    "language": vb.language,
                    "min_midi_note": vb.min_midi_note,
                    "max_midi_note": vb.max_midi_note,
                    "license_summary": vb.license_summary,
                }
                for vb_id, vb in VOICEBANK_REGISTRY.items()
            ]
        }
