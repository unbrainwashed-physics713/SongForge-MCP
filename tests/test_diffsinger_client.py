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
