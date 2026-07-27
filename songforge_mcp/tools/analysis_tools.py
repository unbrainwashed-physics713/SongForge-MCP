import asyncio

from mcp.server.fastmcp import FastMCP

from songforge_mcp.audio_analysis import analyze_audio
from songforge_mcp.shared_state import jobs as _jobs
from songforge_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from songforge_mcp_shared.protocol import validate_audio_file_path


def register(mcp: FastMCP):
    @mcp.tool()
    async def analyze_reference_audio(audio_path: str) -> dict:
        """Starts measuring real BPM and musical key from an audio file
        (tempo tracking + key-profile correlation) — not a guess. Returns
        {"job_id": str} immediately; poll check_vocal_track_status(job_id)
        exactly as for generate_vocal_track (same tool, same registry).
        Usually finishes in a few seconds, but duration scales with the
        input file's length with no fixed cap, so this still goes through
        the job/poll pattern rather than blocking.

        Feed the completed result into generate_vocal_track's
        advanced_settings, e.g. {"BPM (Beats Per Minute)": result["bpm"],
        "Key": f"{result['key']} {result['mode'].title()}"}.

        Does NOT detect chord progression — that needs a real chord chart
        (identify the song, look it up via web search against Chordify/
        Ultimate-Guitar/etc., then put it directly in the caption, e.g.
        "chord progression: Gb - Db - Ab - Bbm") since ACE-Step has no
        chord-sequence input. Useful as a key cross-check, or when no
        chord chart exists (e.g. private/unreleased audio).

        Args:
            audio_path: Any real audio file — not restricted to this
                server's own output folder.

        On completion, check_vocal_track_status returns bpm, key, mode,
        key_confidence, and duration_seconds.
        """
        resolved = validate_audio_file_path(audio_path, param_name="audio_path")
        job = _jobs.create()

        async def run_job() -> None:
            try:
                job.result = await asyncio.to_thread(analyze_audio, resolved)
                job.progress = 1.0
                job.message = "Analysis complete"
                job.status = "complete"
            except VocalSynthMCPError as e:
                job.error = f"[{e.code.name}] {e.message}"
                job.status = "error"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"

        asyncio.create_task(run_job())
        return {"job_id": job.id}
