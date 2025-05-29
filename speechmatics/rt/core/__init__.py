"""
Speechmatics Real-Time SDK - Core Module

Simplified and optimized core components for real-time speech transcription.
"""

from .async_client import AsyncClient
from .events import EventEmitter
from .exceptions import (
    AudioError,
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    EndOfTranscriptError,
    ForceEndSession,
    SessionError,
    SpeechmaticsError,
    TimeoutError,
    TranscriptionError,
    TransportError,
)
from .models import (
    AudioEncoding,
    AudioEventsConfig,
    AudioFormat,
    ClientMessageType,
    ConnectionConfig,
    ServerMessageType,
    SessionInfo,
    TranscriptionConfig,
    TranscriptResult,
    TranslationConfig,
)

__all__ = [
    # Main client
    "AsyncClient",
    # Event system
    "EventEmitter",
    # Configuration models
    "AudioFormat",
    "AudioEventsConfig",
    "TranscriptionConfig",
    "TranslationConfig",
    "ConnectionConfig",
    # Data models
    "SessionInfo",
    "TranscriptResult",
    # Enums
    "AudioEncoding",
    "ClientMessageType",
    "ServerMessageType",
    # Exceptions
    "SpeechmaticsError",
    "ConfigurationError",
    "AuthenticationError",
    "ConnectionError",
    "TransportError",
    "TranscriptionError",
    "AudioError",
    "SessionError",
    "TimeoutError",
    "EndOfTranscriptError",
    "ForceEndSession",
]
