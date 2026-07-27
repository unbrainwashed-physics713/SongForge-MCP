import asyncio
import os

from mcp.server.fastmcp import FastMCP

from songforge_mcp.separator_client import SeparatorClient
from songforge_mcp.shared_state import jobs as _jobs
from songforge_mcp.voice_reference_library import get_voice_library_status, save_voice_clip
from songforge_mcp.youtube_reference import YouTubeReferenceClient
from songforge_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError

_youtube_client = YouTubeReferenceClient()
_separator_client = SeparatorClient()


def register(mcp: FastMCP):
    @mcp.tool()
    async def prepare_voice_reference(voice_name: str, youtube_url: str | None = None) -> dict:
        """Checks whether reference vocal clips already exist for a named
        voice, or prepares a new one from a YouTube link.

        Call with ONLY voice_name first (no youtube_url) whenever the user
        wants to use a particular voice. Two possible results:
        - {"status": "found", ...} — includes total_duration_seconds and
          meets_recommended_minimum. One song typically yields only 1-2
          minutes of actual vocal once instrumental sections are excluded,
          so a single clip essentially never meets the recommended
          minimum (currently 600s) — if meets_recommended_minimum is
          False, tell the user how much they have and that more clips
          (ideally from different songs) are needed, don't treat one clip
          as done.
        - {"status": "not_found", "message": ...} — none exist yet. Ask
          the user to paste a YouTube link for a song featuring this
          voice, and recommend an acoustic version if one exists (sparser
          instrumentation separates into a cleaner vocal). Set the
          expectation up front that multiple videos will likely be
          needed, not just one. Do not search for or guess a link
          yourself.

        Once the user gives a youtube_url, call this again with BOTH
        voice_name and youtube_url to actually prepare it — this returns
        {"job_id": str} immediately (downloads the audio, separates the
        vocal, and saves it into this voice's own library folder, clearly
        labeled with both the voice name and source). Poll with
        check_vocal_track_status(job_id) exactly as for
        generate_vocal_track (same tool, same registry); on completion it
        returns the same found-style status (clips, total_duration_seconds,
        meets_recommended_minimum) so you can tell the user whether to
        keep going or stop.

        Args:
            voice_name: The voice to check/prepare, e.g. "Annika Wells".
            youtube_url: Only pass this once the user has supplied a real
                link — omit it for the initial check.
        """
        if youtube_url is None:
            status = get_voice_library_status(voice_name)
            if status["clips"]:
                return {"status": "found", **status}
            return {
                "status": "not_found",
                "message": (
                    f"No reference clips exist yet for '{voice_name}'. Ask the user to "
                    "paste a YouTube link for a song featuring this voice — recommend an "
                    "acoustic version if one exists, since sparser instrumentation "
                    "separates into a cleaner vocal. One video will almost certainly not "
                    "be enough on its own (typically only 1-2 minutes of usable vocal per "
                    "song) — mention that several more will likely be needed too. Call "
                    "this tool again with that youtube_url once you have one."
                ),
            }

        job = _jobs.create()

        async def run_job() -> None:
            try:
                job.message = f"Downloading {youtube_url}"
                downloaded_path = await asyncio.to_thread(_youtube_client.download, youtube_url)
                job.message = "Separating vocals"
                stems = await asyncio.to_thread(_separator_client.separate, downloaded_path)
                source_label = os.path.splitext(os.path.basename(downloaded_path))[0]
                await asyncio.to_thread(save_voice_clip, voice_name, stems["vocals_path"], source_label)
                job.result = {"status": "prepared", **get_voice_library_status(voice_name)}
                job.progress = 1.0
                job.message = "Voice reference prepared"
                job.status = "complete"
            except VocalSynthMCPError as e:
                job.error = f"[{e.code.name}] {e.message}"
                job.status = "error"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"

        asyncio.create_task(run_job())
        return {"job_id": job.id}
