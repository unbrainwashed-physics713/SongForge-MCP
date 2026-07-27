# SongForge-MCP

A local MCP server that turns Claude into the operator of [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5),
an open-source AI music generation model, so you don't have to.

ACE-Step 1.5 is genuinely capable — but its own interface exposes around
seventy interdependent generation settings, and getting a good result out
of it depends on a number of non-obvious defaults and interactions
between them. SongForge-MCP removes that layer entirely: you describe
the track you want in conversation, and Claude calls this server to
produce it, handling every underlying setting correctly on your behalf.
You never touch a settings panel.

## What this gives you

- **`generate_vocal_track`** — produce a complete original track (vocals
  and instrumentation together) from a style description and full
  lyrics, in the genre and mood you ask for.
- **`split_vocal_stems`** — separate a generated track into an isolated
  vocal stem and an isolated instrumental stem, so the vocal can be
  dropped into your own production rather than used as-is.
- **Reference-audio style matching** — point a generation at a specific
  vocal sample or a YouTube link, and the result adopts that voice's
  timbre and performance character. It does not copy the reference's
  melody, rhythm, or lyrics — those still come entirely from what you
  ask Claude to write.
- **Guardrails, not guesswork.** Every setting this server doesn't
  explicitly need is left at ACE-Step's own proven-correct default,
  rather than reconstructed by guesswork — the approach that produced
  reliable results after every other approach silently produced noise.
  An `advanced_settings` override is available for the rare case where a
  specific ACE-Step setting genuinely needs to change.

## Getting started

**Recommended hardware:** an NVIDIA GPU with **≥12GB VRAM** (≥20GB to run
without CPU offload), plus **~40GB free disk space** for the ACE-Step 1.5
XL-SFT model this server is configured to use. See
[System requirements](docs/INSTALLATION.md#system-requirements) in the
install doc for the full breakdown (including what happens on lower-VRAM
or GPU-less machines) — these numbers come from ACE-Step 1.5's own
published requirements, not a guess.

1. Run `install.bat` (Windows) or `install.sh` (Linux/macOS) — see
   [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for exactly what each
   step does and what to do if one fails. It provisions everything end to
   end, including Python itself on Windows if it isn't already on your
   system.
2. Point Claude Desktop's MCP configuration at this server — also covered
   in `docs/INSTALLATION.md`.
3. Ask for a track in plain language. See [`docs/TOOLS.md`](docs/TOOLS.md)
   for the full tool reference and example requests.

## Documentation

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — install and configure,
  step by step.
- [`docs/TOOLS.md`](docs/TOOLS.md) — what each tool does and how to ask
  for what you want.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how this server
  actually drives ACE-Step under the hood, for anyone maintaining or
  extending it.

## Status

Implemented and verified end-to-end against a live ACE-Step 1.5 instance.
Vocal/instrumental separation is functional but not perfect — some bleed
between stems is a known limitation of the current separation model, not
a bug in this server.
