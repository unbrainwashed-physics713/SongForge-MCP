from songforge_mcp.youtube_reference import _extract_video_id


def test_extracts_id_from_standard_watch_url():
    assert _extract_video_id("https://www.youtube.com/watch?v=aaaaaaaaaaa") == "aaaaaaaaaaa"


def test_extracts_id_from_short_url():
    assert _extract_video_id("https://youtu.be/aaaaaaaaaaa") == "aaaaaaaaaaa"


def test_extracts_id_from_shorts_url():
    assert _extract_video_id("https://youtube.com/shorts/aaaaaaaaaaa") == "aaaaaaaaaaa"


def test_extracts_id_from_mobile_host():
    assert _extract_video_id("https://m.youtube.com/watch?v=aaaaaaaaaaa") == "aaaaaaaaaaa"


def test_rejects_non_youtube_host_even_with_matching_id_pattern():
    # The exact attack this guards against: a non-YouTube host whose URL
    # happens to match the video-ID regex shape must not be treated as a
    # valid YouTube URL, since the extracted "video ID" and raw URL both
    # get handed to yt-dlp, which supports 1000+ site extractors.
    assert _extract_video_id("https://evil-attacker-controlled.example/x?v=aaaaaaaaaaa") is None


def test_rejects_host_that_merely_contains_youtube_as_substring():
    assert _extract_video_id("https://youtube.com.evil.example/watch?v=aaaaaaaaaaa") is None


def test_rejects_garbage_url():
    assert _extract_video_id("not a url at all") is None


def test_rejects_empty_string():
    assert _extract_video_id("") is None
