from __future__ import annotations

from typing import Any
from typing import Optional


class SpeechmaticsError(Exception):
    """Base exception for all Speechmatics RT SDK errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(SpeechmaticsError):
    """Raised when there's an error in configuration."""

    pass


class AuthenticationError(SpeechmaticsError):
    """Raised when authentication fails."""

    pass


class ConnectionError(SpeechmaticsError):
    """Raised when connection to the service fails."""

    pass


class TransportError(SpeechmaticsError):
    """Raised when there's an error in the transport layer."""

    pass


class TranscriptionError(SpeechmaticsError):
    """Raised when transcription fails."""

    pass


class AudioError(SpeechmaticsError):
    """Raised when there's an issue with audio data."""

    pass


class SessionError(SpeechmaticsError):
    """Raised when there's an error with the session state."""

    pass


class TimeoutError(SpeechmaticsError):
    """Raised when an operation times out."""

    pass


class EndOfTranscriptError(SpeechmaticsError):
    """Raised when the transcript has ended."""

    pass


class ForceEndSession(SpeechmaticsError):
    """
    Exception that can be raised by user handlers to force session termination.

    This is a special exception that users can raise from event handlers
    or middleware to cleanly terminate a transcription session early.
    """

    pass
