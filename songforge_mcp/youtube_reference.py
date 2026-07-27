"""Download audio from a YouTube URL for use as ACE-Step reference audio.

ACE-Step's own source (acestep/core/generation/handler/conditioning_embed.py)
shows reference audio is conditioned on via a real acoustic VAE latent of
the reference clip, not a narrow vocal-timbre-only signal as ACE-Step's
own UI text implies — so besides voice character, this plausibly also
nudges instrumentation/production texture toward the reference. It does
not carry over melody, rhythm, or lyrical content (those come from the
generation's own text/lyric conditioning). This is a style reference,
not a way to copy a track's composition. Private/prototype use only,
matching this project's existing use of licensed sample-pack material as
reference/training data — not for redistributing the downloaded audio
itself.
"""
import os
import re
import subprocess

from songforge_mcp_shared.constants import Paths, Timeouts, ensure_private_dir, no_window_popen_kwargs
from songforge_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError

_VIDEO_ID_PATTERNS = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)


def _extract_video_id(url: str) -> str | None:
    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _safe_filename(name: str) -> str:
    """yt-dlp output filenames can contain characters (&, parentheses)
    that broke Playwright's file upload in testing — sanitize to be safe."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:80]


class YouTubeReferenceClient:
    def __init__(self, ytdlp_python: str | None = None):
        self.python_exe = ytdlp_python or os.environ.get("SONGFORGE_YTDLP_PYTHON", "")
        ensure_private_dir(Paths.REFERENCE_AUDIO_CACHE)

    def _require_configured(self) -> None:
        if not self.python_exe or not os.path.isfile(self.python_exe):
            raise VocalSynthMCPError(
                ErrorCode.ACESTEP_NOT_CONFIGURED,
                "SONGFORGE_YTDLP_PYTHON is not set or does not point to a valid "
                "Python interpreter with yt-dlp installed.",
            )

    def download(self, youtube_url: str) -> str:
        """Returns the local path to the downloaded/converted wav file."""
        self._require_configured()
        video_id = _extract_video_id(youtube_url or "")
        if not video_id:
            raise VocalSynthMCPError(
                ErrorCode.INVALID_PARAMETER, f"not a recognizable YouTube URL: {youtube_url!r}"
            )

        # yt-dlp's own -o template uses the same %(id)s it extracts
        # internally, so the deterministic output path can be computed
        # up front rather than parsed out of stdout — parsing stdout for
        # an "[ExtractAudio] Destination: ..." line broke silently on a
        # cache hit (yt-dlp skips re-encoding and never prints that line
        # if a matching file already exists), which would otherwise raise
        # a false SYNTHESIS_FAILED on a perfectly good cached download.
        expected_path = os.path.join(Paths.REFERENCE_AUDIO_CACHE, f"{video_id}.wav")
        if os.path.isfile(expected_path):
            return self._rename_to_safe_name(expected_path)

        out_template = os.path.join(Paths.REFERENCE_AUDIO_CACHE, "%(id)s.%(ext)s")
        try:
            result = subprocess.run(
                [self.python_exe, "-m", "yt_dlp", "-x", "--audio-format", "wav",
                 "-o", out_template, youtube_url],
                capture_output=True, text=True, timeout=Timeouts.YOUTUBE_DOWNLOAD, check=False,
                **no_window_popen_kwargs(),
            )
        except subprocess.TimeoutExpired as e:
            raise VocalSynthMCPError(
                ErrorCode.SUBPROCESS_TIMEOUT,
                f"YouTube download exceeded {Timeouts.YOUTUBE_DOWNLOAD}s",
            ) from e
        if result.returncode != 0:
            raise VocalSynthMCPError(
                ErrorCode.SUBPROCESS_FAILED,
                f"yt-dlp exited {result.returncode}: {result.stderr.strip()[-1500:]}",
            )

        if not os.path.isfile(expected_path):
            raise VocalSynthMCPError(
                ErrorCode.SYNTHESIS_FAILED,
                f"yt-dlp reported success but expected output file was not found: {expected_path}",
            )
        return self._rename_to_safe_name(expected_path)

    @staticmethod
    def _rename_to_safe_name(downloaded_path: str) -> str:
        base = _safe_filename(os.path.splitext(os.path.basename(downloaded_path))[0])
        safe_path = os.path.join(Paths.REFERENCE_AUDIO_CACHE, f"{base}.wav")
        if downloaded_path != safe_path and not os.path.isfile(safe_path):
            os.replace(downloaded_path, safe_path)
            return safe_path
        return downloaded_path if downloaded_path == safe_path else safe_path
