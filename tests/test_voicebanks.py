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
