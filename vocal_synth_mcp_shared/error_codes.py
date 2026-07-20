from enum import IntEnum


class ErrorCode(IntEnum):
    # Process errors (1000s)
    SUBPROCESS_FAILED = 1000
    SUBPROCESS_TIMEOUT = 1001
    DIFFSINGER_NOT_CONFIGURED = 1002

    # Synthesis errors (2000s)
    SYNTHESIS_FAILED = 2000
    VARIANCE_STAGE_FAILED = 2001
    ACOUSTIC_STAGE_FAILED = 2002

    # Validation errors (3000s)
    VALIDATION_FAILED = 3000
    INVALID_PARAMETER = 3001
    MISSING_PARAMETER = 3002
    NOTE_OUT_OF_RANGE = 3003
    PHONEME_NOT_FOUND = 3004
    LYRIC_NOTE_COUNT_MISMATCH = 3005
    VOICEBANK_NOT_FOUND = 3006
    VALUE_OUT_OF_RANGE = 3007


class VocalSynthMCPError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code.name} ({code.value})] {message}")
