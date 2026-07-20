import pkgutil

from mcp.server.fastmcp import FastMCP

import vocal_synth_mcp.tools as tools_package
from vocal_synth_mcp.tool_registry import _EXPECTED_MODULES, register_all_tools


def _modules_on_disk_with_register() -> set[str]:
    found = set()
    for _finder, name, _ispkg in pkgutil.iter_modules(tools_package.__path__):
        module = __import__(f"vocal_synth_mcp.tools.{name}", fromlist=["register"])
        if hasattr(module, "register"):
            found.add(name)
    return found


def test_expected_modules_matches_disk():
    assert _modules_on_disk_with_register() == _EXPECTED_MODULES


def test_register_all_tools_registers_every_expected_module():
    mcp = FastMCP("test")
    register_all_tools(mcp)
    registered_names = {t.name for t in mcp._tool_manager.list_tools()}
    assert {"synthesize_vocal", "list_voicebanks", "validate_score"} <= registered_names
