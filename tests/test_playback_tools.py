import asyncio

import numpy as np
import pytest
import soundfile as sf
from mcp.server.fastmcp import FastMCP

from songforge_mcp.tools import playback_tools
from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError


def _register() -> FastMCP:
    mcp = FastMCP("test")
    playback_tools.register(mcp)
    return mcp


def _write_tone(path, duration_seconds=1.0, samplerate=48000):
    t = np.linspace(0, duration_seconds, int(duration_seconds * samplerate), endpoint=False)
    data = 0.1 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)


def test_play_audio_rejects_path_outside_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    outside_path = tmp_path / "elsewhere.wav"
    _write_tone(outside_path)

    mcp = _register()
    tool = mcp._tool_manager.get_tool("play_audio")
    with pytest.raises(SongForgeMCPError) as exc_info:
        asyncio.run(tool.fn(audio_path=str(outside_path)))
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_play_audio_plays_file_inside_output_dir(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path)

    played = []
    monkeypatch.setattr(playback_tools, "play_audio_now", played.append)

    mcp = _register()
    tool = mcp._tool_manager.get_tool("play_audio")
    result = asyncio.run(tool.fn(audio_path=str(audio_path)))

    assert result == {"status": "playing", "audio_path": str(audio_path)}
    assert played == [str(audio_path)]
