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


def _cmd_flag(cmd, flag):
    return cmd[cmd.index(flag) + 1]


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


def test_run_stage_passes_explicit_out_and_title_flags(tmp_path):
    """Confirmed against the real DiffSinger CLI: both stages accept
    --out/--title, and we always pass them so output paths never depend on
    DiffSinger's own default same-directory/derived-filename behavior."""
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))
    seen_cmds = []

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        seen_cmds.append(cmd)
        stage = cmd[2]
        out_dir = _cmd_flag(cmd, "--out")
        title = _cmd_flag(cmd, "--title")
        if stage == "variance":
            (open(os.path.join(out_dir, f"{title}.ds"), "w")).write("[]")
        else:
            (open(os.path.join(out_dir, f"{title}.wav"), "wb")).write(b"RIFF....")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run", side_effect=fake_run):
        client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")

    assert len(seen_cmds) == 2
    variance_cmd, acoustic_cmd = seen_cmds
    assert variance_cmd[2] == "variance"
    assert acoustic_cmd[2] == "acoustic"
    # acoustic's input .ds must be variance's output .ds, not the original request
    acoustic_input = acoustic_cmd[3]
    assert acoustic_input == os.path.join(
        _cmd_flag(variance_cmd, "--out"), f"{_cmd_flag(variance_cmd, '--title')}.ds"
    )


def test_synthesize_returns_wav_path_and_warnings_on_success(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        stage = cmd[2]
        out_dir = _cmd_flag(cmd, "--out")
        title = _cmd_flag(cmd, "--title")
        if stage == "variance":
            with open(os.path.join(out_dir, f"{title}.ds"), "w") as f:
                f.write("[]")
            stderr = "Warning: OOV phoneme for 'xyz'\n"
        else:
            with open(os.path.join(out_dir, f"{title}.wav"), "wb") as f:
                f.write(b"RIFF....")
            stderr = ""
        return MagicMock(returncode=0, stdout="", stderr=stderr)

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run", side_effect=fake_run):
        result = client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")

    assert result["wav_path"].endswith(".wav")
    assert os.path.isfile(result["wav_path"])
    assert any("OOV" in w for w in result["warnings"])


def test_synthesize_raises_when_variance_stage_produces_no_ds(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with pytest.raises(VocalSynthMCPError) as exc_info:
            client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
        assert exc_info.value.code == ErrorCode.VARIANCE_STAGE_FAILED


def test_synthesize_raises_when_acoustic_stage_produces_no_wav(tmp_path):
    checkout = _make_checkout(tmp_path)
    client = DiffSingerClient(diffsinger_home=str(checkout))

    def fake_run(cmd, cwd, capture_output, text, timeout, check):
        stage = cmd[2]
        if stage == "variance":
            out_dir = _cmd_flag(cmd, "--out")
            title = _cmd_flag(cmd, "--title")
            with open(os.path.join(out_dir, f"{title}.ds"), "w") as f:
                f.write("[]")
        # acoustic stage: "succeeds" per exit code but writes no .wav
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("vocal_synth_mcp.diffsinger_client.subprocess.run", side_effect=fake_run):
        with pytest.raises(VocalSynthMCPError) as exc_info:
            client.synthesize({"ph_seq": "HH AH0"}, experiment="test-exp")
        assert exc_info.value.code == ErrorCode.SYNTHESIS_FAILED
