"""Vocal/instrumental stem separation via audio-separator (BS-Roformer).

BS-Roformer (model_bs_roformer_ep_317_sdr_12.9755.ckpt, audio-separator's
default) was tested against Demucs in this project and left less audible
bleed on ACE-Step output specifically, though neither is perfect — some
synth/reverb bleed into the vocal stem is still expected. This wraps the
`audio-separator` CLI rather than importing it directly, matching this
project's general pattern of subprocessing into external, independently-
versioned tools instead of vendoring them as library dependencies.

Runs from a synchronous method (`separate`) — callers on the asyncio side
must dispatch it via `asyncio.to_thread` (see `tools/separate_tools.py`),
same reasoning as any blocking subprocess call from an async tool.
"""
import os
import platform
import subprocess
import threading
from pathlib import Path

from songforge_mcp_shared.constants import Paths, Timeouts, ensure_private_dir, no_window_popen_kwargs
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError

_SEPARATOR_EXE_NAME = "audio-separator.exe" if platform.system() == "Windows" else "audio-separator"


class SeparatorClient:
    def __init__(self, separator_venv_python: str | None = None):
        self.python_exe = separator_venv_python or os.environ.get(
            "SONGFORGE_SEPARATOR_PYTHON", ""
        )
        ensure_private_dir(Paths.OUTPUT_DIR)
        # audio-separator uses onnxruntime-gpu against the same GPU
        # ACE-Step runs on - a plain threading.Lock (not asyncio.Lock,
        # since this class is driven via asyncio.to_thread rather than
        # natively async) keeps two separation calls from competing for
        # GPU memory at once.
        self._lock = threading.Lock()

    def _require_configured(self) -> str:
        """Returns the resolved path to the audio-separator console
        script living alongside the configured Python interpreter."""
        if not self.python_exe or not os.path.isfile(self.python_exe):
            raise SongForgeMCPError(
                ErrorCode.SEPARATOR_NOT_CONFIGURED,
                "SONGFORGE_SEPARATOR_PYTHON is not set or does not point to a "
                "valid Python interpreter with audio-separator installed. See docs/INSTALLATION.md.",
            )
        separator_exe = os.path.join(os.path.dirname(self.python_exe), _SEPARATOR_EXE_NAME)
        if not os.path.isfile(separator_exe):
            raise SongForgeMCPError(
                ErrorCode.SEPARATOR_NOT_CONFIGURED,
                f"{_SEPARATOR_EXE_NAME} not found alongside {self.python_exe} — "
                "is audio-separator actually installed in that environment?",
            )
        return separator_exe

    def separate(self, audio_path: str) -> dict:
        """Returns {"vocals_path": str, "instrumental_path": str}.

        Idempotent: if this exact source file was already separated
        (matching output files already exist in the stems folder), returns
        those immediately without re-running the separator. A real,
        recurring failure mode is the calling model losing track of an
        earlier result over a long conversation and asking to split the
        same file again — there is no reason to burn GPU time and wait
        through a real separation run twice for the same source."""
        separator_exe = self._require_configured()
        if not os.path.isfile(audio_path):
            raise SongForgeMCPError(
                ErrorCode.FILE_NOT_FOUND, f"audio_path does not exist: {audio_path}"
            )

        out_dir = os.path.join(Paths.OUTPUT_DIR, "stems")
        ensure_private_dir(out_dir)
        stem = Path(audio_path).stem

        existing_vocals = list(Path(out_dir).glob(f"{stem}_(Vocals)_*.wav"))
        existing_instrumental = list(Path(out_dir).glob(f"{stem}_(Instrumental)_*.wav"))
        if existing_vocals and existing_instrumental:
            return {
                "vocals_path": str(existing_vocals[0]),
                "instrumental_path": str(existing_instrumental[0]),
            }

        with self._lock:
            try:
                result = subprocess.run(
                    [separator_exe, audio_path, "--output_dir", out_dir, "--output_format", "wav"],
                    capture_output=True, text=True, timeout=Timeouts.SEPARATION, check=False,
                    **no_window_popen_kwargs(),
                )
            except subprocess.TimeoutExpired as e:
                raise SongForgeMCPError(
                    ErrorCode.SUBPROCESS_TIMEOUT, f"separation exceeded {Timeouts.SEPARATION}s"
                ) from e

        if result.returncode != 0:
            raise SongForgeMCPError(
                ErrorCode.SEPARATION_FAILED,
                f"audio-separator exited {result.returncode}: {result.stderr.strip()[-2000:]}",
            )

        vocals = list(Path(out_dir).glob(f"{stem}_(Vocals)_*.wav"))
        instrumental = list(Path(out_dir).glob(f"{stem}_(Instrumental)_*.wav"))
        if not vocals or not instrumental:
            raise SongForgeMCPError(
                ErrorCode.SEPARATION_FAILED,
                f"separation reported success but expected output files were not found in {out_dir}",
            )
        return {"vocals_path": str(vocals[0]), "instrumental_path": str(instrumental[0])}
