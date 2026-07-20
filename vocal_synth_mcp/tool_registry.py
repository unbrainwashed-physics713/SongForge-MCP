"""Auto-discovers and registers every tool module in vocal_synth_mcp/tools/."""
import importlib
import logging
import pkgutil
import sys

from mcp.server.fastmcp import FastMCP

import vocal_synth_mcp.tools as tools_package

logger = logging.getLogger(__name__)

_EXPECTED_MODULES = frozenset({"synthesize_tools", "voicebank_tools", "validate_tools"})


def register_all_tools(mcp: FastMCP) -> None:
    """Discover and register every tool module in vocal_synth_mcp/tools/.

    A module counts as a tool provider if it defines register(mcp). If a
    module raises during import or registration, log loudly and keep going
    — one broken file shouldn't take the whole server down.
    """
    registered: list[str] = []
    failures: list[tuple[str, Exception]] = []

    for _finder, name, _ispkg in pkgutil.iter_modules(tools_package.__path__):
        try:
            module = importlib.import_module(f"vocal_synth_mcp.tools.{name}")
        except Exception as e:
            logger.error("IMPORT FAILED for tool module %s: %s", name, e, exc_info=True)
            sys.stderr.write(f"[vocal-synth-mcp] FAILED to import tool module '{name}': {e}\n")
            failures.append((name, e))
            continue

        if not hasattr(module, "register"):
            continue

        try:
            module.register(mcp)
            registered.append(name)
        except Exception as e:
            logger.error("REGISTER FAILED for %s: %s", name, e, exc_info=True)
            sys.stderr.write(f"[vocal-synth-mcp] Tool registration failed for '{name}': {e}\n")
            failures.append((name, e))

    missing = _EXPECTED_MODULES - set(registered) - {n for n, _ in failures}
    if missing:
        sys.stderr.write(f"[vocal-synth-mcp] WARNING: expected module(s) not found on disk: {sorted(missing)}\n")
    sys.stderr.write(f"[vocal-synth-mcp] registered {len(registered)} tool module(s)\n")
    if failures:
        sys.stderr.write(f"[vocal-synth-mcp] {len(failures)} tool module(s) failed to load: {[n for n, _ in failures]}\n")
