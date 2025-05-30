"""
Comprehensive exception hierarchy for the Speechmatics Batch SDK.
"""

from __future__ import annotations

from typing import Any


class SpeechmaticsError(Exception):
    """Base exception for all Speechmatics Batch SDK errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
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


class BatchError(SpeechmaticsError):
    """Raised when batch processing fails."""

    pass


class JobError(SpeechmaticsError):
    """Raised when there's an error with a job."""

    pass


class TimeoutError(SpeechmaticsError):
    """Raised when an operation times out."""

    pass
