import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import validate_tools
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def _register() -> FastMCP:
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    return mcp


def test_validate_score_accepts_a_valid_sequence():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [
        {"pitch": 60, "duration_beats": 1.0, "lyric": "hel"},
        {"pitch": 62, "duration_beats": 1.0, "lyric": "lo"},
    ]
    result = asyncio.run(tool.fn(notes=notes, bpm=120.0))
    assert result["valid"] is True
    assert result["note_count"] == 2
    assert result["sung_note_count"] == 2
    assert result["total_duration_seconds"] == pytest.approx(1.0)


def test_validate_score_rejects_out_of_range_pitch():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [{"pitch": 200, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0))
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_validate_score_rejects_non_positive_bpm():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=0.0))
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER
