import os
import time

from mcp.server.fastmcp import FastMCP

from songforge_mcp.shared_state import jobs as _jobs
from songforge_mcp_shared.constants import Paths, ensure_private_dir
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError
from songforge_mcp_shared.protocol import validate_output_dir_audio_path

try:
    import soundfile as sf
except ImportError:  # pragma: no cover - soundfile is a hard dependency in practice
    sf = None


def _best_effort_duration_seconds(path: str) -> float | None:
    if sf is None:
        return None
    try:
        info = sf.info(path)
        return round(info.frames / info.samplerate, 1)
    except Exception:
        # mp3/other formats libsndfile can't read, or a corrupt file -
        # duration is a nice-to-have here, never worth failing the whole
        # listing over.
        return None


def register(mcp: FastMCP):
    @mcp.tool()
    def list_generated_tracks(limit: int = 50) -> list[dict]:
        """Lists finished tracks sitting in this server's output folder,
        newest first — for when a past generation's job_id has been lost
        (jobs are in-memory only and don't survive a server restart) or
        the user asks what's already been made. Does not include
        split-out stems (see split_vocal_stems) — only full-mix renders.

        Args:
            limit: Maximum number of tracks to return (default 50, newest
                first).

        Returns a list of {"path", "filename", "size_bytes",
        "modified_at" (unix timestamp), "duration_seconds" (best-effort,
        None if it couldn't be read)}.
        """
        if not os.path.isdir(Paths.OUTPUT_DIR):
            return []

        entries = []
        with os.scandir(Paths.OUTPUT_DIR) as it:
            for entry in it:
                if not entry.is_file():
                    continue  # skips the stems/ subfolder and any other dirs
                stat = entry.stat()
                entries.append(
                    {
                        "path": entry.path,
                        "filename": entry.name,
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "duration_seconds": _best_effort_duration_seconds(entry.path),
                    }
                )

        entries.sort(key=lambda e: e["modified_at"], reverse=True)
        return entries[: max(0, limit)]

    @mcp.tool()
    def list_recent_jobs(limit: int = 20) -> list[dict]:
        """Lists recent background jobs (from generate_vocal_track,
        generate_vocal_track_takes, split_vocal_stems,
        analyze_reference_audio, or transcribe_instrumental_to_midi),
        newest first — for when a job_id has been lost mid-conversation.
        Jobs are in-memory only: finished/errored jobs older than 1 hour
        are evicted, and none survive a server restart.

        Args:
            limit: Maximum number of jobs to return (default 20, newest
                first).

        Returns a list of {"job_id", "status", "progress", "message",
        "created_at" (unix timestamp)} — call check_vocal_track_status
        for a job's full result rather than expecting it here.
        """
        return [
            {
                "job_id": job.id,
                "status": job.status,
                "progress": round(job.progress, 2),
                "message": job.message,
                "created_at": job.created_at,
            }
            for job in _jobs.list_all()[: max(0, limit)]
        ]

    @mcp.tool()
    def delete_generated_track(audio_path: str) -> dict:
        """Moves a file this server previously produced (a full-mix
        render or a stem) out of the output folder and into a `.trash`
        subfolder — NOT a permanent delete. Deliberately reversible: the
        calling model (or a manipulated/injected instruction) being wrong
        about what's safe to remove should never be able to permanently
        destroy a generation. To actually reclaim disk space, empty
        `.trash` manually via File Explorer — there is no tool for that,
        on purpose.

        Use list_generated_tracks first to see what's actually on disk.

        Args:
            audio_path: A file this server previously produced. Must
                resolve inside this server's own output folder (renders
                or its stems subfolder) — same restriction as
                split_vocal_stems' audio_path.

        Returns {"status": "moved_to_trash", "audio_path": the original
        path, "trash_path": where it actually is now}.
        """
        resolved = validate_output_dir_audio_path(audio_path, param_name="audio_path")
        # Computed from Paths.OUTPUT_ROOT at call time, not stored as its
        # own derived constant - a derived constant would be computed once
        # at import time and silently stop following SONGFORGE_OUTPUT_DIR
        # overrides (or a test's monkeypatch of Paths.OUTPUT_ROOT) made
        # afterward, exactly the bug this project's own tests caught when
        # a similar shortcut was tried for the stems folder.
        trash_dir = os.path.join(Paths.OUTPUT_ROOT, ".trash")
        ensure_private_dir(trash_dir)

        filename = os.path.basename(resolved)
        trash_path = os.path.join(trash_dir, filename)
        if os.path.exists(trash_path):
            # Same filename already trashed earlier - keep both rather
            # than silently overwriting/losing the older one.
            stem, ext = os.path.splitext(filename)
            trash_path = os.path.join(trash_dir, f"{stem}_{int(time.time())}{ext}")

        try:
            os.replace(resolved, trash_path)
        except OSError as e:
            raise SongForgeMCPError(
                ErrorCode.SUBPROCESS_FAILED, f"could not move {resolved} to trash: {e}"
            ) from e
        return {"status": "moved_to_trash", "audio_path": resolved, "trash_path": trash_path}
