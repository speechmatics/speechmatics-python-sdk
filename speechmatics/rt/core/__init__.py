"""
Speechmatics Real-Time SDK - Core Module

Simplified and optimized core components for real-time speech transcription.
"""

from .async_client import AsyncClient
from .events import EventEmitter
from .exceptions import AudioError
from .exceptions import AuthenticationError
from .exceptions import ConfigurationError
from .exceptions import ConnectionError
from .exceptions import EndOfTranscriptError
from .exceptions import ForceEndSession
from .exceptions import SessionError
from .exceptions import SpeechmaticsError
from .exceptions import TimeoutError
from .exceptions import TranscriptionError
from .exceptions import TransportError
from .models import AudioEncoding
from .models import AudioEventsConfig
from .models import AudioFormat
from .models import ClientMessageType
from .models import ConnectionConfig
from .models import ServerMessageType
from .models import SessionInfo
from .models import TranscriptionConfig
from .models import TranscriptResult
from .models import TranslationConfig

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
