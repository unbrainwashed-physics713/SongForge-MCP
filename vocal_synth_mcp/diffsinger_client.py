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
