"""Shared constants: ACE-Step checkout paths, timeouts, and safety limits."""
import os
import platform
import subprocess
from pathlib import Path

# This project's own root (the folder containing pyproject.toml), not
# wherever the process happens to be invoked from. Used as the default
# home for generated output — see _default_output_root() below.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_output_root() -> str:
    """Where generated tracks/stems live if SONGFORGE_OUTPUT_DIR isn't
    set. Deliberately a folder inside this repo checkout, not the OS temp
    directory: temp is fine for scratch state, but a system's cleanup
    tools (Windows Storage Sense, etc.) can and do purge it, backup
    software typically skips it, and it's not somewhere a user would
    think to look for a track they just asked for and want to keep — all
    of which were real problems with the previous tempfile-based default.
    Also deliberately NOT a path outside this repo (e.g. a sibling
    project folder): this repo is meant to be cloned standalone by people
    who won't have this developer's particular multi-project directory
    layout, so the default must be self-contained."""
    return str(_PROJECT_ROOT / "output")


def _resolve_output_root() -> str:
    return os.environ.get("SONGFORGE_OUTPUT_DIR", _default_output_root())


def ensure_private_dir(path: str) -> None:
    """Create a directory if missing, and best-effort restrict it to the
    owning user only (0700). Mirrors reaper_mcp_shared.constants."""
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def no_window_popen_kwargs() -> dict:
    """Extra kwargs for subprocess.run/Popen that stop a console window
    from flashing up on Windows. `capture_output`/pipe redirection alone
    does NOT prevent this — a console-subsystem child process (python.exe,
    yt-dlp, audio-separator.exe) still gets a real, visible console window
    of its own on Windows whenever its parent has none to inherit (which
    this server's parent process typically doesn't, being launched by a
    GUI app), unless CREATE_NO_WINDOW is set explicitly. No-op on POSIX,
    where this isn't a thing."""
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def open_with_default_app(path: str) -> None:
    """Opens a file with the OS's default associated application - used
    to auto-play a completed generation so the user doesn't have to find
    it in File Explorer themselves. Best-effort by design: callers must
    not let a failure here break an otherwise-successful tool response,
    since the file path is always returned regardless and remains the
    real result - this is a convenience on top of that, not a
    replacement for it. `os.startfile` is Windows-only in the standard
    library and resolves the OS's actual default app the same way
    double-clicking the file would; `open`/`xdg-open` cover macOS/Linux
    the same way."""
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class Paths:
    # Root of a separately-cloned ace-step/ACE-Step-1.5 checkout. Must be
    # set by the user at install time (see docs/INSTALLATION.md) — ACE-Step
    # is not pip-installable, and its checkpoints (~28GB) are managed by its
    # own app, not this server.
    ACESTEP_HOME = os.environ.get("SONGFORGE_ACESTEP_HOME", "")
    # Override with SONGFORGE_OUTPUT_DIR to redirect generated output
    # anywhere else (e.g. a personal archive folder) — see
    # _default_output_root() for why the built-in default lives inside
    # this repo rather than the OS temp directory.
    OUTPUT_ROOT = _resolve_output_root()
    OUTPUT_DIR = os.path.join(OUTPUT_ROOT, "renders")
    REFERENCE_AUDIO_CACHE = os.path.join(OUTPUT_ROOT, "reference_audio")
    # A library of extracted vocal-only clips, organized one subfolder per
    # named voice (e.g. reference_voices/annika-wells/) - distinct from
    # REFERENCE_AUDIO_CACHE, which is keyed by YouTube video ID for
    # single-generation reference audio, not accumulated per-voice over
    # multiple clips.
    REFERENCE_VOICES_DIR = os.path.join(OUTPUT_ROOT, "reference_voices")


class GradioServer:
    HOST = "127.0.0.1"
    PORT = int(os.environ.get("SONGFORGE_ACESTEP_PORT", "7866"))
    URL = f"http://{HOST}:{PORT}"


class Timeouts:
    # ACE-Step generation time varies a lot, and not just with luck: a
    # real "timed out" complaint traced back to a genuine, documented
    # hardware constraint, not a bug. ACE-Step's own GPU_COMPATIBILITY.md
    # places this project's 12-16GB VRAM tier as "marginal" for the XL
    # DiT model this server uses - it requires real CPU offload +
    # quantization on this tier, and that tier still permits requesting
    # up to 8-minute songs. Long lyrics push toward longer requested
    # durations and more LM/lyric-conditioning work, both of which add
    # real time on a tier that's already trading speed for VRAM fit via
    # offloading - this compounds, it doesn't just add a little. 900s
    # was measured against short/typical clips (~10-100s with no
    # reference audio, ~9 min observed with reference audio) and never
    # validated against a long-lyrics full-length song on this specific
    # tier - raised to give real headroom for that documented case.
    # Still a generous ceiling chosen by reasoning about known
    # constraints, not a precisely tuned/benchmarked value.
    SERVER_STARTUP = 300.0
    GENERATION = 1800.0
    YOUTUBE_DOWNLOAD = 120.0
    # Separation is a short, independent operation (~5-15s observed) - kept
    # apart from GENERATION so a stuck separator doesn't silently wait 15
    # minutes before reporting a problem.
    SEPARATION = 180.0


MAX_CAPTION_LENGTH = 1000     # characters
MAX_LYRICS_LENGTH = 4000      # characters, generous for a full multi-section song
