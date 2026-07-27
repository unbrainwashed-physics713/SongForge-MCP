import os
import platform
from types import SimpleNamespace

import pytest

from songforge_mcp.separator_client import SeparatorClient
from songforge_mcp_shared import constants
from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError

_EXE_NAME = "audio-separator.exe" if platform.system() == "Windows" else "audio-separator"


def _make_fake_venv(tmp_path):
    """Creates a fake python interpreter + audio-separator console script
    on disk so SeparatorClient._require_configured passes its existence
    checks without needing a real venv."""
    venv_dir = tmp_path / "fake_venv"
    venv_dir.mkdir()
    python_exe = venv_dir / ("python.exe" if platform.system() == "Windows" else "python")
    python_exe.write_text("")
    separator_exe = venv_dir / _EXE_NAME
    separator_exe.write_text("")
    return str(python_exe)


def test_separate_raises_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("SONGFORGE_SEPARATOR_PYTHON", raising=False)
    # A path that definitely doesn't point to a real interpreter - "" would
    # be falsy and silently fall through to any real env var still set in
    # the environment, which isn't what this test means to exercise.
    client = SeparatorClient(separator_venv_python=str(tmp_path / "no_such_python.exe"))
    with pytest.raises(SongForgeMCPError) as exc_info:
        client.separate(str(tmp_path / "input.wav"))
    assert exc_info.value.code == ErrorCode.SEPARATOR_NOT_CONFIGURED


def test_separate_raises_when_input_file_missing(tmp_path):
    python_exe = _make_fake_venv(tmp_path)
    client = SeparatorClient(separator_venv_python=python_exe)
    with pytest.raises(SongForgeMCPError) as exc_info:
        client.separate(str(tmp_path / "does_not_exist.wav"))
    assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND


def test_separate_is_idempotent_and_skips_subprocess_when_stems_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    python_exe = _make_fake_venv(tmp_path)

    input_path = tmp_path / "render.wav"
    input_path.write_text("fake audio")

    stems_dir = tmp_path / "output" / "stems"
    stems_dir.mkdir(parents=True)
    existing_vocals = stems_dir / "render_(Vocals)_model_bs_roformer.wav"
    existing_instrumental = stems_dir / "render_(Instrumental)_model_bs_roformer.wav"
    existing_vocals.write_text("fake vocals")
    existing_instrumental.write_text("fake instrumental")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called when stems already exist")

    monkeypatch.setattr("songforge_mcp.separator_client.subprocess.run", fail_if_called)

    client = SeparatorClient(separator_venv_python=python_exe)
    result = client.separate(str(input_path))

    assert result == {
        "vocals_path": str(existing_vocals),
        "instrumental_path": str(existing_instrumental),
    }


def test_separate_runs_subprocess_and_finds_output_when_no_existing_stems(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    python_exe = _make_fake_venv(tmp_path)

    input_path = tmp_path / "render.wav"
    input_path.write_text("fake audio")

    def fake_run(cmd, **kwargs):
        out_dir = cmd[cmd.index("--output_dir") + 1]
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "render_(Vocals)_model_bs_roformer.wav"), "w") as f:
            f.write("fake vocals")
        with open(os.path.join(out_dir, "render_(Instrumental)_model_bs_roformer.wav"), "w") as f:
            f.write("fake instrumental")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("songforge_mcp.separator_client.subprocess.run", fake_run)

    client = SeparatorClient(separator_venv_python=python_exe)
    result = client.separate(str(input_path))

    assert result["vocals_path"].endswith("render_(Vocals)_model_bs_roformer.wav")
    assert result["instrumental_path"].endswith("render_(Instrumental)_model_bs_roformer.wav")


def test_separate_raises_on_nonzero_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "OUTPUT_DIR", str(tmp_path / "output"))
    python_exe = _make_fake_venv(tmp_path)

    input_path = tmp_path / "render.wav"
    input_path.write_text("fake audio")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="model failed to load")

    monkeypatch.setattr("songforge_mcp.separator_client.subprocess.run", fake_run)

    client = SeparatorClient(separator_venv_python=python_exe)
    with pytest.raises(SongForgeMCPError) as exc_info:
        client.separate(str(input_path))
    assert exc_info.value.code == ErrorCode.SEPARATION_FAILED
