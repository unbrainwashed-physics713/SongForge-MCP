# Architecture

How Vocal-Synth-MCP turns an explicit melody + lyrics into a vocal-only
WAV stem.

## Overview

```
┌──────────────┐    stdio    ┌───────────────────┐   subprocess   ┌──────────────┐
│  MCP Client  │◄──────────►│  Vocal-Synth-MCP   │◄───────────────►│  DiffSinger  │
│(AI assistant)│  (JSON-RPC) │      FastMCP       │  (.ds file +    │  (external   │
└──────────────┘             └───────────────────┘   CLI stages)   │   checkout)  │
                                                                     └──────────────┘
```

Unlike reaper-mcp's persistent Lua-bridge IPC (REAPER is a long-running
app), DiffSinger's `scripts/infer.py` is a one-shot CLI — each
`synthesize_vocal` call is two plain `subprocess.run` invocations
(`variance` then `acoustic`), no daemon or heartbeat needed.

## Package layout

```
vocal_synth_mcp/
├── main.py                 # FastMCP entry point
├── tool_registry.py        # Auto-discovers tools/ modules
├── diffsinger_client.py    # Two-stage subprocess wrapper
├── instructions/
│   └── 00_core.md          # Injected system-prompt instructions
└── tools/                  # synthesize_vocal, list_voicebanks, validate_score

vocal_synth_mcp_shared/
├── constants.py            # Paths, timeouts, safety limits
├── error_codes.py          # VocalSynthMCPError + ErrorCode
├── protocol.py             # .ds build/validate/parse
└── voicebanks.py           # Configured voicebank registry
```

## Design decisions

- **Composition stays out of this codebase.** Every tool takes fully
  explicit notes+lyrics. No melody/lyric generation, no auto-retry or
  auto-parameter-adjustment — see `docs/2026-07-21-design.md`.
- **Typed errors.** `VocalSynthMCPError` + `ErrorCode` give the calling
  LLM specific, machine-readable failure reasons instead of a generic
  message — same pattern as reaper-mcp's `ReaperMCPError`.
- **Subprocess, not a library dependency.** DiffSinger isn't
  pip-installable; `DIFFSINGER_HOME` is a separately-cloned checkout
  configured at install time.
- **Vocal-only output, always.** No backing instrumentation is ever
  generated or mixed in.

See [TOOLS.md](TOOLS.md) for the tool reference, or
[../docs/2026-07-21-design.md](../docs/2026-07-21-design.md) for the full
design rationale.
