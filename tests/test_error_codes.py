from songforge_mcp_shared.error_codes import ErrorCode, SongForgeMCPError


def test_error_carries_code_and_message():
    err = SongForgeMCPError(ErrorCode.INVALID_PARAMETER, "caption must not be empty")
    assert err.code == ErrorCode.INVALID_PARAMETER
    assert err.message == "caption must not be empty"


def test_error_string_includes_code_name_and_value():
    err = SongForgeMCPError(ErrorCode.FILE_NOT_FOUND, "reference audio not found")
    assert str(err) == "[FILE_NOT_FOUND (3008)] reference audio not found"


def test_error_codes_are_unique():
    values = [code.value for code in ErrorCode]
    assert len(values) == len(set(values))
