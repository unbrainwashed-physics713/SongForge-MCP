"""Plays a finished audio file back to the user immediately.

Delegates straight to the OS's own default-app resolution
(`open_with_default_app`). An earlier version of this module launched
Windows Media Player (`wmplayer.exe`) directly instead, to work around
the classic WMP "which app should open this?" prompt - but live testing
found `wmplayer.exe` creates zero visible windows at all on this Windows
11 system (confirmed via a full `EnumWindows` listing). Windows 11 has
replaced it with a modern "Media Player" app hosted under
`ApplicationFrameHost.exe`, which plain `os.startfile()` (used by
`open_with_default_app`) already launches correctly and visibly - so the
wmplayer-specific code was solving a problem that no longer exists on
this OS and was about to ship a regression.
"""
from songforge_mcp_shared.constants import open_with_default_app


def play_audio_now(path: str) -> None:
    """Plays `path` immediately via the OS's default app for its file type."""
    open_with_default_app(path)
