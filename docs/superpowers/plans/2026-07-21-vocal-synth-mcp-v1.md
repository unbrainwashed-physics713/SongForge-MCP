# Vocal-Synth-MCP v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, testable v1 of Vocal-Synth-MCP: an MCP server that renders a vocal-only WAV stem from an explicit melody + lyrics via a subprocess-driven openvpi/DiffSinger pipeline, with a rich diagnostics/typed-error tool contract, following `Reaper-MCP`/`AudacityMCP`'s repo conventions.

**Architecture:** `synthesize_vocal`/`list_voicebanks`/`validate_score` MCP tools call into a small set of pure, independently-testable modules (`protocol.py` builds/validates DiffSinger's `.ds` request format and parses its output; `diffsinger_client.py` subprocesses into a separately-cloned DiffSinger checkout's two-stage `variance`→`acoustic` CLI). All composition/melody/lyric decisions happen outside this codebase, in the calling LLM's conversation — this server only renders what it's explicitly told to sing.

**Tech Stack:** Python ≥3.10, `mcp[cli]` (FastMCP), `g2p_en` (lyric→phoneme conversion), `pytest`/`pytest-asyncio`. External (not a dependency of this repo): a separately-cloned `openvpi/DiffSinger` checkout with its own PyTorch ≥2.4.0 environment.

## Global Constraints

- Python ≥3.10 (per existing `pyproject.toml`).
- `mcp[cli]>=1.0.0` is the only required runtime dependency besides `g2p_en`; DiffSinger itself is never a Python dependency — it's a separately-cloned checkout invoked via subprocess (see design doc's "Technology" section).
- Output is **vocal-only** — no backing instrumentation is ever generated or mixed in by this server.
- No melody/lyric composition logic anywhere in this codebase — every tool takes fully explicit notes+lyrics. No auto-retry or auto-parameter-adjustment inside the server either — diagnostics are reported, retries are the calling LLM's decision.
- All raised errors are `VocalSynthMCPError` carrying a specific `ErrorCode`, mirroring `Reaper-MCP`'s `ReaperMCPError`/`ErrorCode` pattern — never a bare `Exception` or generic message.
- Repo layout mirrors `Reaper-MCP`/`AudacityMCP`: `vocal_synth_mcp/` (tools, auto-registered), `vocal_synth_mcp_shared/` (constants, error codes, protocol), `docs/`, `tests/`, `install.bat`/`install.sh`.
- Source of truth for all of the above: `docs/2026-07-21-design.md` in this repo.

---

### Task 1: Shared error codes

**Files:**
- Create: `vocal_synth_mcp_shared/__init__.py` (empty)
- Create: `vocal_synth_mcp_shared/error_codes.py`
- Test: `tests/test_error_codes.py`

**Interfaces:**
- Produces: `ErrorCode` (IntEnum) with members `SUBPROCESS_FAILED=1000`, `SUBPROCESS_TIMEOUT=1001`, `DIFFSINGER_NOT_CONFIGURED=1002`, `SYNTHESIS_FAILED=2000`, `VARIANCE_STAGE_FAILED=2001`, `ACOUSTIC_STAGE_FAILED=2002`, `VALIDATION_FAILED=3000`, `INVALID_PARAMETER=3001`, `MISSING_PARAMETER=3002`, `NOTE_OUT_OF_RANGE=3003`, `PHONEME_NOT_FOUND=3004`, `LYRIC_NOTE_COUNT_MISMATCH=3005`, `VOICEBANK_NOT_FOUND=3006`, `VALUE_OUT_OF_RANGE=3007`. `VocalSynthMCPError(code: ErrorCode, message: str)` — every later task raises this, never a bare `Exception`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_codes.py
import pytest

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def test_error_carries_code_and_message():
    err = VocalSynthMCPError(ErrorCode.NOTE_OUT_OF_RANGE, "pitch 200 is not a valid MIDI note")
    assert err.code == ErrorCode.NOTE_OUT_OF_RANGE
    assert err.message == "pitch 200 is not a valid MIDI note"


def test_error_string_includes_code_name_and_value():
    err = VocalSynthMCPError(ErrorCode.VOICEBANK_NOT_FOUND, "unknown voicebank 'nope'")
    assert str(err) == "[VOICEBANK_NOT_FOUND (3006)] unknown voicebank 'nope'"


def test_error_codes_are_unique():
    values = [code.value for code in ErrorCode]
    assert len(values) == len(set(values))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_codes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp_shared'`

- [ ] **Step 3: Write the implementation**

Create `vocal_synth_mcp_shared/__init__.py` (empty file).

```python
# vocal_synth_mcp_shared/error_codes.py
from enum import IntEnum


class ErrorCode(IntEnum):
    # Process errors (1000s)
    SUBPROCESS_FAILED = 1000
    SUBPROCESS_TIMEOUT = 1001
    DIFFSINGER_NOT_CONFIGURED = 1002

    # Synthesis errors (2000s)
    SYNTHESIS_FAILED = 2000
    VARIANCE_STAGE_FAILED = 2001
    ACOUSTIC_STAGE_FAILED = 2002

    # Validation errors (3000s)
    VALIDATION_FAILED = 3000
    INVALID_PARAMETER = 3001
    MISSING_PARAMETER = 3002
    NOTE_OUT_OF_RANGE = 3003
    PHONEME_NOT_FOUND = 3004
    LYRIC_NOTE_COUNT_MISMATCH = 3005
    VOICEBANK_NOT_FOUND = 3006
    VALUE_OUT_OF_RANGE = 3007


class VocalSynthMCPError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code.name} ({code.value})] {message}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_error_codes.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp_shared/__init__.py vocal_synth_mcp_shared/error_codes.py tests/test_error_codes.py
git commit -m "feat: add typed VocalSynthMCPError/ErrorCode"
```

---

### Task 2: Shared constants & safety limits

**Files:**
- Create: `vocal_synth_mcp_shared/constants.py`
- Test: `tests/test_constants.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Paths.DIFFSINGER_HOME: str` (from `VOCAL_SYNTH_DIFFSINGER_HOME` env var), `Paths.OUTPUT_DIR: str`, `Timeouts.VARIANCE_STAGE: float`, `Timeouts.ACOUSTIC_STAGE: float`, `MIN_MIDI_NOTE: int`, `MAX_MIDI_NOTE: int`, `MAX_NOTES_PER_CALL: int`, `MAX_LYRIC_LENGTH: int`, `ensure_private_dir(path: str) -> None`. Used by Tasks 3, 4, 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_constants.py
import tempfile

from vocal_synth_mcp_shared import constants


def test_midi_range_is_valid_and_ordered():
    assert 0 <= constants.MIN_MIDI_NOTE < constants.MAX_MIDI_NOTE <= 127


def test_timeouts_are_positive():
    assert constants.Timeouts.VARIANCE_STAGE > 0
    assert constants.Timeouts.ACOUSTIC_STAGE > 0


def test_output_dir_is_under_system_temp():
    assert constants.Paths.OUTPUT_DIR.startswith(tempfile.gettempdir())


def test_ensure_private_dir_creates_directory(tmp_path):
    target = tmp_path / "nested" / "dir"
    constants.ensure_private_dir(str(target))
    assert target.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_constants.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp_shared.constants'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp_shared/constants.py
"""Shared constants: DiffSinger checkout paths, timeouts, and safety limits."""
import os
import tempfile


def ensure_private_dir(path: str) -> None:
    """Create a directory if missing, and best-effort restrict it to the
    owning user only (0700). Mirrors reaper_mcp_shared.constants."""
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


class Paths:
    # Root of a separately-cloned openvpi/DiffSinger checkout. Must be set
    # by the user at install time (see docs/INSTALLATION.md) — DiffSinger
    # is not pip-installable, so this server subprocesses into that clone
    # rather than importing it.
    DIFFSINGER_HOME = os.environ.get("VOCAL_SYNTH_DIFFSINGER_HOME", "")
    OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "vocal_synth_mcp", "renders")


class Timeouts:
    VARIANCE_STAGE = 120.0   # predicts duration/pitch/energy/breathiness/tension
    ACOUSTIC_STAGE = 300.0   # renders audio via the acoustic model + vocoder


# MIDI note range this server accepts without a voicebank-specific override
# (see vocal_synth_mcp_shared/voicebanks.py for per-voicebank ranges, which
# are typically narrower). C2-C6 covers the great majority of pop/EDM lead
# vocal writing.
MIN_MIDI_NOTE = 36  # C2
MAX_MIDI_NOTE = 84  # C6

MAX_NOTES_PER_CALL = 500   # keeps a single .ds file/render to roughly one song section
MAX_LYRIC_LENGTH = 2000    # characters, sanity ceiling on any one lyric string
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_constants.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp_shared/constants.py tests/test_constants.py
git commit -m "feat: add shared paths/timeouts/safety-limit constants"
```

---

### Task 3: `.ds` protocol module — build, validate, parse

**Files:**
- Create: `vocal_synth_mcp_shared/protocol.py`
- Test: `tests/test_protocol.py`
- Modify: `pyproject.toml` — add `g2p_en>=2.1.0` to `dependencies`

**Interfaces:**
- Consumes: `MIN_MIDI_NOTE`, `MAX_MIDI_NOTE`, `MAX_NOTES_PER_CALL` from Task 2; `ErrorCode`, `VocalSynthMCPError` from Task 1.
- Produces: `NoteEvent(pitch: int, duration_beats: float, lyric: str | None)` dataclass; `midi_to_note_name(pitch: int) -> str`; `validate_notes(notes: list[NoteEvent]) -> None` (raises on problems); `build_ds_file(notes: list[NoteEvent], bpm: float, expressive_params: dict | None = None) -> dict`; `parse_stage_output(stdout: str, stderr: str, stage: str) -> list[str]`; `measure_wav_duration_seconds(wav_path: str) -> float`. Used by Tasks 4, 7, 9.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_protocol.py
import wave

import pytest

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import (
    NoteEvent,
    build_ds_file,
    measure_wav_duration_seconds,
    midi_to_note_name,
    parse_stage_output,
    validate_notes,
)


def test_midi_to_note_name_middle_c():
    assert midi_to_note_name(60) == "C4"


def test_midi_to_note_name_sharp():
    assert midi_to_note_name(61) == "C#4"


def test_validate_notes_rejects_empty_list():
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes([])
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_notes_rejects_all_rests():
    notes = [NoteEvent(pitch=-1, duration_beats=1.0, lyric=None)]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.MISSING_PARAMETER


def test_validate_notes_rejects_out_of_range_pitch():
    notes = [NoteEvent(pitch=200, duration_beats=1.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_validate_notes_rejects_zero_duration():
    notes = [NoteEvent(pitch=60, duration_beats=0.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        validate_notes(notes)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_validate_notes_accepts_a_valid_sequence():
    notes = [
        NoteEvent(pitch=60, duration_beats=1.0, lyric="hel"),
        NoteEvent(pitch=-1, duration_beats=0.5, lyric=None),
        NoteEvent(pitch=62, duration_beats=1.0, lyric="lo"),
    ]
    validate_notes(notes)  # must not raise


def test_build_ds_file_produces_matching_length_sequences():
    notes = [
        NoteEvent(pitch=60, duration_beats=1.0, lyric="hi"),
        NoteEvent(pitch=-1, duration_beats=1.0, lyric=None),
    ]
    ds = build_ds_file(notes, bpm=120.0)
    note_seq = ds["note_seq"].split()
    note_dur = ds["note_dur"].split()
    assert note_seq == ["C4", "rest"]
    assert len(note_dur) == 2
    # 1 beat at 120bpm = 0.5s
    assert float(note_dur[0]) == pytest.approx(0.5)


def test_build_ds_file_rejects_non_positive_bpm():
    notes = [NoteEvent(pitch=60, duration_beats=1.0, lyric="hi")]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        build_ds_file(notes, bpm=0.0)
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_build_ds_file_includes_optional_expressive_params():
    notes = [NoteEvent(pitch=60, duration_beats=1.0, lyric="hi")]
    ds = build_ds_file(notes, bpm=120.0, expressive_params={"f0_seq": "220 220"})
    assert ds["f0_seq"] == "220 220"


def test_parse_stage_output_extracts_warning_lines():
    stderr = "loading checkpoint...\nWarning: OOV phoneme for 'xyz'\ndone\n"
    warnings = parse_stage_output(stdout="", stderr=stderr, stage="variance")
    assert warnings == ["[variance] Warning: OOV phoneme for 'xyz'"]


def test_parse_stage_output_returns_empty_list_when_no_warnings():
    assert parse_stage_output(stdout="ok", stderr="done\n", stage="acoustic") == []


def test_measure_wav_duration_seconds(tmp_path):
    path = str(tmp_path / "test.wav")
    framerate = 44100
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * framerate)  # exactly 1 second
    assert measure_wav_duration_seconds(path) == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp_shared.protocol'`

- [ ] **Step 3: Add the dependency**

In `pyproject.toml`, change:
```toml
dependencies = [
    "mcp[cli]>=1.0.0",
]
```
to:
```toml
dependencies = [
    "mcp[cli]>=1.0.0",
    "g2p_en>=2.1.0",
]
```

- [ ] **Step 4: Write the implementation**

```python
# vocal_synth_mcp_shared/protocol.py
"""Wire format helpers for DiffSinger's .ds input files and output parsing."""
import wave
from dataclasses import dataclass

from vocal_synth_mcp_shared.constants import MAX_MIDI_NOTE, MAX_NOTES_PER_CALL, MIN_MIDI_NOTE
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError

_MIDI_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class NoteEvent:
    pitch: int          # MIDI note number, or -1 for a rest
    duration_beats: float
    lyric: str | None   # None for a rest


def midi_to_note_name(pitch: int) -> str:
    """60 -> 'C4', matching DiffSinger's note_seq note-name convention."""
    octave = pitch // 12 - 1
    return f"{_MIDI_NAMES[pitch % 12]}{octave}"


def _beats_to_seconds(beats: float, bpm: float) -> float:
    return beats * 60.0 / bpm


def validate_notes(notes: list[NoteEvent]) -> None:
    if not notes:
        raise VocalSynthMCPError(ErrorCode.MISSING_PARAMETER, "notes must contain at least one note")
    if len(notes) > MAX_NOTES_PER_CALL:
        raise VocalSynthMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"{len(notes)} notes exceeds the {MAX_NOTES_PER_CALL}-note limit per call",
        )
    if not any(n.lyric for n in notes):
        raise VocalSynthMCPError(ErrorCode.MISSING_PARAMETER, "notes must include at least one sung (non-rest) note")
    for i, note in enumerate(notes):
        if note.pitch != -1 and not (MIN_MIDI_NOTE <= note.pitch <= MAX_MIDI_NOTE):
            raise VocalSynthMCPError(
                ErrorCode.NOTE_OUT_OF_RANGE,
                f"note {i}: pitch {note.pitch} is outside the supported range "
                f"{MIN_MIDI_NOTE}-{MAX_MIDI_NOTE}",
            )
        if note.duration_beats <= 0:
            raise VocalSynthMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"note {i}: duration_beats must be > 0, got {note.duration_beats}",
            )


def build_ds_file(
    notes: list[NoteEvent], bpm: float, expressive_params: dict | None = None
) -> dict:
    """Build a DiffSinger .ds request from an explicit note+lyric sequence.

    `notes` must already carry one lyric per sung syllable — this server
    does not do text-to-syllable splitting; the calling LLM hands one
    NoteEvent per syllable (rests use lyric=None). Word/syllable -> ARPAbet
    phoneme conversion happens here via g2p_en. "SP" (silence) is used as
    the rest phoneme, matching common DiffSinger English-dictionary
    convention — confirm this against the actual chosen voicebank's
    phoneme dictionary during setup (see docs/INSTALLATION.md).
    """
    validate_notes(notes)
    if bpm <= 0:
        raise VocalSynthMCPError(ErrorCode.INVALID_PARAMETER, f"bpm must be > 0, got {bpm}")

    from g2p_en import G2p

    g2p = G2p()

    note_seq: list[str] = []
    note_dur: list[str] = []
    ph_seq: list[str] = []
    ph_num: list[str] = []

    for note in notes:
        note_seq.append("rest" if note.pitch == -1 else midi_to_note_name(note.pitch))
        note_dur.append(str(round(_beats_to_seconds(note.duration_beats, bpm), 6)))
        if note.lyric:
            phonemes = [p for p in g2p(note.lyric) if p.strip()]
            if not phonemes:
                raise VocalSynthMCPError(
                    ErrorCode.PHONEME_NOT_FOUND,
                    f"could not derive phonemes for lyric {note.lyric!r}",
                )
            ph_seq.extend(phonemes)
            ph_num.append(str(len(phonemes)))
        else:
            ph_seq.append("SP")
            ph_num.append("1")

    ds_entry: dict = {
        "text": "",
        "ph_seq": " ".join(ph_seq),
        "ph_num": " ".join(ph_num),
        "note_seq": " ".join(note_seq),
        "note_dur": " ".join(note_dur),
        "input_type": "phoneme",
    }
    if expressive_params:
        for key in ("f0_seq", "energy", "breathiness", "voicing", "tension"):
            if key in expressive_params:
                ds_entry[key] = expressive_params[key]
    return ds_entry


def parse_stage_output(stdout: str, stderr: str, stage: str) -> list[str]:
    """Extract warning lines from a DiffSinger CLI stage's output.

    DiffSinger's inference scripts print progress/warnings to stderr; lines
    mentioning "warning" or "oov" (out-of-vocabulary phoneme) are surfaced
    as diagnostics rather than silently dropped.
    """
    warnings = []
    for line in stderr.splitlines():
        if "warning" in line.lower() or "oov" in line.lower():
            warnings.append(f"[{stage}] {line.strip()}")
    return warnings


def measure_wav_duration_seconds(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()
```

- [ ] **Step 5: Install the new dependency and run tests to verify they pass**

Run: `pip install -e .` then `pytest tests/test_protocol.py -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add vocal_synth_mcp_shared/protocol.py tests/test_protocol.py pyproject.toml
git commit -m "feat: add .ds build/validate/parse protocol helpers"
```

---

### Task 4: DiffSinger subprocess client

**Files:**
- Create: `vocal_synth_mcp/__init__.py` (empty)
- Create: `vocal_synth_mcp/diffsinger_client.py`
- Test: `tests/test_diffsinger_client.py`

**Interfaces:**
- Consumes: `Paths`, `Timeouts`, `ensure_private_dir` from Task 2; `ErrorCode`, `VocalSynthMCPError` from Task 1; `parse_stage_output` from Task 3.
- Produces: `DiffSingerClient(diffsinger_home: str | None = None)` with `.synthesize(ds_entry: dict, experiment: str) -> {"wav_path": str, "warnings": list[str]}`. Used by Task 9.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_diffsinger_client.py
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vocal_synth_mcp.diffsinger_client import DiffSingerClient
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def _make_checkout(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "infer.py").write_text("")
    return tmp_path


def test_synthesize_raises_when_not_configured():
    client = DiffSingerClient(diffsinger_home="")
    with pytest.raises(VocalSynthMCPError) as exc_info:
        client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
    assert exc_info.value.code == ErrorCode.DIFFSINGER_NOT_CONFIGURED


def test_synthesize_raises_on_stage_timeout(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="infer.py", timeout=1.0)
        with pytest.raises(VocalSynthMCPError) as exc_info:
            client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
        assert exc_info.value.code == ErrorCode.SUBPROCESS_TIMEOUT


def test_synthesize_raises_on_nonzero_exit(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="RuntimeError: bad checkpoint")
        with pytest.raises(VocalSynthMCPError) as exc_info:
            client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
        assert exc_info.value.code == ErrorCode.VARIANCE_STAGE_FAILED


def test_synthesize_returns_wav_path_and_warnings_on_success(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        render_id = None
        for part in cmd:
            if str(part).endswith(".ds"):
                render_id = os.path.splitext(os.path.basename(part))[0]
        out_dir = checkout / "infer_out"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{render_id}.wav").write_bytes(b"RIFF....")
        stage = cmd[2]
        stderr = "Warning: OOV phoneme for 'xyz'\n" if stage == "variance" else ""
        return MagicMock(returncode=0, stdout="", stderr=stderr)

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run", side_effect=fake_run):
        result = client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")

    assert result["wav_path"].endswith(".wav")
    assert os.path.isfile(result["wav_path"])
    assert any("OOV" in w for w in result["warnings"])


def test_synthesize_raises_when_acoustic_stage_produces_no_wav(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with pytest.raises(VocalSynthMCPError) as exc_info:
            client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
        assert exc_info.value.code == ErrorCode.SYNTHESIS_FAILED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_diffsinger_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/diffsinger_client.py
"""Subprocess wrapper around a cloned openvpi/DiffSinger checkout.

DiffSinger is not pip-installable — inference happens by invoking its own
scripts/infer.py inside a separately-cloned checkout (see
docs/INSTALLATION.md for how that checkout gets set up). This module owns
the two-stage subprocess invocation (variance -> acoustic) and turns
process failures into typed VocalSynthMCPErrors. The exact output-file
naming convention below (infer_out/{render_id}.wav) needs confirming
against real DiffSinger CLI behavior during Task 14's manual verification
— fix in one place here if it differs.
"""
import json
import os
import subprocess
import tempfile
import uuid

from vocal_synth_mcp_shared.constants import Paths, Timeouts, ensure_private_dir
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import parse_stage_output


class DiffSingerClient:
    def __init__(self, diffsinger_home: str | None = None):
        self.diffsinger_home = diffsinger_home if diffsinger_home is not None else Paths.DIFFSINGER_HOME
        ensure_private_dir(Paths.OUTPUT_DIR)

    def _require_configured(self) -> None:
        if not self.diffsinger_home or not os.path.isdir(self.diffsinger_home):
            raise VocalSynthMCPError(
                ErrorCode.DIFFSINGER_NOT_CONFIGURED,
                "VOCAL_SYNTH_DIFFSINGER_HOME is not set or does not point to a "
                "valid directory. See docs/INSTALLATION.md.",
            )

    def _run_stage(self, stage: str, ds_path: str, experiment: str, timeout: float) -> tuple[str, str]:
        script = os.path.join(self.diffsinger_home, "scripts", "infer.py")
        cmd = ["python", script, stage, ds_path, "--exp", experiment]
        try:
            result = subprocess.run(
                cmd, cwd=self.diffsinger_home, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise VocalSynthMCPError(
                ErrorCode.SUBPROCESS_TIMEOUT,
                f"DiffSinger {stage} stage exceeded {timeout}s timeout",
            ) from e
        except OSError as e:
            raise VocalSynthMCPError(
                ErrorCode.SUBPROCESS_FAILED,
                f"failed to launch DiffSinger {stage} stage: {e}",
            ) from e

        if result.returncode != 0:
            code = ErrorCode.VARIANCE_STAGE_FAILED if stage == "variance" else ErrorCode.ACOUSTIC_STAGE_FAILED
            raise VocalSynthMCPError(
                code,
                f"DiffSinger {stage} stage exited {result.returncode}: "
                f"{result.stderr.strip()[-2000:]}",
            )
        return result.stdout, result.stderr

    def synthesize(self, ds_entry: dict, experiment: str) -> dict:
        """Run the variance -> acoustic pipeline for one .ds entry.

        Returns {"wav_path": str, "warnings": list[str]}.
        """
        self._require_configured()
        render_id = uuid.uuid4().hex
        ds_dir = os.path.join(tempfile.gettempdir(), "vocal_synth_mcp")
        os.makedirs(ds_dir, exist_ok=True)
        ds_path = os.path.join(ds_dir, f"{render_id}.ds")
        with open(ds_path, "w", encoding="utf-8") as f:
            json.dump([ds_entry], f)

        warnings: list[str] = []
        stdout, stderr = self._run_stage("variance", ds_path, experiment, Timeouts.VARIANCE_STAGE)
        warnings += parse_stage_output(stdout, stderr, "variance")
        stdout, stderr = self._run_stage("acoustic", ds_path, experiment, Timeouts.ACOUSTIC_STAGE)
        warnings += parse_stage_output(stdout, stderr, "acoustic")

        wav_path = os.path.join(self.diffsinger_home, "infer_out", f"{render_id}.wav")
        if not os.path.isfile(wav_path):
            raise VocalSynthMCPError(
                ErrorCode.SYNTHESIS_FAILED,
                f"acoustic stage reported success but no output wav found at {wav_path}",
            )
        return {"wav_path": wav_path, "warnings": warnings}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_diffsinger_client.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/__init__.py vocal_synth_mcp/diffsinger_client.py tests/test_diffsinger_client.py
git commit -m "feat: add DiffSinger two-stage subprocess client"
```

---

### Task 5: Voicebank registry

**Files:**
- Create: `vocal_synth_mcp_shared/voicebanks.py`
- Test: `tests/test_voicebanks.py`

**Interfaces:**
- Consumes: nothing beyond stdlib.
- Produces: `VoicebankInfo(name, experiment, language, min_midi_note, max_midi_note, license_summary)` frozen dataclass; `VOICEBANK_REGISTRY: dict[str, VoicebankInfo]`. Used by Tasks 8, 9.

**Context for this task:** research this session confirmed the LUNAI Project's actual terms (from `github.com/lunaiproject/lunai_singers`'s terms-of-use file, checked 2026-07-21): non-commercial use is permitted with attribution ("`<Character>` from LUNAI Project"); commercial use requires written per-character permission from the LUNAI team first. User decision: proceed with a LUNAI character as the v1 default now to evaluate quality; swap it for a different voicebank later if the quality doesn't hold up. Per-character language/vocal-character metadata wasn't resolved by documentation research — that requires actually listening once it's installed (Task 14), so `language` below is honestly marked `"unconfirmed"` rather than guessed.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_voicebanks.py
from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY


def test_registry_is_not_empty():
    assert len(VOICEBANK_REGISTRY) >= 1


def test_every_entry_has_a_valid_ordered_midi_range():
    for vb_id, vb in VOICEBANK_REGISTRY.items():
        assert 0 <= vb.min_midi_note < vb.max_midi_note <= 127, vb_id


def test_every_entry_has_a_nonempty_license_summary():
    for vb_id, vb in VOICEBANK_REGISTRY.items():
        assert vb.license_summary.strip(), vb_id


def test_every_entry_has_a_nonempty_experiment_name():
    for vb_id, vb in VOICEBANK_REGISTRY.items():
        assert vb.experiment.strip(), vb_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_voicebanks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp_shared.voicebanks'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp_shared/voicebanks.py
"""Registry of configured DiffSinger voicebanks.

Each entry's `experiment` value must match the folder name under
DIFFSINGER_HOME/checkpoints/ once the voicebank is installed — see
docs/INSTALLATION.md for the exact setup steps.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VoicebankInfo:
    name: str
    experiment: str
    language: str
    min_midi_note: int
    max_midi_note: int
    license_summary: str


# v1 default: a LUNAI Project character. LUNAI's terms (verified 2026-07-21
# against github.com/lunaiproject/lunai_singers's terms-of-use file) permit
# non-commercial use with attribution ("<Character> from LUNAI Project");
# commercial use needs written per-character permission from the LUNAI team
# first (email request, ~7 business day turnaround per their terms). Their
# terms also prohibit porting/modifying models for other engines — this
# server invokes the same underlying DiffSinger checkpoint directly via
# subprocess rather than through OpenUtau's GUI; user's explicit call was
# to proceed and evaluate quality now, revisit if this specific point
# becomes a blocker before any commercial release.
#
# Character picked arbitrarily from LUNAI's roster — per-character
# language/vocal-character metadata wasn't available from documentation
# alone. Confirm this is actually a fit (language, tone, range) by ear
# during Task 14's manual verification, and swap this entry (or add more)
# for a different LUNAI character or a different voicebank entirely if it
# isn't a fit ("if the voicebank sucks we scrap it, find another").
VOICEBANK_REGISTRY: dict[str, VoicebankInfo] = {
    "lunai-katyusha": VoicebankInfo(
        name="Katyusha (LUNAI Project)",
        experiment="lunai_katyusha",
        language="unconfirmed",
        min_midi_note=48,   # C3 — conservative default until confirmed by ear
        max_midi_note=72,   # C5 — conservative default until confirmed by ear
        license_summary=(
            "Non-commercial use permitted with attribution "
            "('Katyusha from LUNAI Project'). Commercial use requires "
            "written per-character permission from the LUNAI team first."
        ),
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_voicebanks.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp_shared/voicebanks.py tests/test_voicebanks.py
git commit -m "feat: add voicebank registry with LUNAI Katyusha v1 default"
```

---

### Task 6: Instructions loader + core instructions doc

**Files:**
- Create: `vocal_synth_mcp/instructions/__init__.py`
- Create: `vocal_synth_mcp/instructions/00_core.md`
- Test: `tests/test_instructions.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_instructions() -> str`. Used by Task 11.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_instructions.py
from vocal_synth_mcp.instructions import load_instructions


def test_load_instructions_returns_nonempty_text():
    text = load_instructions()
    assert len(text) > 0


def test_load_instructions_documents_the_note_format():
    text = load_instructions()
    assert "duration_beats" in text
    assert "validate_score" in text
    assert "list_voicebanks" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instructions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.instructions'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/instructions/__init__.py
from pathlib import Path


def load_instructions() -> str:
    """Load the core instruction file."""
    filepath = Path(__file__).parent / "00_core.md"
    return filepath.read_text(encoding="utf-8")
```

```markdown
<!-- vocal_synth_mcp/instructions/00_core.md -->
# Vocal-Synth-MCP

Renders a **vocal-only** WAV stem from an explicit melody + lyrics. This
server never composes anything — no melody, no lyrics, no backing
instrumentation. All of that reasoning is yours, done in conversation with
the user before calling any tool here.

## Workflow

1. If a REAPER project is open (via a connected reaper-mcp server), read
   its key/BPM/structure first — don't guess parameters you can look up.
2. Work out lyrics and an explicit vocal melody (pitch + rhythm per
   syllable) matching the requested mood/style/section. Reason about the
   note sequence first, then separately about expressive delivery
   (dynamics, phrasing) — don't conflate the two in one step.
3. Propose the lyrics back to the user for confirmation before rendering.
4. Call `validate_score` first — it's a fast, free pre-check that catches
   out-of-range notes and structural problems before a full render.
5. Call `list_voicebanks` to pick a `voicebank` id and confirm your notes
   fit its MIDI range.
6. Call `synthesize_vocal` with the confirmed, explicit result.
7. Read the returned `diagnostics` — warnings, requested vs. actual
   duration. If something looks wrong, decide whether to adjust notes and
   retry, or ask the user. This server will not retry or adjust anything
   on its own.

## Note format

Every tool that takes notes expects a list of:

```json
{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}
```

- `pitch`: MIDI note number (36-84 by default; a chosen voicebank may be
  narrower — check `list_voicebanks`). Use `-1` for a rest.
- `duration_beats`: note length in beats, relative to the call's `bpm`.
- `lyric`: one syllable per sung note. `null`/omitted for rests.

One `NoteEvent` per syllable — this server does not split words into
syllables for you.

## Simple vs. granular control

`synthesize_vocal`'s `expressive_params` argument is optional. Omit it for
normal use — DiffSinger's own variance model predicts pitch/energy/
breathiness automatically. Supply it only when you want precise control,
e.g. reacting to a previous take's diagnostics with an explicit pitch
curve.

## Output

Vocal-only WAV stem. No bass, synths, or other backing elements are ever
part of the output — if you want a full arrangement, that's composed
separately (e.g. via reaper-mcp) and this stem is dropped in alongside it.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_instructions.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/instructions/
git commit -m "feat: add injected instructions doc for the calling LLM"
```

---

### Task 7: `validate_score` tool

**Files:**
- Create: `vocal_synth_mcp/tools/__init__.py` (empty)
- Create: `vocal_synth_mcp/tools/validate_tools.py`
- Test: `tests/test_validate_tools.py`

**Interfaces:**
- Consumes: `NoteEvent`, `validate_notes` from Task 3; `ErrorCode`, `VocalSynthMCPError` from Task 1.
- Produces: MCP tool `validate_score(notes: list[dict], bpm: float) -> dict` registered via `register(mcp: FastMCP)`. Used by Task 10.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validate_tools.py
import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import validate_tools
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def _register() -> FastMCP:
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    return mcp


def test_validate_score_accepts_a_valid_sequence():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [
        {"pitch": 60, "duration_beats": 1.0, "lyric": "hel"},
        {"pitch": 62, "duration_beats": 1.0, "lyric": "lo"},
    ]
    result = asyncio.run(tool.fn(notes=notes, bpm=120.0))
    assert result["valid"] is True
    assert result["note_count"] == 2
    assert result["sung_note_count"] == 2
    assert result["total_duration_seconds"] == pytest.approx(1.0)


def test_validate_score_rejects_out_of_range_pitch():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [{"pitch": 200, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0))
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_validate_score_rejects_non_positive_bpm():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("validate_score")
    notes = [{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=0.0))
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validate_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.tools'`

- [ ] **Step 3: Write the implementation**

Create `vocal_synth_mcp/tools/__init__.py` (empty file).

```python
# vocal_synth_mcp/tools/validate_tools.py
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import NoteEvent, validate_notes


def register(mcp: FastMCP):
    @mcp.tool()
    async def validate_score(notes: list[dict], bpm: float) -> dict:
        """Check a note+lyric sequence for problems before full synthesis.

        Fast pre-check — does not invoke DiffSinger. Catches out-of-range
        notes, missing lyrics, and structural problems so the calling LLM
        can fix them before spending time on a full two-stage render.

        Args:
            notes: List of {"pitch": int (MIDI note, -1 for rest),
                "duration_beats": float, "lyric": str or null}.
            bpm: Tempo in beats per minute.
        """
        if bpm <= 0:
            raise VocalSynthMCPError(ErrorCode.INVALID_PARAMETER, f"bpm must be > 0, got {bpm}")
        note_events = [
            NoteEvent(pitch=n["pitch"], duration_beats=n["duration_beats"], lyric=n.get("lyric"))
            for n in notes
        ]
        validate_notes(note_events)
        total_beats = sum(n.duration_beats for n in note_events)
        return {
            "valid": True,
            "note_count": len(note_events),
            "sung_note_count": sum(1 for n in note_events if n.lyric),
            "total_duration_seconds": round(total_beats * 60.0 / bpm, 3),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validate_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/tools/__init__.py vocal_synth_mcp/tools/validate_tools.py tests/test_validate_tools.py
git commit -m "feat: add validate_score MCP tool"
```

---

### Task 8: `list_voicebanks` tool

**Files:**
- Create: `vocal_synth_mcp/tools/voicebank_tools.py`
- Test: `tests/test_voicebank_tools.py`

**Interfaces:**
- Consumes: `VOICEBANK_REGISTRY` from Task 5.
- Produces: MCP tool `list_voicebanks() -> dict` registered via `register(mcp: FastMCP)`. Used by Task 10.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_voicebank_tools.py
import asyncio

from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import voicebank_tools
from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY


def test_list_voicebanks_returns_every_registered_voicebank():
    mcp = FastMCP("test")
    voicebank_tools.register(mcp)
    tool = mcp._tool_manager.get_tool("list_voicebanks")
    result = asyncio.run(tool.fn())
    ids = {vb["id"] for vb in result["voicebanks"]}
    assert ids == set(VOICEBANK_REGISTRY.keys())
    for vb in result["voicebanks"]:
        assert "license_summary" in vb
        assert "min_midi_note" in vb
        assert "max_midi_note" in vb
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voicebank_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.tools.voicebank_tools'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/tools/voicebank_tools.py
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY


def register(mcp: FastMCP):
    @mcp.tool()
    async def list_voicebanks() -> dict:
        """List available DiffSinger voicebanks and their ranges/licensing.

        Call this before synthesize_vocal to pick a voicebank id and confirm
        the melody fits its supported MIDI note range.
        """
        return {
            "voicebanks": [
                {
                    "id": vb_id,
                    "name": vb.name,
                    "language": vb.language,
                    "min_midi_note": vb.min_midi_note,
                    "max_midi_note": vb.max_midi_note,
                    "license_summary": vb.license_summary,
                }
                for vb_id, vb in VOICEBANK_REGISTRY.items()
            ]
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voicebank_tools.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/tools/voicebank_tools.py tests/test_voicebank_tools.py
git commit -m "feat: add list_voicebanks MCP tool"
```

---

### Task 9: `synthesize_vocal` tool

**Files:**
- Create: `vocal_synth_mcp/tools/synthesize_tools.py`
- Test: `tests/test_synthesize_tools.py`

**Interfaces:**
- Consumes: `DiffSingerClient` from Task 4; `NoteEvent`, `build_ds_file`, `measure_wav_duration_seconds` from Task 3; `VOICEBANK_REGISTRY` from Task 5; `ErrorCode`, `VocalSynthMCPError` from Task 1.
- Produces: MCP tool `synthesize_vocal(notes: list[dict], bpm: float, voicebank: str, expressive_params: dict | None = None) -> dict` registered via `register(mcp: FastMCP)`; module-level `_client: DiffSingerClient` (patched in tests). Used by Task 10.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synthesize_tools.py
import asyncio
import wave
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.tools import synthesize_tools
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError


def _write_silent_wav(path: str, seconds: float, framerate: int = 44100) -> None:
    n_frames = int(seconds * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)


def _register() -> FastMCP:
    mcp = FastMCP("test")
    synthesize_tools.register(mcp)
    return mcp


def test_synthesize_vocal_rejects_unknown_voicebank():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    notes = [{"pitch": 60, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank="does-not-exist"))
    assert exc_info.value.code == ErrorCode.VOICEBANK_NOT_FOUND


def test_synthesize_vocal_rejects_note_outside_voicebank_range():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    voicebank_id = next(iter(synthesize_tools.VOICEBANK_REGISTRY))
    vb = synthesize_tools.VOICEBANK_REGISTRY[voicebank_id]
    notes = [{"pitch": vb.max_midi_note + 1, "duration_beats": 1.0, "lyric": "hi"}]
    with pytest.raises(VocalSynthMCPError) as exc_info:
        asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank=voicebank_id))
    assert exc_info.value.code == ErrorCode.NOTE_OUT_OF_RANGE


def test_synthesize_vocal_returns_wav_path_and_diagnostics(tmp_path):
    mcp = _register()
    tool = mcp._tool_manager.get_tool("synthesize_vocal")
    wav_path = str(tmp_path / "out.wav")
    _write_silent_wav(wav_path, seconds=1.0)

    voicebank_id = next(iter(synthesize_tools.VOICEBANK_REGISTRY))
    notes = [
        {"pitch": 60, "duration_beats": 1.0, "lyric": "hi"},
        {"pitch": 62, "duration_beats": 1.0, "lyric": "there"},
    ]
    with patch.object(
        synthesize_tools._client, "synthesize",
        return_value={"wav_path": wav_path, "warnings": ["[variance] Warning: OOV phoneme"]},
    ):
        result = asyncio.run(tool.fn(notes=notes, bpm=120.0, voicebank=voicebank_id))

    assert result["wav_path"] == wav_path
    assert result["diagnostics"]["warnings"] == ["[variance] Warning: OOV phoneme"]
    assert result["diagnostics"]["requested_duration_seconds"] == pytest.approx(2.0)
    assert result["diagnostics"]["actual_duration_seconds"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_synthesize_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.tools.synthesize_tools'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/tools/synthesize_tools.py
from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.diffsinger_client import DiffSingerClient
from vocal_synth_mcp_shared.error_codes import ErrorCode, VocalSynthMCPError
from vocal_synth_mcp_shared.protocol import NoteEvent, build_ds_file, measure_wav_duration_seconds
from vocal_synth_mcp_shared.voicebanks import VOICEBANK_REGISTRY

_client = DiffSingerClient()


def register(mcp: FastMCP):
    @mcp.tool()
    async def synthesize_vocal(
        notes: list[dict], bpm: float, voicebank: str, expressive_params: dict | None = None
    ) -> dict:
        """Render a vocal-only WAV stem from an explicit melody + lyrics.

        This tool does not compose anything — notes and lyrics must already
        be fully decided (by the calling LLM's conversation with the user)
        before calling this. Call validate_score first to catch problems
        cheaply, and list_voicebanks to pick a valid `voicebank` id.

        Args:
            notes: List of {"pitch": int (MIDI note, -1 for rest),
                "duration_beats": float, "lyric": str or null}. One entry
                per sung syllable; rests use lyric=null.
            bpm: Tempo in beats per minute.
            voicebank: A voicebank id from list_voicebanks.
            expressive_params: Optional explicit pitch/energy/breathiness/
                tension curves. Omit to let DiffSinger's variance model
                predict them automatically.
        """
        if voicebank not in VOICEBANK_REGISTRY:
            raise VocalSynthMCPError(
                ErrorCode.VOICEBANK_NOT_FOUND,
                f"unknown voicebank {voicebank!r}. Call list_voicebanks for valid ids.",
            )
        vb = VOICEBANK_REGISTRY[voicebank]
        note_events = [
            NoteEvent(pitch=n["pitch"], duration_beats=n["duration_beats"], lyric=n.get("lyric"))
            for n in notes
        ]
        for i, note in enumerate(note_events):
            if note.pitch != -1 and not (vb.min_midi_note <= note.pitch <= vb.max_midi_note):
                raise VocalSynthMCPError(
                    ErrorCode.NOTE_OUT_OF_RANGE,
                    f"note {i}: pitch {note.pitch} is outside {voicebank}'s range "
                    f"{vb.min_midi_note}-{vb.max_midi_note}",
                )

        ds_entry = build_ds_file(note_events, bpm, expressive_params)
        result = _client.synthesize(ds_entry, experiment=vb.experiment)
        actual_duration = measure_wav_duration_seconds(result["wav_path"])
        requested_beats = sum(n.duration_beats for n in note_events)
        requested_seconds = requested_beats * 60.0 / bpm

        return {
            "wav_path": result["wav_path"],
            "diagnostics": {
                "warnings": result["warnings"],
                "requested_duration_seconds": round(requested_seconds, 3),
                "actual_duration_seconds": round(actual_duration, 3),
            },
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synthesize_tools.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/tools/synthesize_tools.py tests/test_synthesize_tools.py
git commit -m "feat: add synthesize_vocal MCP tool"
```

---

### Task 10: Tool auto-registration

**Files:**
- Create: `vocal_synth_mcp/tool_registry.py`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Consumes: `vocal_synth_mcp.tools` package (Tasks 7-9).
- Produces: `register_all_tools(mcp: FastMCP) -> None`; `_EXPECTED_MODULES: frozenset[str]`. Used by Task 11.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tool_registry.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tool_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.tool_registry'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/tool_registry.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tool_registry.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add vocal_synth_mcp/tool_registry.py tests/test_tool_registry.py
git commit -m "feat: add tool auto-registration"
```

---

### Task 11: FastMCP entry point

**Files:**
- Create: `vocal_synth_mcp/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `load_instructions` from Task 6; `register_all_tools` from Task 10.
- Produces: module-level `mcp: FastMCP`; `main() -> None` (matches `pyproject.toml`'s `vocal-synth-mcp = "vocal_synth_mcp.main:main"` script entry).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
def test_main_module_registers_all_tools_on_import():
    import vocal_synth_mcp.main as main_module

    names = {t.name for t in main_module.mcp._tool_manager.list_tools()}
    assert {"synthesize_vocal", "list_voicebanks", "validate_score"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocal_synth_mcp.main'`

- [ ] **Step 3: Write the implementation**

```python
# vocal_synth_mcp/main.py
import sys

# MCP's stdio transport requires UTF-8 JSON-RPC framing; Python's default
# stdio encoding otherwise follows the OS/locale default, which on Windows
# is a legacy codepage, not UTF-8. Must happen before anything touches
# stdio. Same fix as reaper-mcp's main.py, same underlying reason.
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from mcp.server.fastmcp import FastMCP

from vocal_synth_mcp.instructions import load_instructions
from vocal_synth_mcp.tool_registry import register_all_tools

mcp = FastMCP("VocalSynthMCP", instructions=load_instructions())
register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across every task pass, no failures

- [ ] **Step 6: Commit**

```bash
git add vocal_synth_mcp/main.py tests/test_main.py
git commit -m "feat: add FastMCP entry point"
```

---

### Task 12: Install scripts

**Files:**
- Create: `install.sh`
- Create: `install.bat`

**Interfaces:**
- Consumes: `pyproject.toml`'s `[project.optional-dependencies].dev` extra.
- Produces: nothing consumed by other tasks — these are user-facing setup scripts referenced by Task 13's `docs/INSTALLATION.md`.

- [ ] **Step 1: Write `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up vocal-synth-mcp..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

if [ -z "${VOCAL_SYNTH_DIFFSINGER_HOME:-}" ]; then
    echo ""
    echo "VOCAL_SYNTH_DIFFSINGER_HOME is not set."
    echo "Clone openvpi/DiffSinger separately, install its own requirements.txt"
    echo "(PyTorch >=2.4.0 matched to your CUDA version), then set:"
    echo "  export VOCAL_SYNTH_DIFFSINGER_HOME=/path/to/DiffSinger"
    echo "See docs/INSTALLATION.md for full steps."
fi

echo "Done. Run 'vocal-synth-mcp' (inside .venv) to start the server."
```

- [ ] **Step 2: Write `install.bat`**

```bat
@echo off
setlocal

cd /d "%~dp0"

echo Setting up vocal-synth-mcp...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -e ".[dev]"

if "%VOCAL_SYNTH_DIFFSINGER_HOME%"=="" (
    echo.
    echo VOCAL_SYNTH_DIFFSINGER_HOME is not set.
    echo Clone openvpi/DiffSinger separately, install its own requirements.txt
    echo ^(PyTorch ^>=2.4.0 matched to your CUDA version^), then set:
    echo   setx VOCAL_SYNTH_DIFFSINGER_HOME "C:\path\to\DiffSinger"
    echo See docs\INSTALLATION.md for full steps.
)

echo Done. Run 'vocal-synth-mcp' ^(inside .venv^) to start the server.
```

- [ ] **Step 3: Verify both scripts are syntactically valid**

Run: `bash -n install.sh`
Expected: no output, exit code 0

Run (on Windows): `cmd /c "install.bat & exit /b 0"` is not safe to run unattended (it creates a venv) — instead just confirm no obvious syntax errors by eye per the content above; full execution is covered by Task 14's real install.

- [ ] **Step 4: Commit**

```bash
git add install.sh install.bat
git commit -m "feat: add install scripts"
```

---

### Task 13: Repo docs

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/INSTALLATION.md`
- Create: `docs/TOOLS.md`
- Create: `CONTRIBUTING.md`
- Create: `CHANGELOG.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the finished implementation from Tasks 1-11 (this task documents what exists).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Write `docs/ARCHITECTURE.md`**

```markdown
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
```

- [ ] **Step 2: Write `docs/INSTALLATION.md`**

```markdown
# Installation

## 1. Install this package

```bash
./install.sh    # or install.bat on Windows
```

This creates a `.venv` and installs `vocal-synth-mcp` plus its dev
dependencies (`pytest`, `pytest-asyncio`, `g2p_en`).

## 2. Set up DiffSinger separately

DiffSinger is not a Python dependency of this project — it's a
separately-cloned checkout this server subprocesses into.

```bash
git clone https://github.com/openvpi/DiffSinger.git
cd DiffSinger
python -m venv .venv-diffsinger
source .venv-diffsinger/bin/activate   # .venv-diffsinger\Scripts\activate on Windows
pip install torch>=2.4.0   # match this to your CUDA version first — see pytorch.org
pip install -r requirements.txt
```

Set `VOCAL_SYNTH_DIFFSINGER_HOME` to point at that clone:

```bash
export VOCAL_SYNTH_DIFFSINGER_HOME=/path/to/DiffSinger        # macOS/Linux
setx VOCAL_SYNTH_DIFFSINGER_HOME "C:\path\to\DiffSinger"       # Windows
```

## 3. Install a voicebank

v1 ships configured for the LUNAI Project's "Katyusha" voicebank (see
`vocal_synth_mcp_shared/voicebanks.py` for the full license summary —
non-commercial use is fine with attribution, commercial use needs
written per-character permission from LUNAI first).

1. Download the voicebank from LUNAI Project's GitHub releases
   (`github.com/lunaiproject/lunai_singers`).
2. Extract the DiffSinger checkpoint from its OpenUtau packaging into
   `$VOCAL_SYNTH_DIFFSINGER_HOME/checkpoints/lunai_katyusha/` (the folder
   name must match the `experiment` value in `voicebanks.py`).
3. To use a different voicebank instead, add a new entry to
   `VOICEBANK_REGISTRY` in `vocal_synth_mcp_shared/voicebanks.py` — one
   dataclass instance, no other code changes needed.

## 4. Run

```bash
vocal-synth-mcp
```

Add it to your MCP client config (Claude Desktop/Code) alongside
reaper-mcp, same as any other stdio MCP server.
```

- [ ] **Step 3: Write `docs/TOOLS.md`**

```markdown
# Tools

## `validate_score(notes, bpm) -> dict`

Fast pre-check for a note+lyric sequence. Does not invoke DiffSinger.

Returns `{"valid": true, "note_count": int, "sung_note_count": int, "total_duration_seconds": float}`
or raises `VocalSynthMCPError` (`NOTE_OUT_OF_RANGE`, `INVALID_PARAMETER`,
`MISSING_PARAMETER`).

## `list_voicebanks() -> dict`

Returns `{"voicebanks": [{"id", "name", "language", "min_midi_note", "max_midi_note", "license_summary"}, ...]}`.

## `synthesize_vocal(notes, bpm, voicebank, expressive_params=None) -> dict`

Renders a vocal-only WAV stem.

- `notes`: `[{"pitch": int (-1 for rest), "duration_beats": float, "lyric": str | null}]`
- `voicebank`: an id from `list_voicebanks`
- `expressive_params`: optional `{"f0_seq"/"energy"/"breathiness"/"voicing"/"tension": str}` — omit for automatic prediction

Returns `{"wav_path": str, "diagnostics": {"warnings": list[str], "requested_duration_seconds": float, "actual_duration_seconds": float}}`
or raises `VocalSynthMCPError` (`VOICEBANK_NOT_FOUND`, `NOTE_OUT_OF_RANGE`,
`DIFFSINGER_NOT_CONFIGURED`, `SUBPROCESS_TIMEOUT`, `VARIANCE_STAGE_FAILED`,
`ACOUSTIC_STAGE_FAILED`, `SYNTHESIS_FAILED`).
```

- [ ] **Step 4: Write `CONTRIBUTING.md`**

```markdown
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
```

- [ ] **Step 5: Write `CHANGELOG.md`**

```markdown
# Changelog

## Unreleased

- Initial v1: `synthesize_vocal`, `list_voicebanks`, `validate_score` MCP
  tools. Subprocess integration with a separately-cloned openvpi/DiffSinger
  checkout. LUNAI Project's "Katyusha" voicebank as the configured default.
```

- [ ] **Step 6: Update `README.md`**

Read the current `README.md` first, then replace its "Status" section
(the part starting `**Status:** design complete, implementation not
started.`) with:

```markdown
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
```

- [ ] **Step 7: Commit**

```bash
git add docs/ARCHITECTURE.md docs/INSTALLATION.md docs/TOOLS.md CONTRIBUTING.md CHANGELOG.md README.md
git commit -m "docs: add architecture/installation/tools docs, update README status"
```

---

### Task 14: Manual end-to-end verification (go/no-go gate)

**Files:** none created — this is a manual verification pass against a
real DiffSinger checkout, not automatable in CI (needs GPU + external
model weights).

**Interfaces:**
- Consumes: the complete v1 implementation from Tasks 1-13.
- Produces: a real rendered WAV file + a documented go/no-go decision on the LUNAI Katyusha voicebank.

- [ ] **Step 1: Set up the real environment**

Follow `docs/INSTALLATION.md` for real: clone `openvpi/DiffSinger`,
install its requirements with a real PyTorch matched to your CUDA
version, download and place the LUNAI Katyusha voicebank, set
`VOCAL_SYNTH_DIFFSINGER_HOME`.

- [ ] **Step 2: Confirm the output-path convention**

Manually run DiffSinger's `scripts/infer.py variance` and `... acoustic`
once by hand against a minimal `.ds` file to see where it actually writes
the output WAV. Compare against `diffsinger_client.py`'s assumption
(`infer_out/{render_id}.wav`) and fix that one line in
`vocal_synth_mcp/diffsinger_client.py` if the real behavior differs.

- [ ] **Step 3: Run a real synthesis through the MCP server**

Start the server (`vocal-synth-mcp`) and, from an MCP client (or a small
manual script calling `synthesize_tools.register`'s tool function
directly against the real `_client`), call `synthesize_vocal` with a
short real phrase — e.g. 4-8 notes, a few words of lyric — at a real bpm.

- [ ] **Step 4: Confirm the .ds phoneme dictionary matches this voicebank**

If the acoustic stage errors on phoneme lookup, the `g2p_en`-produced
ARPAbet phonemes don't match Katyusha's dictionary — check
`$VOCAL_SYNTH_DIFFSINGER_HOME/checkpoints/lunai_katyusha/` for a phoneme
dictionary file and adjust `protocol.py`'s phoneme mapping (or the "SP"
rest-token convention) to match what's actually there.

- [ ] **Step 5: Listen to the output**

Play the resulting WAV. Judge: does it sing recognizable English at the
requested pitch/rhythm? Is the voice character usable for the intended
EDM/pop context?

- [ ] **Step 6: Confirm real VRAM usage**

While the acoustic stage is running, check actual GPU memory usage
(`nvidia-smi` on a second terminal, or Task Manager's GPU tab on
Windows). This resolves the design doc's open question #5 — expected to
be comfortably under the RTX 5070's 12GB given the documented CPU
fallback path, but confirm the real number rather than leaving it as an
inference.

- [ ] **Step 7: Record the go/no-go decision**

Add a short section to `docs/2026-07-21-design.md`'s "Open questions"
recording the real outcome — voicebank verdict ("LUNAI Katyusha confirmed
usable, v1 default stands" or "rejected: <reason>, swap `voicebanks.py`'s
entry for <replacement> and repeat this task") and the measured VRAM
figure from Step 6. Commit that update.

```bash
git add docs/2026-07-21-design.md
git commit -m "docs: record v1 voicebank verification outcome"
```
