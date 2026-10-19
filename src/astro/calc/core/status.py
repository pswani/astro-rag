"""Statuses and reason codes (design §12.9), shared by every feature."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    OK = "ok"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class Reason(StrEnum):
    MISSING_INPUT = "missing_input"
    INVALID_LOCAL_TIME = "invalid_local_time"
    AMBIGUOUS_LOCAL_TIME = "ambiguous_local_time"
    OUT_OF_RANGE = "out_of_range"
    UNSUPPORTED_FEATURE = "unsupported_feature"
    UNSUPPORTED_CALENDAR = "unsupported_calendar"
    UNSUPPORTED_PROFILE = "unsupported_profile"
    UNSUPPORTED_METHOD = "unsupported_method"
    UNSUPPORTED_WINDOW = "unsupported_window"
    SENSITIVE_BIRTH_TIME = "sensitive_birth_time"
    DEPENDENCY_CYCLE = "dependency_cycle"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    EPHEMERIS_UNAVAILABLE = "ephemeris_unavailable"
    NO_SUNRISE = "no_sunrise"
    TIME_UNKNOWN = "time_unknown"
    TOOL_ERROR = "tool_error"


class CalcError(Exception):
    """A calculation could not be performed for a stated reason (not a bug)."""

    def __init__(self, reason: Reason, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail
