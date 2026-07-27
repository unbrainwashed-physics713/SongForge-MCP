import os
import time

import numpy as np
import psutil
import pytest
import soundfile as sf

from songforge_mcp.acestep_client import (
    _REFERENCE_TRIM_WINDOW_SECONDS,
    ACEStepClient,
    _slugify_title,
    _trim_reference_for_key_coherence,
)
from songforge_mcp_shared import constants


def _write_tone(path, duration_seconds, samplerate=48000):
    t = np.linspace(0, duration_seconds, int(duration_seconds * samplerate), endpoint=False)
    data = 0.1 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)


def test_returns_unchanged_path_when_already_short_enough(tmp_path):
    path = tmp_path / "short.wav"
    _write_tone(path, _REFERENCE_TRIM_WINDOW_SECONDS - 5)
    assert _trim_reference_for_key_coherence(str(path)) == str(path)


def test_trims_long_file_to_window_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_AUDIO_CACHE", str(tmp_path / "cache"))
    path = tmp_path / "long.wav"
    _write_tone(path, 200.0)

    trimmed = _trim_reference_for_key_coherence(str(path))

    assert trimmed != str(path)
    assert os.path.isfile(trimmed)
    info = sf.info(trimmed)
    duration = info.frames / info.samplerate
    assert duration == pytest.approx(_REFERENCE_TRIM_WINDOW_SECONDS, abs=0.1)


def test_trimmed_window_is_taken_from_the_middle_not_the_start(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Paths, "REFERENCE_AUDIO_CACHE", str(tmp_path / "cache"))
    path = tmp_path / "long.wav"
    samplerate = 48000
    duration = 200.0
    # Silence everywhere except a distinctive tone right in the middle -
    # if the trim genuinely comes from the middle, the trimmed file should
    # contain real signal, not silence.
    total_frames = int(duration * samplerate)
    data = np.zeros(total_frames)
    mid_start = total_frames // 2 - samplerate
    mid_end = total_frames // 2 + samplerate
    t = np.linspace(0, 2.0, mid_end - mid_start, endpoint=False)
    data[mid_start:mid_end] = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    sf.write(str(path), data, samplerate)

    trimmed = _trim_reference_for_key_coherence(str(path))
    trimmed_data, _ = sf.read(trimmed)
    assert np.abs(trimmed_data).max() > 0.1


def test_slugify_title_produces_hyphenated_lowercase_slug():
    assert _slugify_title("Hearts on a Wire!") == "hearts-on-a-wire"


def test_slugify_title_collapses_repeated_punctuation():
    assert _slugify_title("Hearts -- on   a Wire???") == "hearts-on-a-wire"


def test_slugify_title_truncates_to_max_length():
    long_title = "a" * 100
    assert _slugify_title(long_title, max_length=10) == "a" * 10


def test_slugify_title_returns_empty_for_punctuation_only():
    assert _slugify_title("!!!???") == ""


def test_acquire_generate_lock_succeeds_when_no_lock_exists(tmp_path):
    lock_path = str(tmp_path / "generate.lock")
    assert ACEStepClient._acquire_generate_lock(lock_path) is True
    assert os.path.isfile(lock_path)


def test_acquire_generate_lock_fails_when_already_held(tmp_path):
    lock_path = str(tmp_path / "generate.lock")
    assert ACEStepClient._acquire_generate_lock(lock_path) is True
    # Simulates a second, separate songforge-mcp process trying to drive
    # its own generation while one is already in flight elsewhere - must
    # not also succeed, otherwise two processes can drive Playwright
    # against the same single-GPU ACE-Step server concurrently.
    assert ACEStepClient._acquire_generate_lock(lock_path) is False


def test_acquire_generate_lock_reclaims_stale_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Timeouts, "GENERATION", 1.0)
    lock_path = str(tmp_path / "generate.lock")
    with open(lock_path, "w"):
        pass
    old_time = time.time() - 1000
    os.utime(lock_path, (old_time, old_time))

    assert ACEStepClient._acquire_generate_lock(lock_path) is True


def test_acquire_generate_lock_reclaims_immediately_when_holder_is_dead(tmp_path):
    lock_path = str(tmp_path / "generate.lock")
    dead_pid = 999999
    while psutil.pid_exists(dead_pid):
        dead_pid += 1
    with open(lock_path, "w") as f:
        f.write(str(dead_pid))
    # Fresh mtime (not stale by age) - only reclaimable because the PID
    # written into the lock file does not correspond to a live process,
    # which is exactly what happens when Claude Desktop is force-closed
    # mid-generation and the holding process never runs its cleanup.
    assert ACEStepClient._acquire_generate_lock(lock_path) is True


def test_acquire_generate_lock_does_not_reclaim_when_holder_is_alive(tmp_path):
    lock_path = str(tmp_path / "generate.lock")
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))
    assert ACEStepClient._acquire_generate_lock(lock_path) is False


def test_acquire_launch_lock_succeeds_when_no_lock_exists(tmp_path):
    lock_path = str(tmp_path / "launch.lock")
    assert ACEStepClient._acquire_launch_lock(lock_path) is True
    assert os.path.isfile(lock_path)


def test_acquire_launch_lock_fails_when_already_held(tmp_path):
    lock_path = str(tmp_path / "launch.lock")
    assert ACEStepClient._acquire_launch_lock(lock_path) is True
    # A second, separate attempt (simulating a different OS process) must
    # not also succeed - this is the exact bug this lock exists to close:
    # two processes both launching a competing ACE-Step server.
    assert ACEStepClient._acquire_launch_lock(lock_path) is False


def test_acquire_launch_lock_reclaims_stale_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(constants.Timeouts, "SERVER_STARTUP", 1.0)
    lock_path = str(tmp_path / "launch.lock")
    with open(lock_path, "w"):
        pass
    old_time = time.time() - 1000
    os.utime(lock_path, (old_time, old_time))

    # constants.Timeouts.SERVER_STARTUP is patched, but acestep_client
    # imported Timeouts by reference from the same module object, so the
    # patched class attribute is visible through that reference too.
    assert ACEStepClient._acquire_launch_lock(lock_path) is True
