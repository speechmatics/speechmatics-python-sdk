"""
Models for the Speechmatics RT SDK.

This module contains all data models, enums, and configuration classes used
throughout the Speechmatics Real-Time Speech Recognition SDK. These models
provide type-safe interfaces for configuration, session management, and
result handling.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class AudioEncoding(str, Enum):
    """
    Supported audio encoding formats for real-time transcription.

    The Speechmatics RT API supports several audio encoding formats for
    optimal compatibility with different audio sources and quality requirements.

    Attributes:
        PCM_F32LE: 32-bit float PCM used in the WAV audio format, little-endian architecture. 4 bytes per sample.
        PCM_S16LE: 16-bit signed integer PCM used in the WAV audio format, little-endian architecture. 2 bytes per sample.
        MULAW: 8 bit μ-law (mu-law) encoding. 1 byte per sample.

    Examples:
        >>> encoding = AudioEncoding.PCM_S16LE
    """

    PCM_F32LE = "pcm_f32le"
    PCM_S16LE = "pcm_s16le"
    MULAW = "mulaw"


@dataclass
class AudioEventsConfig:
    types: Optional[list[str]] = None
    """Optional list of audio event types to detect."""

    def to_dict(self):
        if self.types is None:
            return {}
        return asdict(self)


class ClientMessageType(str, Enum):
    """
    Message types that can be sent from client to server.

    These enum values represent the different types of messages that the
    client can send to the Speechmatics RT API during a transcription session.

    Attributes:
        START_RECOGNITION: Initiates a new transcription session with
                          configuration parameters.
        ADD_AUDIO: Indicates that audio data follows (not used in message
                   headers, audio is sent as binary data).
        END_OF_STREAM: Signals that no more audio data will be sent.
        SET_RECOGNITION_CONFIG: Updates transcription configuration during
                               an active session (advanced use).
        GET_SPEAKERS: Internal, Speechmatics only message. Allows the client to request speaker data.

    Examples:
        >>> # Starting a recognition session
        >>> message = {
        ...     "message": ClientMessageType.START_RECOGNITION,
        ...     "audio_format": audio_format.to_dict(),
        ...     "transcription_config": config.to_dict()
        ... }
        >>>
        >>> # Ending the session
        >>> end_message = {
        ...     "message": ClientMessageType.END_OF_STREAM,
        ...     "last_seq_no": sequence_number
        ... }
    """

    START_RECOGNITION = "StartRecognition"
    ADD_AUDIO = "AddAudio"
    END_OF_STREAM = "EndOfStream"
    SET_RECOGNITION_CONFIG = "SetRecognitionConfig"
    GET_SPEAKERS = "GetSpeakers"


class ServerMessageType(str, Enum):
    """
    Message types that can be received from the server.

    These enum values represent the different types of messages that the
    Speechmatics RT API can send to the client.

    Attributes:
        RECOGNITION_STARTED: Confirms that recognition has started successfully.
        AUDIO_ADDED: Acknowledges receipt of audio data (rarely used).
        ADD_PARTIAL_TRANSCRIPT: Provides interim transcription results that
            may change as more audio is processed.
        ADD_TRANSCRIPT: Provides final transcription results that will not
            change for the given audio segment.
        END_OF_UTTERANCE: Signals that an utterance has ended, based on silence.
        AUDIO_EVENT_STARTED: Signals the start of an audio event.
        AUDIO_EVENT_ENDED: Signals the end of an audio event.
        ADD_TRANSLATION: Provides final translation results that will not
            change for the given audio segment.
        ADD_PARTIAL_TRANSLATION: Provides interim translation results that
            may change as more context becomes available.
        SPEAKER_RESULT: Internal, Speechmatics only message containing the speakers data.
        INFO: Informational messages from the server.
        WARNING: Warning messages that don't stop transcription.
        ERROR: Error messages indicating transcription failure.

    Examples:
        >>> # Register event handlers for different message types
        >>> @client.on(ServerMessageType.ADD_TRANSCRIPT)
        >>> def handle_final(message):
        ...     print(f"Final: {message['metadata']['transcript']}")
        >>>
        >>> @client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
        >>> def handle_partial(message):
        ...     print(f"Partial: {message['metadata']['transcript']}")
        >>>
        >>> @client.on(ServerMessageType.ERROR)
        >>> def handle_error(message):
        ...     print(f"Error: {message['reason']}")
    """

    RECOGNITION_STARTED = "RecognitionStarted"
    AUDIO_ADDED = "AudioAdded"
    ADD_PARTIAL_TRANSCRIPT = "AddPartialTranscript"
    ADD_TRANSCRIPT = "AddTranscript"
    END_OF_TRANSCRIPT = "EndOfTranscript"
    END_OF_UTTERANCE = "EndOfUtterance"
    AUDIO_EVENT_STARTED = "AudioEventStarted"
    AUDIO_EVENT_ENDED = "AudioEventEnded"
    ADD_TRANSLATION = "AddTranslation"
    ADD_PARTIAL_TRANSLATION = "AddPartialTranslation"
    SPEAKERS_RESULT = "SpeakersResult"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"


@dataclass
class AudioFormat:
    """
    Configuration for audio format parameters.

    This class defines the audio format specification including encoding type,
    sample rate, and chunk size for streaming. These parameters must match
    the actual audio data being sent to ensure proper transcription.

    Attributes:
        encoding: Audio encoding format. Defaults to PCM_S16LE.
        sample_rate: Sample rate in Hz. Defaults to 44100 Hz.
        chunk_size: Size of audio chunks in bytes for streaming. Defaults to 4096.

    Examples:
        File:
            >>> audio_format = AudioFormat()

        Raw:
            >>> audio_format = AudioFormat(
            ...     encoding=AudioEncoding.PCM_S16LE,
            ...     sample_rate=16000,
            ... )
    """

    encoding: Optional[AudioEncoding] = None
    sample_rate: int = 44100
    chunk_size: int = 4096

    def to_dict(self) -> dict[str, Any]:
        """
        Convert audio format to dictionary.

        Returns:
            Dictionary containing audio format specification with keys:
            - type: "raw" for raw audio data | "file" for file data
            - encoding: String encoding value
            - sample_rate: Integer sample rate in Hz

        Examples:
            >>> audio_format = AudioFormat()
            >>> audio_format.to_dict()
            >>> # Returns: {
            >>> #     "type": "file",
            >>> # }

            >>> audio_format = AudioFormat(
            ...     encoding=AudioEncoding.PCM_S16LE,
            ...     sample_rate=16000
            ... )
            >>> audio_format.to_dict()
            >>> # Returns: {
            >>> #     "type": "raw",
            >>> #     "encoding": "pcm_s16le",
            >>> #     "sample_rate": 16000
            >>> # }
        """

        if self.encoding:
            return {
                "type": "raw",
                "encoding": self.encoding,
                "sample_rate": self.sample_rate,
            }

        return {
            "type": "file",
        }


@dataclass
class ConversationConfig:
    """Conversation configuration for end-of-utterance detection."""

    end_of_utterance_silence_trigger: Optional[float] = None
    """How much silence in seconds is required to trigger end of utterance detection."""


@dataclass
class SpeakerDiarizationConfig:
    """Speaker diarization configuration."""

    max_speakers: Optional[int] = None
    """This enforces the maximum number of speakers allowed in a single audio stream."""

    speaker_sensitivity: Optional[float] = None
    """The sensitivity of the speaker detection.
    This is a number between 0 and 1, where 0 means least sensitive and 1 means
    most sensitive."""

    prefer_current_speaker: Optional[bool] = None
    """Whether to prefer the current speaker when assigning speaker labels.
    If true, the algorithm will prefer to stay with the current active speaker if it
    is a close enough match, even if other speakers may be closer. This is useful
    for cases where we can flip incorrectly between similar speakers during a single
    speaker section."""


@dataclass
class TranscriptionConfig:
    """
    Configuration for transcription behavior and features.

    Attributes:
        language: (Optional) ISO 639-1 language code (e.g., "en", "es", "fr").
            Defaults to "en".
        operating_point: (Optional) Which acoustic model to use.
            Defaults to "enhanced".
        output_locale: (Optional) RFC-5646 language code for transcript output (eg. "en-US").
            Defaults to None.
        diarization: Type of diarization to use. Options: "none", "speaker.
            Defaults to None.
        additional_vocab: (Optional) Additional vocabulary that is not part of the standard language.
            Defaults to None.
        punctuation_overrides: (Optional) Permitted punctuation marks for advanced punctuation.
            Defaults to None.
        domain: (Optional) Optionally request a language pack optimized for a specific domain (e.g. 'finance').
            Defaults to None.
        enable_entities: (Optional) Whether to enable entity detection/recognition.
            Defaults to None.
        enable_partials: (Optional) Whether to receive partial transcription results.
            Defaults to None.
        max_delay: (Optional) Maximum delay in seconds for transcript delivery.
            Defaults to None.
        max_delay_mode: (Optional) Determines whether the threshold specified in max_delay can be exceeded
            if a potential entity is detected. Flexible means if a potential entity
            is detected, then the max_delay can be overriden until the end of that
            entity. Fixed means that max_delay specified ignores any potential
            entity that would not be completed within that threshold.
        speaker_diarization_config: (Optional) Configuration for speaker diarization.
            Defaults to None.
        streaming_mode: (Optional) Indicates if we run the engine in streaming mode, or regular RT mode.
        audio_filtering_config: (Optional) Configuration for limiting the transcription of quiet audio.
            Defaults to None.
        transcript_filtering_config: (Optional) Configuration for applying filtering to the transcription.
            Defaults to None.
        conversation_config: (Optional) Configuration for end-of-utterance detection.
            Defaults to None.
        ctrl: (Optional) Configuration for controlling the engine.
            Defaults to None.


    Examples:
        Basic English transcription:
            >>> config = TranscriptionConfig(language="en")

        Spanish with partials enabled:
            >>> config = TranscriptionConfig(
            ...     language="es",
            ...     operating_point="enhanced",
            ...     enable_partials=True
            ... )

        Advanced configuration with speaker diarization:
            >>> config = TranscriptionConfig(
            ...     language="en",
            ...     enable_partials=True,
            ...     max_delay=5.0,
            ...     speaker_diarization_config={
            ...         "speaker_sensitivity": 0.7,
            ...         "max_speakers": 4
            ...     }
            ... )
    """

    language: str = "en"
    operating_point: Optional[str] = None
    output_locale: Optional[str] = None
    diarization: Optional[str] = None
    additional_vocab: Optional[dict] = None
    punctuation_overrides: Optional[dict] = None
    domain: Optional[str] = None
    enable_entities: Optional[bool] = None
    audio_filtering_config: Optional[dict] = None
    transcript_filtering_config: Optional[dict] = None
    max_delay: Optional[float] = None
    max_delay_mode: Optional[str] = None
    enable_partials: Optional[bool] = None
    speaker_diarization_config: Optional[SpeakerDiarizationConfig] = None
    streaming_mode: Optional[bool] = None
    conversation_config: Optional[ConversationConfig] = None
    ctrl: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert transcription parameters to dictionary.

        Returns:
        Transcription configuration as a dict while excluding None values.

        Examples:
            >>> config = TranscriptionConfig(
            ...     language="en",
            ...     enable_partials=True,
            ...     max_delay=5.0,
            ...     enable_entities=True
            ... )
            >>> api_dict = config.to_dict()
            >>> # Returns: {
            >>> #     "language": "en",
            >>> #     "enable_partials": True,
            >>> #     "max_delay_mode": "flexible",
            >>> #     "enable_entities": True,
            >>> #     "max_delay": 5.0
            >>> # }
        """
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


@dataclass
class TranslationConfig:
    """Translation config.

    Attributes:
        target_languages: Target languages for which translation should be produced.
        enable_partials: Indicates if partial translation, where sentences are produced
            immediately, is enabled.

    Examples:
        >>> config = TranslationConfig(
        ...     target_languages=["fr", "es"],
        ...     enable_partials=True
        ... )
        >>> config_dict = config.to_dict()
        >>> # Returns: {
        >>> #     "target_languages": ["fr", "es"],
        >>> #     "enable_partials": True
        >>> # }
    """

    target_languages: list[str]
    enable_partials: Optional[bool] = None

    def to_dict(self):
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


@dataclass
class ConnectionConfig:
    """
    Configuration for WebSocket connection parameters.

    This class defines all connection-related settings including URL,
    authentication, timeouts, and advanced features like temporary
    token generation.

    Attributes:
        url: WebSocket endpoint URL (e.g., "wss://eu2.rt.speechmatics.com/v2").
        api_key: Speechmatics API key for authentication.
        connect_timeout: Timeout in seconds for connection establishment.
        operation_timeout: Default timeout for transcription operations.
        ping_timeout: Timeout for WebSocket ping/pong heartbeat.
        buffer_size: Maximum number of messages to buffer.
        semaphore_timeout: Timeout for buffer semaphore acquisition.
        generate_temp_token: Whether to generate temporary tokens for enhanced security.

    Raises:
        ValueError: If URL format is invalid, API key is empty, timeouts are
                   not positive, or buffer_size is out of range.

    Examples:
        Basic configuration:
            >>> config = ConnectionConfig(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-api-key"
            ... )

        High-throughput configuration:
            >>> config = ConnectionConfig(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-api-key",
            ...     buffer_size=2048,
            ...     operation_timeout=600.0
            ... )

        Secure configuration with temporary tokens:
            >>> config = ConnectionConfig(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-main-api-key",
            ...     generate_temp_token=True,
            ...     connect_timeout=60.0
            ... )
    """

    url: str
    api_key: str
    connect_timeout: float = 30.0
    operation_timeout: float = 300.0
    ping_timeout: float = 60.0
    buffer_size: int = 512
    semaphore_timeout: float = 120.0
    generate_temp_token: bool = False


@dataclass
class SessionInfo:
    """
    Information about the current transcription session.

    This class tracks session state and metadata throughout the lifecycle
    of a real-time transcription session, providing unique identifiers
    and sequence tracking.

    Attributes:
        request_id: Unique identifier for this client request/session.
        session_id: Server-assigned session ID (set after recognition starts).
        sequence_number: Current sequence number for message ordering.
        is_running: Whether the transcription session is currently active.

    Examples:
        Creating session info:
            >>> import uuid
            >>> session = SessionInfo(request_id=str(uuid.uuid4()))

        Checking session state:
            >>> if session.is_running:
            ...     # Session is active, can send audio
            ...     pass
    """

    request_id: str
    session_id: Optional[str] = None
    sequence_number: int = 0
    is_running: bool = False


@dataclass
class TranscriptResult:
    """
    Structured representation of transcription results.

    This class provides a convenient way to work with transcription results
    from the Speechmatics RT API, extracting and organizing the relevant
    information from server messages.

    Attributes:
        transcript: The transcribed text content.
        is_final: Whether this is a final result (True) or partial (False).
        confidence: Confidence score for the transcription (0.0 to 1.0).
        start_time: Start time of the audio segment in seconds.
        end_time: End time of the audio segment in seconds.
        speaker: Speaker label if speaker diarization is enabled.

    Examples:
        Creating from server message:
            >>> @client.on(ServerMessageType.ADD_TRANSCRIPT)
            >>> def handle_transcript(message):
            ...     result = TranscriptResult.from_message(message)
            ...     print(f"Final: {result.transcript}")
            ...     if result.confidence:
            ...         print(f"Confidence: {result.confidence:.2f}")

        Working with timing information:
            >>> if result.start_time and result.end_time:
            ...     duration = result.end_time - result.start_time
            ...     print(f"Segment duration: {duration:.2f}s")

        Speaker diarization results:
            >>> if result.speaker:
            ...     print(f"Speaker {result.speaker}: {result.transcript}")
    """

    transcript: str
    is_final: bool
    confidence: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> TranscriptResult:
        """
        Create a TranscriptResult from a server message.

        Extracts and organizes transcription information from the raw
        server message format into a structured, easy-to-use object.

        Args:
            message: Raw message dictionary from the Speechmatics RT API
                    containing transcription results.

        Returns:
            A TranscriptResult object with extracted information.

        Examples:
            >>> # Typical server message structure:
            >>> message = {
            ...     "message": "AddTranscript",
            ...     "metadata": {
            ...         "transcript": "Hello world",
            ...         "confidence": 0.95,
            ...         "start_time": 1.5,
            ...         "end_time": 2.8
            ...     }
            ... }
            >>> result = TranscriptResult.from_message(message)
            >>> # result.transcript == "Hello world"
            >>> # result.is_final == True (because message type is "AddTranscript")
            >>> # result.confidence == 0.95
        """
        metadata = message.get("metadata", {})
        return cls(
            transcript=metadata.get("transcript", ""),
            is_final=message.get("message") == ServerMessageType.ADD_TRANSCRIPT,
            confidence=metadata.get("confidence"),
            start_time=metadata.get("start_time"),
            end_time=metadata.get("end_time"),
            speaker=metadata.get("speaker"),
        )
