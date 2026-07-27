import os
import tempfile

import pytest

from songforge_mcp_shared import constants


def test_timeouts_are_positive():
    assert constants.Timeouts.GENERATION > 0
    assert constants.Timeouts.SERVER_STARTUP > 0
    assert constants.Timeouts.YOUTUBE_DOWNLOAD > 0


def test_default_output_root_is_inside_this_repo_not_system_temp():
    default_root = constants._default_output_root()
    assert not default_root.startswith(tempfile.gettempdir())
    assert os.path.isfile(os.path.join(default_root, "..", "pyproject.toml"))


def test_output_dir_is_under_output_root():
    assert constants.Paths.OUTPUT_DIR.startswith(constants.Paths.OUTPUT_ROOT)


def test_reference_audio_cache_is_under_output_root():
    assert constants.Paths.REFERENCE_AUDIO_CACHE.startswith(constants.Paths.OUTPUT_ROOT)


def test_resolve_output_root_honors_env_var_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SONGFORGE_OUTPUT_DIR", str(tmp_path))
    assert constants._resolve_output_root() == str(tmp_path)


def test_resolve_output_root_falls_back_to_default_without_env_var(monkeypatch):
    monkeypatch.delenv("SONGFORGE_OUTPUT_DIR", raising=False)
    assert constants._resolve_output_root() == constants._default_output_root()


def test_ensure_private_dir_creates_directory(tmp_path):
    target = tmp_path / "nested" / "dir"
    constants.ensure_private_dir(str(target))
    assert target.is_dir()


def test_gradio_server_url_matches_host_and_port():
    assert constants.GradioServer.URL == f"http://{constants.GradioServer.HOST}:{constants.GradioServer.PORT}"


def test_no_window_popen_kwargs_returns_dict():
    kwargs = constants.no_window_popen_kwargs()
    assert isinstance(kwargs, dict)


def test_no_window_popen_kwargs_sets_creationflags_on_windows(monkeypatch):
    if not hasattr(constants.subprocess, "CREATE_NO_WINDOW"):
        pytest.skip("subprocess.CREATE_NO_WINDOW only exists on Windows")
    monkeypatch.setattr(constants.platform, "system", lambda: "Windows")
    kwargs = constants.no_window_popen_kwargs()
    assert kwargs == {"creationflags": constants.subprocess.CREATE_NO_WINDOW}


def test_no_window_popen_kwargs_empty_on_posix(monkeypatch):
    monkeypatch.setattr(constants.platform, "system", lambda: "Linux")
    assert constants.no_window_popen_kwargs() == {}
