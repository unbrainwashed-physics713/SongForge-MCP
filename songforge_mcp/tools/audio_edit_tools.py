"""Trim/fade/format-convert a file this server previously produced.

Writing mp3 goes through ffmpeg via subprocess rather than soundfile,
since libsndfile (soundfile's backend) can only write wav/flac directly.
This project already implicitly depends on ffmpeg being on PATH for
YouTube reference-audio downloading (yt_dlp's -x --audio-format wav
needs it) - this tool just makes that dependency load-bearing instead of
incidental, see docs/INSTALLATION.md.
"""
import asyncio
import os
import subprocess
import time

import numpy as np
import soundfile as sf
from mcp.server.fastmcp import FastMCP

from songforge_mcp.shared_state import jobs as _jobs
from songforge_mcp_shared.constants import Paths, Timeouts, ensure_private_dir, no_window_popen_kwargs
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError
from songforge_mcp_shared.protocol import validate_output_dir_audio_path

_SUPPORTED_OUTPUT_FORMATS = frozenset({"wav", "flac", "mp3"})
_NATIVE_SOUNDFILE_FORMATS = frozenset({"wav", "flac"})


def _apply_fades(data: np.ndarray, sr: int, fade_in_seconds: float, fade_out_seconds: float) -> np.ndarray:
    data = data.copy()
    n = len(data)
    if fade_in_seconds > 0:
        fade_len = min(int(fade_in_seconds * sr), n)
        ramp = np.linspace(0.0, 1.0, fade_len)
        if data.ndim == 2:
            ramp = ramp[:, None]
        data[:fade_len] = data[:fade_len] * ramp
    if fade_out_seconds > 0:
        fade_len = min(int(fade_out_seconds * sr), n)
        ramp = np.linspace(1.0, 0.0, fade_len)
        if data.ndim == 2:
            ramp = ramp[:, None]
        data[n - fade_len:] = data[n - fade_len:] * ramp
    return data


def _write_via_ffmpeg(data: np.ndarray, sr: int, out_path: str) -> None:
    tmp_wav = out_path + ".tmp.wav"
    sf.write(tmp_wav, data, sr)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav, out_path],
            capture_output=True, text=True, timeout=Timeouts.FFMPEG_CONVERT, check=False,
            **no_window_popen_kwargs(),
        )
    except FileNotFoundError as e:
        raise SongForgeMCPError(
            ErrorCode.SUBPROCESS_FAILED,
            "ffmpeg was not found on PATH - required to write mp3 output, since soundfile "
            "can only write wav/flac directly. Install ffmpeg and ensure it's on PATH.",
        ) from e
    except subprocess.TimeoutExpired as e:
        raise SongForgeMCPError(
            ErrorCode.SUBPROCESS_TIMEOUT, f"ffmpeg conversion exceeded {Timeouts.FFMPEG_CONVERT}s"
        ) from e
    finally:
        try:
            os.remove(tmp_wav)
        except OSError:
            pass
    if result.returncode != 0:
        raise SongForgeMCPError(
            ErrorCode.SUBPROCESS_FAILED, f"ffmpeg exited {result.returncode}: {result.stderr.strip()[-1500:]}"
        )


def _edit_audio_track_sync(
    resolved_path: str,
    trim_start_seconds: float | None,
    trim_end_seconds: float | None,
    fade_in_seconds: float | None,
    fade_out_seconds: float | None,
    output_format: str | None,
) -> dict:
    info = sf.info(resolved_path)
    duration = info.frames / info.samplerate

    start_seconds = trim_start_seconds or 0.0
    end_seconds = trim_end_seconds if trim_end_seconds is not None else duration
    if start_seconds < 0 or start_seconds >= duration:
        raise SongForgeMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"trim_start_seconds {start_seconds} is outside the file's {duration:.1f}s duration",
        )
    if end_seconds <= start_seconds or end_seconds > duration:
        raise SongForgeMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"trim_end_seconds {end_seconds} must be greater than trim_start_seconds "
            f"({start_seconds}) and at most the file's {duration:.1f}s duration",
        )

    start_frame = int(start_seconds * info.samplerate)
    stop_frame = int(end_seconds * info.samplerate)
    data, sr = sf.read(resolved_path, start=start_frame, stop=stop_frame)
    clip_seconds = (stop_frame - start_frame) / sr

    fade_in = fade_in_seconds or 0.0
    fade_out = fade_out_seconds or 0.0
    if fade_in < 0 or fade_out < 0:
        raise SongForgeMCPError(
            ErrorCode.INVALID_PARAMETER, "fade_in_seconds/fade_out_seconds must not be negative"
        )
    if fade_in + fade_out > clip_seconds:
        raise SongForgeMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"fade_in_seconds + fade_out_seconds ({fade_in + fade_out}) exceeds the trimmed "
            f"clip's length ({clip_seconds:.1f}s)",
        )
    if fade_in > 0 or fade_out > 0:
        data = _apply_fades(data, sr, fade_in, fade_out)

    source_ext = os.path.splitext(resolved_path)[1].lstrip(".").lower()
    fmt = (output_format or (source_ext if source_ext in _SUPPORTED_OUTPUT_FORMATS else "wav")).lower()
    if fmt not in _SUPPORTED_OUTPUT_FORMATS:
        raise SongForgeMCPError(
            ErrorCode.INVALID_PARAMETER,
            f"output_format {output_format!r} is not one of {sorted(_SUPPORTED_OUTPUT_FORMATS)}",
        )

    ensure_private_dir(Paths.OUTPUT_DIR)
    base = os.path.splitext(os.path.basename(resolved_path))[0]
    out_path = os.path.join(Paths.OUTPUT_DIR, f"{base}_edited_{int(time.time())}.{fmt}")

    if fmt in _NATIVE_SOUNDFILE_FORMATS:
        sf.write(out_path, data, sr)
    else:
        _write_via_ffmpeg(data, sr, out_path)

    return {
        "audio_path": out_path,
        "duration_seconds": round(clip_seconds, 1),
        "output_format": fmt,
    }


def register(mcp: FastMCP):
    @mcp.tool(structured_output=False)
    async def edit_audio_track(
        audio_path: str,
        trim_start_seconds: float | None = None,
        trim_end_seconds: float | None = None,
        fade_in_seconds: float | None = None,
        fade_out_seconds: float | None = None,
        output_format: str | None = None,
    ) -> dict:
        """Starts trimming and/or fading a file this server previously
        produced — writes a NEW file, never overwrites the original.
        Returns {"job_id": str} immediately; poll
        check_vocal_track_status(job_id) exactly as for
        generate_vocal_track (same tool, same registry).

        Args:
            audio_path: A file this server previously produced. Must
                resolve inside this server's own output folder — same
                restriction as split_vocal_stems' audio_path.
            trim_start_seconds: Optional start point in seconds (default
                0.0 — keep the beginning).
            trim_end_seconds: Optional end point in seconds (default: the
                file's own full length).
            fade_in_seconds: Optional linear fade-in length in seconds,
                applied after trimming.
            fade_out_seconds: Optional linear fade-out length in seconds,
                applied after trimming.
            output_format: "wav", "flac", or "mp3". Defaults to the
                source file's own format if it's one of these three,
                otherwise "wav". mp3 output requires ffmpeg on PATH (this
                server's YouTube-reference downloading already depends on
                it implicitly) — soundfile can only write wav/flac
                directly.

        On completion, check_vocal_track_status returns audio_path,
        duration_seconds (the trimmed clip's length), and output_format.
        """
        resolved = validate_output_dir_audio_path(audio_path, param_name="audio_path")
        job = _jobs.create()

        async def run_job() -> None:
            try:
                job.result = await asyncio.to_thread(
                    _edit_audio_track_sync,
                    resolved, trim_start_seconds, trim_end_seconds,
                    fade_in_seconds, fade_out_seconds, output_format,
                )
                job.progress = 1.0
                job.message = "Edit complete"
                job.status = "complete"
            except SongForgeMCPError as e:
                job.error = f"[{e.code.name}] {e.message}"
                job.status = "error"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"

        asyncio.create_task(run_job())
        return {"job_id": job.id}
