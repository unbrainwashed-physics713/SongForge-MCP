import asyncio

from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import voicebank_tools
from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY


def test_list_voicebanks_returns_every_registered_voicebank():
    mcp = FastMCP("test")
    voicebank_tools.register(mcp)
    tool = mcp._tool_manager.get_tool("list_voicebanks")
    result = asyncio.run(tool.fn())
    ids = {vb["id"] for vb in result["voicebanks"]}
    assert ids == set(VOICEBANK_REGISTRY.keys())
    for vb in result["voicebanks"]:
        assert "license_summary" in vb
        assert "min_midi_note" in vb
        assert "max_midi_note" in vb
