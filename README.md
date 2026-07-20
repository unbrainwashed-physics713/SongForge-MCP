# Vocal-Synth-MCP

Local, self-hosted MCP server for generating sung vocal stems from an
explicit melody + lyrics — no vocal sample packs, no hiring a vocalist,
full lyrical control. Pairs with [reaper-mcp](../Reaper-MCP) in the same
Claude session: this server does pure vocal synthesis, reaper-mcp's
existing tools handle importing the result into a project.

**Status:** design complete, implementation not started. Read
[`docs/2026-07-21-design.md`](docs/2026-07-21-design.md) before doing
anything else in this repo — it captures the full architecture, the
technology decision (DiffSinger, not OpenUtau or Synthesizer V, and why),
confirmed hardware feasibility, and — importantly — the voice-sourcing/
licensing discussion. Don't skip that section.

## Next steps

See "Open questions for the next session" at the end of the design doc.
This needs a proper implementation plan before any code gets written.
