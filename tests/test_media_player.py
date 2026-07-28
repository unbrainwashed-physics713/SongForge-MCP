from songforge_mcp import media_player


def test_play_audio_now_delegates_to_default_app(monkeypatch):
    calls = []
    monkeypatch.setattr(media_player, "open_with_default_app", calls.append)
    media_player.play_audio_now("C:\\some\\track.wav")
    assert calls == ["C:\\some\\track.wav"]
