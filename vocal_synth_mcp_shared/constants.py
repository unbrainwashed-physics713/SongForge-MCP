"""Shared constants: DiffSinger checkout paths, timeouts, and safety limits."""
import os
import tempfile


def ensure_private_dir(path: str) -> None:
    """Create a directory if missing, and best-effort restrict it to the
    owning user only (0700). Mirrors reaper_mcp_shared.constants."""
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


class Paths:
    # Root of a separately-cloned openvpi/DiffSinger checkout. Must be set
    # by the user at install time (see docs/INSTALLATION.md) — DiffSinger
    # is not pip-installable, so this server subprocesses into that clone
    # rather than importing it.
    DIFFSINGER_HOME = os.environ.get("VOCAL_SYNTH_DIFFSINGER_HOME", "")
    OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "vocal_synth_mcp", "renders")


class Timeouts:
    VARIANCE_STAGE = 120.0   # predicts duration/pitch/energy/breathiness/tension
    ACOUSTIC_STAGE = 300.0   # renders audio via the acoustic model + vocoder


# MIDI note range this server accepts without a voicebank-specific override
# (see vocal_synth_mcp_shared/voicebanks.py for per-voicebank ranges, which
# are typically narrower). C2-C6 covers the great majority of pop/EDM lead
# vocal writing.
MIN_MIDI_NOTE = 36  # C2
MAX_MIDI_NOTE = 84  # C6

MAX_NOTES_PER_CALL = 500   # keeps a single .ds file/render to roughly one song section
MAX_LYRIC_LENGTH = 2000    # characters, sanity ceiling on any one lyric string
