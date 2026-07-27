# Contributing to SongForge-MCP

Thanks for your interest in contributing! Every PR — tool, bug fix, doc, or test — is welcome.

## Development setup

```bash
git clone https://github.com/xDarkzx/SongForge-MCP.git
cd SongForge-MCP
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # .venv/bin/pip on Linux/macOS
```

This installs `songforge-mcp` in editable mode along with `pytest` /
`pytest-asyncio` for tests. It does not set up ACE-Step 1.5 itself —
run `install.bat`/`install.sh` for the full environment, or see
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Running tests

```bash
pytest -v
```

All tests must pass before submitting a PR. The test suite is fully
mocked/stubbed — it does not require a GPU or a running ACE-Step
instance.

## Adding a new tool

Repo layout mirrors `Reaper-MCP`'s conventions — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture.

1. Drop a `songforge_mcp/tools/<name>_tools.py` module that defines
   `register(mcp)`. It's auto-discovered — the only other place to
   touch is adding the module name to `tool_registry.py`'s
   `_EXPECTED_MODULES` (a test enforces this stays in sync).
2. Every raised error must be a `SongForgeMCPError` with a specific
   `ErrorCode` from `songforge_mcp_shared/error_codes.py` — never a
   bare exception.
3. No composition logic belongs in this codebase — every tool takes
   fully explicit inputs (style description, lyrics, settings); Claude
   does the creative work in conversation, this server only renders.
   See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for why.

## Code style

- Python 3.10+ (type hints on public surfaces).
- No comments or docstrings on obvious code — well-named identifiers are enough.
- Keep input validation explicit; error handling should mention the specific bad value.

## Pull requests

- Keep PRs focused on a single change.
- Include tests for new tools.
- Describe what your change does and why.
- Update `CHANGELOG.md` under the current unreleased section.

## Reporting issues

Open an issue on GitHub with:

- What you expected to happen.
- What actually happened.
- Steps to reproduce.
- Your OS, Python version, and GPU (model + VRAM).
- Relevant stderr output from the MCP server.
