# Vocal-Synth-MCP

Local, self-hosted MCP server for generating sung vocal stems from an
explicit melody + lyrics — no vocal sample packs, no hiring a vocalist,
full lyrical control. Pairs with [reaper-mcp](../Reaper-MCP) in the same
Claude session: this server does pure vocal synthesis, reaper-mcp's
existing tools handle importing the result into a project.

**Status:** v1 implemented. See
[`docs/2026-07-21-design.md`](docs/2026-07-21-design.md) for the full
design rationale (technology decision, voicebank licensing discussion),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it's built, and
[`docs/INSTALLATION.md`](docs/INSTALLATION.md) to set it up — DiffSinger
itself is a separate, non-pip-installable checkout you clone yourself.

## Next steps

Manual end-to-end verification (real DiffSinger checkout + the LUNAI
Katyusha voicebank) is tracked in
`docs/superpowers/plans/2026-07-21-vocal-synth-mcp-v1.md`'s final task.
Fine-tuning on personal vocal libraries (v2) is deferred — see the design
doc's "Voice sourcing" section before touching that.
