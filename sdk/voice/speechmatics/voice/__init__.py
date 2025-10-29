#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#


"""Voice Agents SDK.

A comprehensive set of utility classes tailored for Voice Agents and
using the Speechmatics Python Real-Time SDK, including the processing of
partial and final transcription from the STT engine into accumulated
transcriptions with flags to indicate changes between messages, etc.
"""

__version__ = "0.0.0"

from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import OperatingPoint
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import SpeakerIdentifier

from ._client import VoiceAgentClient
from ._models import AdditionalVocabEntry
from ._models import AgentClientMessageType
from ._models import AgentServerMessageType
from ._models import EndOfUtteranceMode
from ._models import SegmentMessage
from ._models import SessionMetricsMessage
from ._models import SmartTurnConfig
from ._models import SpeakerFocusConfig
from ._models import SpeakerFocusMode
from ._models import SpeakerMetricsMessage
from ._models import SpeechSegmentConfig
from ._models import SpeechSegmentEmitMode
from ._models import TurnPredictionMessage
from ._models import TurnStartEndMessage
from ._models import VADStatusMessage
from ._models import VoiceAgentConfig
from ._presets import VoiceAgentConfigPreset

__all__ = [
    "__version__",
    # Client
    "VoiceAgentClient",
    # Config
    "AdditionalVocabEntry",
    "AudioEncoding",
    "AudioFormat",
    "EndOfUtteranceMode",
    "OperatingPoint",
    "SpeakerDiarizationConfig",
    "SpeakerFocusConfig",
    "SpeakerFocusMode",
    "SpeakerIdentifier",
    "SmartTurnConfig",
    "SpeechSegmentConfig",
    "SpeechSegmentEmitMode",
    "VoiceAgentConfig",
    "VoiceAgentConfigPreset",
    # Client messages
    "AgentClientMessageType",
    # Server messages
    "AgentServerMessageType",
    "SegmentMessage",
    "SessionMetricsMessage",
    "SpeakerMetricsMessage",
    "TurnPredictionMessage",
    "TurnStartEndMessage",
    "VADStatusMessage",
]
