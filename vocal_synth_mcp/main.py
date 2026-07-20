import sys

# MCP's stdio transport requires UTF-8 JSON-RPC framing; Python's default
# stdio encoding otherwise follows the OS/locale default, which on Windows
# is a legacy codepage, not UTF-8. Must happen before anything touches
# stdio. Same fix as reaper-mcp's main.py, same underlying reason.
#
# Guarded per-stream: under pytest, sys.stdin is replaced with a
# DontReadFromInput object that has no .reconfigure(), which would raise
# AttributeError on import. A no-op there is safe — it only matters for the
# real stdio transport this module drives when actually run as a server.
for _stream in (sys.stdout, sys.stdin, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.instructions import load_instructions
from vocal_synth_mcp.tool_registry import register_all_tools

mcp = FastMCP("VocalSynthMCP", instructions=load_instructions())
register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
