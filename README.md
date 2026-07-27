<h1 align="center">SongForge-MCP</h1>

<p align="center">
  <strong>Generate original AI music through Claude, powered by ACE-Step 1.5</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-purple.svg" alt="MCP Compatible" /></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-0.2.0-orange.svg" alt="v0.2.0" /></a>
  <a href="https://github.com/xDarkzx/SongForge-MCP/actions/workflows/ci.yml"><img src="https://github.com/xDarkzx/SongForge-MCP/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://github.com/ace-step/ACE-Step-1.5"><img src="https://img.shields.io/badge/GPU-12GB%2B%20VRAM-red.svg" alt="GPU 12GB+ VRAM" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="docs/TOOLS.md">Tools Reference</a> &bull;
  <a href="docs/ARCHITECTURE.md">Architecture</a> &bull;
  <a href="CHANGELOG.md">Changelog</a> &bull;
  <a href="CONTRIBUTING.md">Contributing</a> &bull;
  <a href="docs/INSTALLATION.md#troubleshooting">Troubleshooting</a>
</p>

---

**Ask Claude for a song in plain English — "an upbeat pop track about
road trips, with lyrics about freedom" — and get back a real, finished
audio file.** No music software, no AI/ML knowledge, and no account or
subscription required. Everything runs on your own computer.

## What is this, exactly?

This is an **MCP server** — a small local program that gives Claude
Desktop (Anthropic's Claude app) a new ability it doesn't have out of
the box: generating actual music. "MCP" (Model Context Protocol) is
just the standard way Claude apps plug in extra tools; you don't need
to understand it to use this, only to install it once (see below).

Under the hood, this server drives [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) —
a genuinely capable, open-source AI music generation model, entirely
credited to its original authors; this project doesn't train or own
any model, it just automates using one well. ACE-Step's own interface
exposes around seventy interdependent generation settings, and getting
a good result out of it depends on a number of non-obvious defaults and
interactions between them. SongForge-MCP removes that layer entirely:
you describe the track you want in conversation, and Claude calls this
server to produce it, handling every underlying setting correctly on
your behalf. You never touch a settings panel.

## Runs entirely on your own machine

There is no cloud service behind this, no subscription, and no account
to create. Generation happens on your own GPU, using models downloaded
once to your own disk. Your prompts, lyrics, and generated audio are
never sent to any third-party server for processing, and nothing about
your usage is logged or transmitted anywhere. The one exception is
strictly opt-in: if you point a generation at a YouTube link for
reference-audio style matching, that specific request naturally reaches
YouTube to fetch the audio — nothing else in this server makes any
outbound network call. Everything else, including every generation
itself, stays entirely local.

## Features

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

## Quick Start

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
2. The installer offers to configure Claude Desktop for you automatically
   — say yes and restart Claude Desktop. If you'd rather do it by hand
   (or use a different MCP client), see `docs/INSTALLATION.md`.
3. Ask for a track in plain language. See [`docs/TOOLS.md`](docs/TOOLS.md)
   for the full tool reference and example requests.

## Works well alongside Reaper-MCP

If your production workflow is built around REAPER, the vocal and
instrumental stems this server produces are well suited to import
directly into a REAPER project using [Reaper-MCP](https://github.com/xDarkzx/Reaper-MCP),
a companion MCP server for AI-assisted composition, mixing, and
mastering in REAPER. Both servers can be connected to the same Claude
Desktop session, allowing a track to be generated here and then placed,
arranged, and produced further without leaving the conversation.

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
