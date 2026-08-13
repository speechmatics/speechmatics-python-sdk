from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from typing import Optional
from typing import Union
from warnings import warn

from speechmatics.rt import Model
from speechmatics.rt import TranscriptionConfig as RTTranscriptionConfig

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_WORD_DELIMITER = " "


class ClientMessageType(str, Enum):
    """
    Message types that can be sent from client to the Agent STT service.

    The Agent STT service adds no client messages of its own; these are the RT messages
    it forwards downstream.

    Attributes:
        START_RECOGNITION: Starts the session, carrying the audio and transcription config.
        END_OF_STREAM: Signals that no more audio will be sent.
        FORCE_END_OF_UTTERANCE: Closes the current turn immediately, flushing the buffered
            segment. Sent by clients that run their own VAD.
        SET_RECOGNITION_CONFIG: Updates the transcription config mid-session.
        GET_SPEAKERS: Requests the session's speaker data.
    """

    START_RECOGNITION = "StartRecognition"
    END_OF_STREAM = "EndOfStream"
    FORCE_END_OF_UTTERANCE = "ForceEndOfUtterance"
    SET_RECOGNITION_CONFIG = "SetRecognitionConfig"
    GET_SPEAKERS = "GetSpeakers"


class ServerMessageType(str, Enum):
    """
    Message types that can be received from the Agent STT service.

    The service emits its own segment, speech and turn messages, and passes the RT engine's
    messages through unchanged.

    Attributes:
        RECOGNITION_STARTED: Session accepted; carries the session id and language pack info.
        AUDIO_ADDED: Audio frame acknowledged.
        ADD_SEGMENT: A finalized segment, closed at a turn or content boundary.
        ADD_PARTIAL_SEGMENT: Interim preview of the segment being built.
        SPEECH_STARTED: The service's VAD detected speech onset.
        SPEECH_ENDED: The service's VAD detected speech offset.
        START_OF_TURN: The service's turn detection opened a turn.
        END_OF_TURN: The service's turn detection closed a turn.
        ADD_TRANSCRIPT: Word-level final transcript, passed through from the RT engine.
        ADD_PARTIAL_TRANSCRIPT: Word-level partial transcript, passed through from the RT engine.
        END_OF_UTTERANCE: Consumed by the service for segmentation and not forwarded; listed
            so handlers stay valid against a direct RT endpoint.
        END_OF_TRANSCRIPT: The service has finished sending messages.
        SPEAKERS_RESULT: Response to GetSpeakers.
        AUDIO_EVENT_STARTED: Start of a detected audio event.
        AUDIO_EVENT_ENDED: End of a detected audio event.
        INFO: Informational message.
        WARNING: Warning; the session continues, possibly with adjusted config.
        ERROR: Error; the session is over.

    Examples:
        >>> @client.on(ServerMessageType.ADD_SEGMENT)
        >>> def handle_segment(message):
        ...     print(message["segment"]["transcript"])
    """

    RECOGNITION_STARTED = "RecognitionStarted"
    AUDIO_ADDED = "AudioAdded"
    ADD_SEGMENT = "AddSegment"
    ADD_PARTIAL_SEGMENT = "AddPartialSegment"
    SPEECH_STARTED = "SpeechStarted"
    SPEECH_ENDED = "SpeechEnded"
    START_OF_TURN = "StartOfTurn"
    END_OF_TURN = "EndOfTurn"
    ADD_TRANSCRIPT = "AddTranscript"
    ADD_PARTIAL_TRANSCRIPT = "AddPartialTranscript"
    END_OF_UTTERANCE = "EndOfUtterance"
    END_OF_TRANSCRIPT = "EndOfTranscript"
    SPEAKERS_RESULT = "SpeakersResult"
    AUDIO_EVENT_STARTED = "AudioEventStarted"
    AUDIO_EVENT_ENDED = "AudioEventEnded"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"


SEGMENT_MESSAGES = (ServerMessageType.ADD_SEGMENT, ServerMessageType.ADD_PARTIAL_SEGMENT)

TIMED_MESSAGES = (
    ServerMessageType.SPEECH_STARTED,
    ServerMessageType.SPEECH_ENDED,
    ServerMessageType.START_OF_TURN,
    ServerMessageType.END_OF_TURN,
)


class VADMode(str, Enum):
    """
    Where turn boundaries come from. This SDK never detects them itself.

    Attributes:
        SERVER: The service runs its own VAD and turn detection, emitting SpeechStarted,
            SpeechEnded, StartOfTurn and EndOfTurn, and closing segments itself.
        CLIENT: The application closes each turn by calling `finalize()`, which sends
            ForceEndOfUtterance with an audio timestamp. Whatever produced that signal is up to
            the application - a VAD, a turn model, or a push-to-talk button - so a host
            framework's own endpointing (Pipecat, LiveKit, ...) works unchanged.
    """

    SERVER = "server"
    CLIENT = "client"


@dataclass
class VADConfig:
    """
    Tuning for the service's VAD. Only applied when `VADMode.SERVER` is in use.

    Attributes:
        window: Silence in seconds before the service closes the turn.
        onset_threshold: Speech probability above which speech starts.
        offset_threshold: Speech probability below which speech ends.
    """

    window: Optional[float] = None
    onset_threshold: Optional[float] = None
    offset_threshold: Optional[float] = None


@dataclass
class AdditionalVocabEntry:
    """
    A word to bias the engine towards, optionally with pronunciation hints.

    Attributes:
        content: The word or phrase.
        sounds_like: Alternative pronunciations, written as they sound.

    Examples:
        >>> AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"])
    """

    content: str
    sounds_like: Optional[list[str]] = None


@dataclass
class TranscriptionConfig(RTTranscriptionConfig):
    """
    Transcription config for the Agent STT service.

    Extends the RT transcription config with the service-only fields (`vad_config`,
    `emit_sentences`). See `speechmatics.rt.TranscriptionConfig` for the inherited fields.

    Attributes:
        vad_mode: Whether the service or the client decides turn boundaries.
        vad_config: Tuning for the service's VAD, used when `vad_mode` is `SERVER`.
        emit_sentences: Close a segment on every sentence boundary, not just at the turn
            boundary.
        additional_vocab: Words to bias the engine towards, as `AdditionalVocabEntry` objects
            or raw dicts.
        model: Left unset by default. The service's profile pins the model for the session,
            and sending it alongside the profile's `operating_point` would put both keys in
            the resolved StartRecognition.

    Examples:
        Service VAD, sentence-level segments:
            >>> config = TranscriptionConfig(language="en", emit_sentences=True)

        Client VAD (Pipecat, LiveKit):
            >>> config = TranscriptionConfig(language="en", vad_mode=VADMode.CLIENT)
    """

    model: Optional[Model] = None
    additional_vocab: Optional[list[Union[AdditionalVocabEntry, dict[str, Any]]]] = None
    vad_mode: VADMode = VADMode.SERVER
    vad_config: VADConfig = field(default_factory=VADConfig)
    emit_sentences: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.model is not None and self.operating_point is not None:
            raise ValueError("Cannot specify both 'model' and 'operating_point'. Use 'model' instead.")
        if self.operating_point is not None:
            warn("'operating_point' is deprecated, use 'model' instead.", DeprecationWarning, stacklevel=2)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to the wire form of `StartRecognition.transcription_config`.

        Returns:
            The config as a dict, excluding None values, with `vad_config.enabled` derived
            from `vad_mode` and `vad_mode` itself dropped.
        """
        result = super().to_dict()
        result.pop("vad_mode", None)
        vad_config = result.pop("vad_config", None) or {}
        vad_config["enabled"] = self.vad_mode is VADMode.SERVER
        result["vad_config"] = vad_config
        return result


@dataclass
class Segment:
    """
    A segment of transcript, the unit the Agent STT service works in.

    Attributes:
        transcript: The rendered segment text.
        start_time: Segment start in seconds from the start of the session.
        end_time: Segment end in seconds from the start of the session.
        speaker: Speaker label (e.g. "S1"), when diarization attributed one.
        is_final: True for AddSegment, False for AddPartialSegment.
    """

    transcript: str
    start_time: float = 0.0
    end_time: float = 0.0
    speaker: Optional[str] = None
    is_final: bool = True

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> Segment:
        """Create a Segment from an AddSegment or AddPartialSegment message."""
        segment = message.get("segment") or {}
        metadata = message.get("metadata") or {}
        return cls(
            transcript=segment.get("transcript", ""),
            start_time=metadata.get("start_time", 0.0),
            end_time=metadata.get("end_time", 0.0),
            speaker=segment.get("speaker"),
            is_final=message.get("message") == ServerMessageType.ADD_SEGMENT,
        )


@dataclass
class TimedEvent:
    """
    A speech or turn event from the service, reduced to its single timestamp.

    Attributes:
        message: The message type (SpeechStarted, SpeechEnded, StartOfTurn, EndOfTurn).
        time: The event time in seconds from the start of the session.
    """

    message: str
    time: float = 0.0

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> TimedEvent:
        """Create a TimedEvent from a speech or turn message."""
        metadata = message.get("metadata") or {}
        time = metadata.get("start_time", metadata.get("end_time", 0.0))
        return cls(message=message.get("message", ""), time=time)


@dataclass
class LanguagePackInfo:
    """
    Language pack details reported in RecognitionStarted.

    Attributes:
        language_description: Human-readable language name.
        word_delimiter: The separator between words for this language, used when joining
            segments into a transcript.
        writing_direction: "ltr" or "rtl".
        itn: Whether inverse text normalization is applied.
        adapted: Whether the language pack is adapted.
    """

    language_description: str = ""
    word_delimiter: str = DEFAULT_WORD_DELIMITER
    writing_direction: str = "ltr"
    itn: bool = True
    adapted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanguagePackInfo:
        """Create LanguagePackInfo from the RecognitionStarted language_pack_info block."""
        return cls(
            language_description=data.get("language_description", ""),
            word_delimiter=data.get("word_delimiter", DEFAULT_WORD_DELIMITER),
            writing_direction=data.get("writing_direction", "ltr"),
            itn=data.get("itn", True),
            adapted=data.get("adapted", False),
        )


@dataclass
class SessionInfo:
    """
    State of the current Agent STT session.

    Attributes:
        request_id: Client-generated id for this session.
        session_id: Service-assigned session id, set once RecognitionStarted arrives.
        language_pack_info: Language pack reported in RecognitionStarted.
    """

    request_id: str
    session_id: Optional[str] = None
    language_pack_info: LanguagePackInfo = field(default_factory=LanguagePackInfo)
