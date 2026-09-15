"""Errors with stable codes that the API returns to the app."""

from __future__ import annotations


class AnalysisError(Exception):
    """A user-facing analysis failure. ``code`` is part of the API contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


VIDEO_UNREADABLE = "video_unreadable"
VIDEO_TOO_LONG = "video_too_long"
VIDEO_TOO_LARGE = "video_too_large"
UNSUPPORTED_FORMAT = "unsupported_format"
NO_PLAYER_DETECTED = "no_player_detected"
INTERNAL = "internal"
