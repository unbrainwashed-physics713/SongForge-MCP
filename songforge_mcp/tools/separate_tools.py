import asyncio

from mcp.server.fastmcp import FastMCP

from songforge_mcp.shared_state import jobs as _jobs, separator_client as _client
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError
from songforge_mcp_shared.protocol import validate_output_dir_audio_path


def register(mcp: FastMCP):
    @mcp.tool(structured_output=False)
    async def split_vocal_stems(audio_path: str) -> dict:
        """Start splitting a full mix into a vocals-only stem and an
        instrumental-only stem via BS-Roformer separation. Returns
        {"job_id": str} immediately — poll check_vocal_track_status(job_id)
        exactly as for generate_vocal_track (same tool, same registry);
        on completion it returns vocals_path/instrumental_path instead of
        audio_path. Idempotent — splitting an already-split file returns
        the existing stems instantly instead of re-running.

        Some synth/reverb bleed into the vocal stem is a known limitation
        of the separation itself.

        Args:
            audio_path: A file this server previously produced (typically
                generate_vocal_track's audio_path). Must be inside this
                server's own output folder.
        """
        audio_path = validate_output_dir_audio_path(audio_path, param_name="audio_path")
        job = _jobs.create()

        async def run_job() -> None:
            try:
                job.message = f"Separating {audio_path}"
                result = await asyncio.to_thread(_client.separate, audio_path)
                job.result = {
                    "vocals_path": result["vocals_path"],
                    "instrumental_path": result["instrumental_path"],
                }
                job.progress = 1.0
                job.message = "Separation complete"
                job.status = "complete"
            except SongForgeMCPError as e:
                job.error = f"[{e.code.name}] {e.message}"
                job.status = "error"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"

        asyncio.create_task(run_job())
        return {"job_id": job.id}
