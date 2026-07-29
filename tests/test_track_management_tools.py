import os
import time

import numpy as np
import pytest
import soundfile as sf
from mcp.server.fastmcp import FastMCP

from songforge_mcp.shared_state import jobs as _jobs
from songforge_mcp.tools import track_management_tools
from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError


def _register() -> FastMCP:
    mcp = FastMCP("test")
    track_management_tools.register(mcp)
    return mcp


def _write_tone(path, duration_seconds=1.0, samplerate=48000):
    t = np.linspace(0, duration_seconds, int(duration_seconds * samplerate), endpoint=False)
    data = 0.1 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)


def test_list_generated_tracks_returns_empty_when_output_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "does_not_exist"))
    mcp = _register()
    tool = mcp._tool_manager.get_tool("list_generated_tracks")
    assert tool.fn() == []


def test_list_generated_tracks_lists_files_newest_first_and_skips_subfolders(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    older = output_dir / "older.wav"
    _write_tone(older)
    os.utime(older, (time.time() - 100, time.time() - 100))

    newer = output_dir / "newer.wav"
    _write_tone(newer)

    stems_dir = output_dir / "stems"
    stems_dir.mkdir()
    _write_tone(stems_dir / "should_not_appear.wav")

    mcp = _register()
    tool = mcp._tool_manager.get_tool("list_generated_tracks")
    result = tool.fn()

    filenames = [r["filename"] for r in result]
    assert filenames == ["newer.wav", "older.wav"]
    assert all(r["duration_seconds"] == pytest.approx(1.0, abs=0.05) for r in result)


def test_list_generated_tracks_respects_limit(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))
    for i in range(5):
        _write_tone(output_dir / f"track_{i}.wav")

    mcp = _register()
    tool = mcp._tool_manager.get_tool("list_generated_tracks")
    assert len(tool.fn(limit=2)) == 2


def test_list_recent_jobs_returns_newest_first():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("list_recent_jobs")

    job1 = _jobs.create()
    job1.status = "complete"
    time.sleep(0.01)
    job2 = _jobs.create()
    job2.status = "running"
    job2.progress = 0.5
    job2.message = "halfway"

    result = tool.fn()
    ids = [r["job_id"] for r in result]
    assert ids.index(job2.id) < ids.index(job1.id)

    entry = next(r for r in result if r["job_id"] == job2.id)
    assert entry["status"] == "running"
    assert entry["progress"] == 0.5
    assert entry["message"] == "halfway"


def test_list_recent_jobs_respects_limit():
    mcp = _register()
    tool = mcp._tool_manager.get_tool("list_recent_jobs")
    for _ in range(5):
        _jobs.create()
    assert len(tool.fn(limit=2)) == 2


def test_delete_generated_track_rejects_path_outside_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    outside_path = tmp_path / "elsewhere.wav"
    _write_tone(outside_path)

    mcp = _register()
    tool = mcp._tool_manager.get_tool("delete_generated_track")
    with pytest.raises(SongForgeMCPError) as exc_info:
        tool.fn(audio_path=str(outside_path))
    assert exc_info.value.code == ErrorCode.INVALID_PARAMETER


def test_delete_generated_track_moves_file_to_trash_not_permanently_deleting(tmp_path, monkeypatch):
    output_root = tmp_path / "root"
    output_dir = output_root / "renders"
    output_dir.mkdir(parents=True)
    monkeypatch.setattr(constants.Paths, "OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    audio_path = output_dir / "render.wav"
    _write_tone(audio_path)

    mcp = _register()
    tool = mcp._tool_manager.get_tool("delete_generated_track")
    result = tool.fn(audio_path=str(audio_path))

    assert result["status"] == "moved_to_trash"
    assert not audio_path.exists()
    trash_path = output_root / ".trash" / "render.wav"
    assert trash_path.exists()
    assert result["trash_path"] == str(trash_path)


def test_delete_generated_track_keeps_both_on_filename_collision_in_trash(tmp_path, monkeypatch):
    output_root = tmp_path / "root"
    output_dir = output_root / "renders"
    output_dir.mkdir(parents=True)
    monkeypatch.setattr(constants.Paths, "OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(output_dir))

    trash_dir = output_root / ".trash"
    trash_dir.mkdir()
    _write_tone(trash_dir / "render.wav")  # a same-named file already trashed earlier

    audio_path = output_dir / "render.wav"
    _write_tone(audio_path)

    mcp = _register()
    tool = mcp._tool_manager.get_tool("delete_generated_track")
    result = tool.fn(audio_path=str(audio_path))

    assert result["trash_path"] != str(trash_dir / "render.wav")
    assert os.path.isfile(result["trash_path"])
    assert os.path.isfile(trash_dir / "render.wav")  # the earlier one is still there too
