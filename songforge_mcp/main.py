import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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

from songforge_mcp.instructions import load_instructions
from songforge_mcp.tool_registry import register_all_tools
from songforge_mcp.tools.generate_tools import _client as _acestep_client


@asynccontextmanager
async def _lifespan(_app: FastMCP) -> AsyncIterator[dict]:
    """Starts warming up ACE-Step's server as soon as this MCP server
    itself starts (i.e. as soon as Claude Desktop launches it) instead of
    waiting for the first generate_vocal_track call to discover it's cold
    and pay the multi-minute checkpoint-load cost right when a user is
    waiting on a result. Uses the exact same ACEStepClient instance (and
    its lock) that generate_vocal_track uses — a separate instance here
    would risk two competing launches racing to bind the same port if a
    real request comes in while this is still starting up.

    Fire-and-forget: this schedules the warm-up and returns immediately,
    so it never delays this server's own startup or its ability to accept
    the initialize handshake. Failures (e.g. SONGFORGE_ACESTEP_HOME not
    configured yet) are swallowed here — a real generate_vocal_track call
    will surface the same problem properly through its own error path.
    """
    async def warm_up() -> None:
        try:
            sys.stderr.write("[songforge-mcp] warming up ACE-Step server in the background...\n")
            await _acestep_client.ensure_server_running()
            sys.stderr.write("[songforge-mcp] ACE-Step server is warm and ready\n")
        except Exception as e:
            sys.stderr.write(f"[songforge-mcp] ACE-Step warm-up did not complete: {e}\n")

    warmup_task = asyncio.create_task(warm_up())
    try:
        yield {}
    finally:
        warmup_task.cancel()


mcp = FastMCP("VocalSynthMCP", instructions=load_instructions(), lifespan=_lifespan)
register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
