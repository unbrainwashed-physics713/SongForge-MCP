import asyncio
import wave
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import synthesize_tools
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def _write_silent_wav(path: str, seconds: float, framerate: int = 44100) -> None:
    n_frames = int(seconds * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)


def _register() -> FastMCP:
    mcp = FastMCP("test")
    synthesize_tools.register(mcp)
    return mcp


def test_synthesize_vocal_rejects_unknown_voicebank():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    notes = [{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank="does-not-exist"))
    assert exc_info.value.code == ErrorCode.VOICEBANK_NOT_FOUND


def test_synthesize_vocal_rejects_note_outside_voicebank_range():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    voicebank_id = next(iter(synthesize_tools.VOICEBANK_REGISTRY))
    vb = synthesize_tools.VOICEBANK_REGISTRY[voicebank_id]
    notes = [{"pitch": vb.max_midi_note + 1, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank=voicebank_id))
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_synthesize_vocal_returns_wav_path_and_diagnostics(tmp_path):
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    wav_path = str(tmp_path / "out.wav")
    _write_silent_wav(wav_path, seconds=1.0)

    voicebank_id = next(iter(synthesize_tools.VOICEBANK_REGISTRY))
    notes = [
        {"pitch": 60, "duration_beats": 1.0, "lyric": "hi"},
        {"pitch": 62, "duration_beats": 1.0, "lyric": "there"},
    ]
    with patch.object(
        synthesize_tools._client, "synthesize",
        return_value={"wav_path": wav_path, "warnings": ["[variance] Warning: OOV phoneme"]},
    ):
        result = asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank=voicebank_id))

    assert result["wav_path"] == wav_path
    assert result["diagnostics"]["warnings"] == ["[variance] Warning: OOV phoneme"]
    # 2 notes x 1 beat each at 120bpm = 1.0s requested (beats * 60/bpm)
    assert result["diagnostics"]["requested_duration_seconds"] == pytest.approx(1.0)
    assert result["diagnostics"]["actual_duration_seconds"] == pytest.approx(1.0)
