import asyncio
import os

import numpy as np
import pytest
import soundfile as sf
from mcp.server.fastmcp import FastMCP

from songforge_mcp.tools import audio_edit_tools
from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError


def _register() -> FastMCP:
    mcp = FastMCP("test")
    audio_edit_tools.register(mcp)
    return mcp


def _write_tone(path, duration_seconds=4.0, samplerate=48000, amplitude=0.5):
    t = np.linspace(0, duration_seconds, int(duration_seconds * samplerate), endpoint=False)
    data = amplitude * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)
    return data, samplerate


async def _run_and_poll(mcp, **kwargs):
    edit_tool = mcp._tool_manager.get_tool("edit_audio_track")
    result = await edit_tool.fn(**kwargs)
    from songforge_mcp.shared_state import jobs as _jobs

    job = _jobs.get(result["job_id"])
    # The real work runs via asyncio.to_thread (a genuine OS thread), so
    # zero-delay sleep(0) yields aren't enough to let it actually
    # progress - a small real delay per poll is needed.
    deadline = asyncio.get_event_loop().time() + 5.0
    while job.status == "running" and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.01)
    return job


def test_edit_audio_track_rejects_path_outside_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    outside_path = tmp_path / "elsewhere.wav"
    _write_tone(outside_path)

    mcp = _register()
    with pytest.raises(SongForgeMCPError) as exc_info:
        asyncio.run(mcp._tool_manager.get_tool("edit_audio_track").fn(audio_path=str(outside_path)))
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_edit_audio_track_trims_and_writes_new_file_without_touching_original(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=4.0)
    original_bytes = audio_path.read_bytes()

    mcp = _register()
    job = asyncio.run(_run_and_poll(
        mcp, audio_path=str(audio_path), trim_start_seconds=1.0, trim_end_seconds=3.0
    ))

    assert job.status == "complete"
    assert job.result["duration_seconds"] == pytest.approx(2.0, abs=0.05)
    new_path = job.result["audio_path"]
    assert new_path != str(audio_path)
    assert os.path.isfile(new_path)
    assert audio_path.read_bytes() == original_bytes  # original untouched

    info = sf.info(new_path)
    assert info.frames / info.samplerate == pytest.approx(2.0, abs=0.05)


def test_edit_audio_track_applies_fades(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=4.0, amplitude=0.8)

    mcp = _register()
    job = asyncio.run(_run_and_poll(
        mcp, audio_path=str(audio_path), fade_in_seconds=0.5, fade_out_seconds=0.5
    ))

    assert job.status == "complete"
    data, sr = sf.read(job.result["audio_path"])
    assert abs(data[0]) < 0.01  # faded down to (near) silence at the very start
    assert abs(data[-1]) < 0.01  # and at the very end
    # A single arbitrary middle sample can land on the sine wave's own
    # zero-crossing regardless of fading - check peak amplitude over a
    # window instead, which the fades don't reach.
    middle = data[len(data) // 2 - 500 : len(data) // 2 + 500]
    assert np.max(np.abs(middle)) > 0.7  # untouched in the middle (original amplitude 0.8)


def test_edit_audio_track_rejects_trim_start_past_duration(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=2.0)

    mcp = _register()
    job = asyncio.run(_run_and_poll(mcp, audio_path=str(audio_path), trim_start_seconds=5.0))
    assert job.status == "error"
    assert "VALUE_OUT_OF_RANGE" in job.error


def test_edit_audio_track_rejects_trim_end_before_trim_start(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=4.0)

    mcp = _register()
    job = asyncio.run(_run_and_poll(
        mcp, audio_path=str(audio_path), trim_start_seconds=3.0, trim_end_seconds=1.0
    ))
    assert job.status == "error"
    assert "VALUE_OUT_OF_RANGE" in job.error


def test_edit_audio_track_rejects_fades_longer_than_clip(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=2.0)

    mcp = _register()
    job = asyncio.run(_run_and_poll(
        mcp, audio_path=str(audio_path), fade_in_seconds=1.5, fade_out_seconds=1.5
    ))
    assert job.status == "error"
    assert "VALUE_OUT_OF_RANGE" in job.error


def test_edit_audio_track_rejects_unsupported_output_format(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=2.0)

    mcp = _register()
    job = asyncio.run(_run_and_poll(mcp, audio_path=str(audio_path), output_format="ogg"))
    assert job.status == "error"
    assert "INVALID_PARAMETER" in job.error


def test_edit_audio_track_mp3_conversion_invokes_ffmpeg_and_cleans_up_temp_wav(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=2.0)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # Simulate ffmpeg actually producing the requested output file.
        out_path = cmd[-1]
        with open(out_path, "wb") as f:
            f.write(b"fake mp3 bytes")
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(audio_edit_tools.subprocess, "run", fake_run)

    mcp = _register()
    job = asyncio.run(_run_and_poll(mcp, audio_path=str(audio_path), output_format="mp3"))

    assert job.status == "complete"
    assert job.result["output_format"] == "mp3"
    assert job.result["audio_path"].endswith(".mp3")
    assert os.path.isfile(job.result["audio_path"])
    assert len(calls) == 1 and calls[0][0] == "ffmpeg"
    # The intermediate wav soundfile had to write before ffmpeg could run
    # must not be left behind alongside the real mp3 output.
    leftover_tmp_wavs = list(output_dir.glob("*.tmp.wav"))
    assert leftover_tmp_wavs == []


def test_edit_audio_track_reports_clear_error_when_ffmpeg_missing(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    audio_path = output_dir / "render.wav"
    _write_tone(audio_path, duration_seconds=2.0)

    def missing_ffmpeg(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(audio_edit_tools.subprocess, "run", missing_ffmpeg)

    mcp = _register()
    job = asyncio.run(_run_and_poll(mcp, audio_path=str(audio_path), output_format="mp3"))

    assert job.status == "error"
    assert "SUBPROCESS_FAILED" in job.error
    assert "ffmpeg" in job.error.lower()
