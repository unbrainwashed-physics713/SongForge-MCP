# Contributing

- Repo layout mirrors `Reaper-MCP`/`AudacityMCP` — see `docs/ARCHITECTURE.md`.
- Adding a tool: drop a `vocal_synth_mcp/tools/<name>_tools.py` module that
  defines `register(mcp)`. It's auto-discovered — no registry to edit by
  hand, other than adding the module name to `tool_registry.py`'s
  `_EXPECTED_MODULES` (a test enforces this stays in sync).
- Every raised error must be a `VocalSynthMCPError` with a specific
  `ErrorCode` from `vocal_synth_mcp_shared/error_codes.py` — never a bare
  exception.
- No composition logic in this codebase — every tool takes fully explicit
  notes+lyrics. See `docs/2026-07-21-design.md` for why.
- Run `pytest -v` before committing.
