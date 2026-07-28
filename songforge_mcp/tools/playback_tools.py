from mcp.server.fastmcp import FastMCP

from songforge_mcp.media_player import play_audio_now
from songforge_mcp_shared.protocol import validate_output_dir_audio_path


def register(mcp: FastMCP):
    @mcp.tool(structured_output=False)
    async def play_audio(audio_path: str) -> dict:
        """Plays a file this server previously produced, on demand.

        Every completed `generate_vocal_track` already auto-plays its
        result — this tool is the fallback for when that didn't work or
        wasn't visible (e.g. only flashed in the taskbar), or when the
        user asks to hear an earlier result again later in the
        conversation.

        Args:
            audio_path: A file this server previously produced
                (`audio_path`, `vocals_path`, or `instrumental_path`
                from an earlier completed job). Must be inside this
                server's own output folder.
        """
        audio_path = validate_output_dir_audio_path(audio_path, param_name="audio_path")
        play_audio_now(audio_path)
        return {"status": "playing", "audio_path": audio_path}
