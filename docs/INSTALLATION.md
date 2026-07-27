# Installation

## System requirements

This server automates ACE-Step 1.5 — its hardware needs are what actually
matter here, not this server's own footprint (which is trivial). Numbers
below are from [ACE-Step 1.5's own published requirements](https://github.com/ace-step/ACE-Step-1.5)
(`docs/en/INSTALL.md` and `docs/en/GPU_COMPATIBILITY.md` in that repo),
not this project's own estimate.

| | Requirement |
|---|---|
| OS | Windows, Linux, or macOS |
| Python | 3.11 or 3.12 for the ACE-Step checkout specifically (this server's own venv is more permissive, but ACE-Step itself requires 3.11-3.12) |
| GPU | An NVIDIA CUDA GPU is what this project's installers target and what has actually been tested. ACE-Step 1.5 also supports AMD ROCm, Intel XPU, Apple Silicon (MPS), and CPU-only — but `install.bat`/`install.sh` don't set those up automatically; see ACE-Step's own `docs/en/INSTALL.md` if you need one of them |
| VRAM | This project is configured to use the **XL-SFT** model (higher quality than the smaller 2B model) — ACE-Step's own docs put that at **≥12GB VRAM with CPU offload + quantization, ≥20GB for it to run without offload** (their GPU_COMPATIBILITY.md tier table calls 12-16GB "marginal" for XL specifically). Below ~12GB VRAM, expect either failures or a very degraded/offloaded configuration — a smaller 2B-class model would be a better fit for that hardware, which isn't what this installer sets up |
| Disk | ~40GB free is checked by the installer before it proceeds — the XL-SFT checkpoint alone is ~28GB and downloads on first generation, on top of PyTorch/CUDA and this project's other dependencies |
| No GPU at all | Both installers detect the absence of an NVIDIA GPU and fall back to CPU builds so the install itself won't fail, but this has not been performance-tested by this project — expect generation to be dramatically slower, likely impractically so for the XL-SFT configuration these installers set up |

If your hardware doesn't meet the VRAM guidance above, running ACE-Step
1.5 directly (outside this server) with a smaller model and its own
GPU-tier auto-configuration is a better starting point than trying to
force the XL-SFT setup this installer targets.

## Installing

Two installer scripts provision everything this server needs in one pass:
this server's own environment, a full ACE-Step 1.5 checkout with the
exact dependency versions it requires, and an isolated environment for
vocal/instrumental separation.

- **Windows:** `install.bat`
- **Linux / macOS:** `install.sh` (`bash install.sh`)

Run the one matching your OS once from this folder. What follows explains
what each step does and how to recover if a step fails partway through —
both scripts are safe to re-run; completed steps are skipped or cleanly
repeated.

The two scripts differ in two places, both called out below: Python
bootstrap (Windows installs Python for you; Linux/macOS just tells you
the right command) and environment-variable persistence (Windows sets
them permanently via `setx`; Linux/macOS prints `export` lines for you to
add to your shell profile, since there's no cross-shell equivalent of
`setx`).

## What the installer does

### 1. Python

**Windows:** if `python` isn't found on your system `PATH`, the installer
downloads and silently installs Python 3.11 for the current user and adds
it to `PATH`. If this step runs, **restart your terminal and re-run
`install.bat`** so the updated `PATH` takes effect before the rest of the
install continues.

**Linux/macOS:** `install.sh` checks for `python3` (3.10+) and, if
missing, prints the right install command for your distro
(`apt-get`/`dnf`/`pacman`) or `brew` on macOS, then exits — installing
Python unattended isn't safe to automate across that many package
managers. Install it and re-run the script.

### 2. Disk space check

ACE-Step 1.5's model checkpoint is approximately 28 GB and downloads on
its first run. The installer checks for at least 40 GB free before
proceeding and stops with a clear message if there isn't enough — running
this download on a nearly-full drive has caused real problems in testing.
If it stops here, free up space (clearing package manager caches and
stale virtual-machine disk images are usually the largest wins) and
re-run the installer.

### 3. This server's own environment

Creates `.venv` in this folder and installs `songforge-mcp` along with
its dependencies (`mcp`, `playwright`, `yt-dlp`), then downloads the
Chromium browser Playwright needs.

### 4. ACE-Step 1.5

If `SONGFORGE_ACESTEP_HOME` isn't already set, the installer clones
[`ace-step/ACE-Step-1.5`](https://github.com/ace-step/ACE-Step-1.5) into
a sibling folder and sets up its own virtual environment inside that
checkout, including:

- PyTorch, pinned to a specific version matched to a known-good CUDA
  build. **This pin matters** — a newer PyTorch version breaks the
  prebuilt accelerated-attention component ACE-Step depends on, which in
  turn breaks its language-model backend in a way that's harder to
  diagnose than simply running slower. Don't "helpfully" upgrade it.
- ACE-Step's own requirements, including its language-model component.

On Linux, the installer detects an NVIDIA GPU (via `nvidia-smi`) and
installs the same pinned CUDA build as Windows. Without a detected NVIDIA
GPU (including all of macOS, which has no CUDA support), it falls back to
a plain CPU PyTorch build instead. That CPU fallback has not been
performance-tested by this project — it's the correct package per
PyTorch's own published wheel support, but expect generation to be much
slower than on a CUDA GPU.

This is the slowest part of the install — expect it to take a while on
a typical connection. The 28 GB checkpoint itself is *not* downloaded
here; it downloads automatically the first time a track is generated.

If you already have an ACE-Step 1.5 checkout you'd like to reuse, set
`SONGFORGE_ACESTEP_HOME` to point at it before running the installer
and this step is skipped.

### 5. Vocal/instrumental separator

Creates a separate, isolated environment (`.separator_env`) for
`audio-separator`, the tool used by `split_vocal_stems`. This is kept
independent from ACE-Step's own environment deliberately — the two have
unrelated dependency requirements, and past experience in this project
showed that combining environments with different needs silently breaks
one or the other.

### 6. Environment variables

The installer needs three environment variables set so this server can
find everything it just installed:

| Variable | Points to |
|---|---|
| `SONGFORGE_ACESTEP_HOME` | The ACE-Step 1.5 checkout |
| `SONGFORGE_SEPARATOR_PYTHON` | The separator environment's Python interpreter |
| `SONGFORGE_YTDLP_PYTHON` | This server's own Python interpreter (yt-dlp is installed alongside it) |

A fourth, optional one controls where generated tracks/stems are saved:

| Variable | Points to |
|---|---|
| `SONGFORGE_OUTPUT_DIR` *(optional)* | Where generated tracks and stems are saved. Defaults to an `output/` folder inside this repo checkout if unset — not the OS temp directory, since temp can be purged by system cleanup tools and isn't somewhere you'd think to look for a track you asked for and want to keep. Set this if you'd rather output land somewhere else (e.g. a personal music archive folder). |

**Windows:** `install.bat` sets these as permanent user environment
variables via `setx` automatically.

**Linux/macOS:** `install.sh` prints the three `export` lines at the end
of the run — add them to your shell profile (`~/.bashrc`, `~/.zshrc`, or
equivalent) yourself. The script doesn't edit that file for you.

**Restart your terminal (and Claude Desktop, if it's running) after
installation** so these take effect.

## Configuring Claude Desktop

Add this server to Claude Desktop's MCP configuration, pointing at the
executable created inside this project's own `.venv`:

```json
{
  "mcpServers": {
    "songforge-mcp": {
      "command": "C:\\path\\to\\SongForge-MCP\\.venv\\Scripts\\songforge-mcp.exe"
    }
  }
}
```

On Linux/macOS, point at the `.venv/bin/songforge-mcp` script instead:

```json
{
  "mcpServers": {
    "songforge-mcp": {
      "command": "/path/to/SongForge-MCP/.venv/bin/songforge-mcp"
    }
  }
}
```

Restart Claude Desktop after saving. See [`docs/TOOLS.md`](TOOLS.md) for
how to use it once connected.

## First run

The first time you ask for a track, expect a longer wait than usual —
ACE-Step's ~28 GB checkpoint downloads and its model loads into memory on
first use. Subsequent generations are much faster since the model server
stays running in the background between requests.

## Troubleshooting

- **"ACESTEP_NOT_CONFIGURED" or "SEPARATOR_NOT_CONFIGURED" errors** — the
  relevant environment variable isn't set or doesn't point to a valid
  install. Re-run `install.bat`, or check the table above and set the
  variable manually, then restart Claude Desktop.
- **A generation silently never completes** — check
  `<ACE-Step folder>/mcp_server_stderr.txt` for what ACE-Step's own
  process is doing; this is the same log a human would check if running
  it manually.
- **GPU/CUDA errors on generation** — confirm your GPU driver actually
  supports the pinned PyTorch/CUDA combination from step 4. This is a
  hardware-compatibility question outside this server's control.
