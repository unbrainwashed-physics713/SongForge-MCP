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
