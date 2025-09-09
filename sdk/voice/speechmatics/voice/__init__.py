#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#


"""Voice Agents SDK.

A comprehensive set of utility classes tailored for Voice Agents and
using the Speechmatics Python Real-Time SDK, including the processing of
partial and final transcription from the STT engine into accumulated
transcriptions with flags to indicate changes between messages, etc.
"""

__version__ = "0.1.2"

from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import OperatingPoint

from ._client import VoiceAgentClient
from ._models import AdditionalVocabEntry
from ._models import AgentClientMessageType
from ._models import AgentServerMessageType
from ._models import AnnotationFlags
from ._models import AnnotationResult
from ._models import DiarizationFocusMode
from ._models import DiarizationKnownSpeaker
from ._models import DiarizationSpeakerConfig
from ._models import EndOfUtteranceMode
from ._models import SpeakerSegment
from ._models import SpeakerVADStatus
from ._models import SpeechFragment
from ._models import VoiceAgentConfig

__all__ = [
    # SDK
    "__version__",
    # Conversation config
    "VoiceAgentConfig",
    "EndOfUtteranceMode",
    "DiarizationSpeakerConfig",
    "DiarizationFocusMode",
    "AdditionalVocabEntry",
    "DiarizationKnownSpeaker",
    "AudioEncoding",
    "AudioFormat",
    "OperatingPoint",
    # Transcription models
    "AnnotationFlags",
    "AnnotationResult",
    "SpeakerSegment",
    "SpeechFragment",
    # Events
    "SpeakerVADStatus",
    # Client
    "VoiceAgentClient",
    "AgentClientMessageType",
    "AgentServerMessageType",
]
