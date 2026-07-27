"""A library of extracted vocal-only clips, organized one folder per
named voice, for building up private reference material for a specific
voice over multiple source clips.

Deliberately separate from reference_audio's existing per-video-ID cache
(REFERENCE_AUDIO_CACHE) - that cache holds one clip per YouTube video for
single-generation use; this library accumulates multiple clips per named
voice over time, correctly labeled so a later session (or the same one,
much later) can find what already exists instead of re-extracting it or
losing track of what a given file actually is.
"""
import os
import re

from songforge_mcp_shared.constants import Paths, ensure_private_dir
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError
from songforge_mcp_shared.protocol import measure_wav_duration_seconds

# A commonly cited practical floor for a usable voice-conversion/SVC
# training set is somewhere in the 10-30+ minute range of real vocal
# audio - not a hard cutoff (some usable results exist below it, quality
# keeps improving above it), but one YouTube song typically yields only
# 1-2 minutes of actual vocal after instrumental sections are excluded,
# so a single clip is essentially never enough on its own. This constant
# exists so that fact is surfaced to the calling AI programmatically
# instead of relying on it remembering to mention it.
RECOMMENDED_MINIMUM_SECONDS = 600.0


def slugify_voice_name(name: str, max_length: int = 60) -> str:
    """Filesystem-safe slug for a voice name (e.g. "Annika Wells" ->
    "annika-wells") - lowercase, alphanumerics and hyphens only."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:max_length].strip("-")


def voice_dir(voice_name: str) -> str:
    slug = slugify_voice_name(voice_name)
    if not slug:
        raise SongForgeMCPError(
            ErrorCode.INVALID_PARAMETER, f"voice_name {voice_name!r} has no usable characters"
        )
    return os.path.join(Paths.REFERENCE_VOICES_DIR, slug)


def list_voice_clips(voice_name: str) -> list[str]:
    """Returns absolute paths of every clip already prepared for this
    voice, or an empty list if none exist yet (not an error - "no clips
    yet" is an expected, normal state, not a failure)."""
    directory = voice_dir(voice_name)
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith((".wav", ".flac", ".mp3"))
    )


def get_voice_library_status(voice_name: str) -> dict:
    """Returns the current state of a voice's reference library: every
    clip's path, how many there are, their combined duration, and whether
    that combined duration meets RECOMMENDED_MINIMUM_SECONDS. Use this
    (not a bare clip count) to judge whether "enough" material exists -
    a handful of short clips can still fall well short of a usable
    total, and one clip essentially never will."""
    clips = list_voice_clips(voice_name)
    total_seconds = sum(measure_wav_duration_seconds(c) for c in clips)
    return {
        "clips": clips,
        "clip_count": len(clips),
        "total_duration_seconds": round(total_seconds, 1),
        "meets_recommended_minimum": total_seconds >= RECOMMENDED_MINIMUM_SECONDS,
        "recommended_minimum_seconds": RECOMMENDED_MINIMUM_SECONDS,
    }


def save_voice_clip(voice_name: str, source_vocals_path: str, source_label: str) -> str:
    """Copies an already-extracted vocal stem into this voice's library
    folder, named so both the voice and the specific source clip are
    identifiable later (e.g. annika-wells/annika-wells_huA8H72ThSo.wav) -
    never just a bare video ID or a bare "vocals.wav", both of which lose
    track of which voice a file belongs to the moment it's looked at
    outside the folder it was created in."""
    directory = voice_dir(voice_name)
    ensure_private_dir(directory)
    slug = slugify_voice_name(voice_name)
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", source_label).strip("_")[:60]
    ext = os.path.splitext(source_vocals_path)[1] or ".wav"
    dest_path = os.path.join(directory, f"{slug}_{safe_label}{ext}")

    with open(source_vocals_path, "rb") as src, open(dest_path, "wb") as dst:
        dst.write(src.read())
    return dest_path
