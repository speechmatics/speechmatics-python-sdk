#
# Copyright (c) 2026, Speechmatics / Cantab Research Ltd
#

"""Speechmatics Agent STT SDK.

A client for the Speechmatics Agent STT service, built on the Speechmatics Python Real-Time
SDK. The service works in segments rather than word groups and reports speech and turn events.

This SDK runs no VAD and no turn detection of its own: either the service's VAD closes turns,
or the application's does (Pipecat, LiveKit, ...) by calling `finalize()`.
"""

__version__ = "0.0.0"

from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioError
from speechmatics.rt import AudioFormat
from speechmatics.rt import AuthBase
from speechmatics.rt import AuthenticationError
from speechmatics.rt import ConfigurationError
from speechmatics.rt import ConnectionConfig
from speechmatics.rt import ConnectionError
from speechmatics.rt import EventEmitter
from speechmatics.rt import JWTAuth
from speechmatics.rt import Microphone
from speechmatics.rt import SessionError
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import SpeakerIdentifier
from speechmatics.rt import StaticKeyAuth
from speechmatics.rt import TimeoutError
from speechmatics.rt import TranscriptionError
from speechmatics.rt import TransportError

from ._client import AgentSttAsyncClient
from ._models import DEFAULT_CHUNK_SIZE
from ._models import DEFAULT_MODEL
from ._models import DEFAULT_SAMPLE_RATE
from ._models import DEFAULT_WORD_DELIMITER
from ._models import SEGMENT_MESSAGES
from ._models import TIMED_MESSAGES
from ._models import AdditionalVocabEntry
from ._models import ClientMessageType
from ._models import LanguagePackInfo
from ._models import Model
from ._models import Segment
from ._models import ServerMessageType
from ._models import SessionInfo
from ._models import TimedEvent
from ._models import TranscriptionConfig
from ._models import TurnConfig
from ._models import TurnDetectionMode
from ._transcript import Transcript
from ._url import resolve_url

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_MODEL",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_WORD_DELIMITER",
    "SEGMENT_MESSAGES",
    "TIMED_MESSAGES",
    "__version__",
    # Client
    "AgentSttAsyncClient",
    # Config
    "AdditionalVocabEntry",
    "AudioEncoding",
    "AudioFormat",
    "ConnectionConfig",
    "SpeakerDiarizationConfig",
    "SpeakerIdentifier",
    "TranscriptionConfig",
    "TurnConfig",
    "TurnDetectionMode",
    "Model",
    # Auth
    "AuthBase",
    "JWTAuth",
    "StaticKeyAuth",
    # Messages
    "ClientMessageType",
    "ServerMessageType",
    "Segment",
    "TimedEvent",
    # Session
    "LanguagePackInfo",
    "SessionInfo",
    "Transcript",
    "resolve_url",
    # Utilities
    "EventEmitter",
    "Microphone",
    # Exceptions
    "AudioError",
    "AuthenticationError",
    "ConfigurationError",
    "ConnectionError",
    "SessionError",
    "TimeoutError",
    "TranscriptionError",
    "TransportError",
]
