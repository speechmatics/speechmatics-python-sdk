#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import Field

from speechmatics.rt import AudioEncoding
from speechmatics.rt import OperatingPoint
from speechmatics.rt import SpeakerIdentifier

# ==============================================================================
# ENUMS
# ==============================================================================


class EndOfUtteranceMode(str, Enum):
    """End of turn delay options for transcription.

    - `EXTERNAL`: External end of turn detection. The engine will not perform any
        end of turn detection and will use an external trigger via `finalize()`.

    - `FIXED`: Fixed end of turn delay. The STT engine will use silence detection
        to determine the end of turn. For slow speakers, this may result in
        sentences being split up into smaller segments.

    - `ADAPTIVE`: Adaptive end of turn delay. The STT engine will use silence detection
        to determine the end of turn. The delay is adaptive and will be adjusted
        based on the content of what the most recent speaker has said, such as
        rate of speech and whether they have any pauses or disfluencies.

    - `SMART_TURN`: Smart turn end of turn delay. The STT engine will use a combination
        of silence detection, adaptive delay and smart turn detection using machine learning
        to determine the end of turn.

    Examples:
        Using fixed mode (default):
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     end_of_utterance_mode=EndOfUtteranceMode.FIXED
            ... )

        Using adaptive mode for natural conversations:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE
            ... )

        Using smart turn detection:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     end_of_utterance_mode=EndOfUtteranceMode.SMART_TURN,
            ... )

        External control (manual finalization):
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL
            ... )
            >>> # Later in code:
            >>> client.finalize()
    """

    EXTERNAL = "external"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    SMART_TURN = "smart_turn"


class TranscriptionUpdatePreset(str, Enum):
    """Filter options for when to emit changes to transcription.

    - `COMPLETE`: Emit complete transcription.
    - `COMPLETE_PLUS_TIMING`: Emit complete transcription with timing changes.
    - `WORDS`: Emit when word context has changed.
    - `WORDS_PLUS_TIMING`: Emit when word context or timing has changed.
    - `TIMING`: Emit when timing has changed.
    """

    COMPLETE = "complete"
    COMPLETE_PLUS_TIMING = "complete_plus_timing"
    WORDS = "words"
    WORDS_PLUS_TIMING = "words_plus_timing"
    TIMING = "timing"


class SpeakerFocusMode(str, Enum):
    """Speaker focus mode for diarization.

    - `RETAIN`: Retain words spoken by other speakers (not listed in `ignore_speakers`)
        and process them as passive speaker frames.
    - `IGNORE`: Ignore words spoken by other speakers and they will not be processed.

    Examples:
        Retain all speakers but mark focus:
            >>> config = SpeakerFocusConfig(
            ...     focus_speakers=["S1"],
            ...     focus_mode=SpeakerFocusMode.RETAIN
            ... )

        Ignore non-focus speakers completely:
            >>> config = SpeakerFocusConfig(
            ...     focus_speakers=["S1", "S2"],
            ...     focus_mode=SpeakerFocusMode.IGNORE
            ... )
    """

    RETAIN = "retain"
    IGNORE = "ignore"


class AgentClientMessageType(str, Enum):
    """Message types that can be sent from client to server.

    These enum values represent the different types of messages that the
    client can send to the Speechmatics RT API during a transcription session.

    Attributes:
        FinalizeTurn: Force the finalization of the current turn.
        EndOfStream: Signals that no more audio data will be sent.
        GetSpeakers: Internal, Speechmatics only message. Allows the client to request speaker data.

    Examples:
        >>> # Finalizing the current turn
        >>> finalize_turn_message = {
        ...     "message": AgentClientMessageType.FINALIZE_TURN
        ... }
        >>> await client.send_message(finalize_turn_message)
        >>>
        >>> # Ending the session
        >>> end_message = {
        ...     "message": AgentClientMessageType.END_OF_STREAM,
        ...     "last_seq_no": sequence_number
        ... }
        >>> await client.send_message(end_message)
    """

    FINALIZE_TURN = "Finalize"
    END_OF_STREAM = "EndOfStream"
    GET_SPEAKERS = "GetSpeakers"


class AgentServerMessageType(str, Enum):
    """Message types that can be received from the server / agent.

    These enum values represent the different types of messages that the
    Speechmatics RT API / Voice Agent SDK can send to the client.

    Attributes:
        RecognitionStarted: The recognition session has started.
        EndOfTranscript: The recognition session has ended.
        Info: Informational message.
        Warning: Warning message.
        Error: Error message.
        AddPartialTranscript: Partial transcript has been added.
        AddTranscript: Transcript has been added.
        EndOfUtterance: End of utterance has been detected (from STT engine).
        SpeakerStarted: Speech has started.
        SpeakerEnded: Speech has ended.
        AddPartialSegment: A partial / interim segment has been detected.
        AddSegment: A final segment has been detected.
        StartOfTurn: Start of turn has been detected.
        EndOfTurnPrediction: End of turn prediction timing.
        EndOfTurn: End of turn has been detected.
        SpeakersResult: Speakers result has been detected.
        Metrics: Metrics for the STT engine.
        SpeakerMetrics: Metrics relating to speakers.

    Examples:
        >>> # Register event handlers for different message types
        >>> @client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT)
        >>> def handle_interim(message):
        ...     segments: list[SpeakerSegment] = message['segments']
        ...     print(f"Interim: {segments}")
        >>>
        >>> @client.on(AgentServerMessageType.ADD_SEGMENT)
        >>> def handle_final(message):
        ...     segments: list[SpeakerSegment] = message['segments']
        ...     print(f"Final: {segments}")
        >>>
        >>> @client.on(AgentServerMessageType.END_OF_TURN)
        >>> def handle_end_of_turn(message):
        ...     print(f"End of turn")
        >>>
        >>> @client.on(AgentServerMessageType.ERROR)
        >>> def handle_error(message):
        ...     print(f"Error: {message['reason']}")
    """

    # API messages
    RECOGNITION_STARTED = "RecognitionStarted"
    END_OF_TRANSCRIPT = "EndOfTranscript"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"

    # Raw transcription messages
    ADD_PARTIAL_TRANSCRIPT = "AddPartialTranscript"
    ADD_TRANSCRIPT = "AddTranscript"
    END_OF_UTTERANCE = "EndOfUtterance"

    # VAD messages
    SPEAKER_STARTED = "SpeakerStarted"
    SPEAKER_ENDED = "SpeakerEnded"

    # Segment messages
    ADD_PARTIAL_SEGMENT = "AddPartialSegment"
    ADD_SEGMENT = "AddSegment"

    # End of turn messages
    START_OF_TURN = "StartOfTurn"
    END_OF_TURN_PREDICTION = "EndOfTurnPrediction"
    END_OF_TURN = "EndOfTurn"

    # Speaker messages
    SPEAKERS_RESULT = "SpeakersResult"

    # Metrics
    METRICS = "Metrics"
    TTFB_METRICS = "TTFBMetrics"
    SPEAKER_METRICS = "SpeakerMetrics"


class AnnotationFlags(str, Enum):
    """Flags to apply when processing speech / objects."""

    # High-level segment updates
    NEW = "new"
    UPDATED_FULL = "updated_full"
    UPDATED_FULL_LCASE = "updated_full_lcase"
    UPDATED_STRIPPED = "updated_stripped"
    UPDATED_STRIPPED_LCASE = "updated_stripped_lcase"
    UPDATED_FINALS = "updated_finals"
    UPDATED_PARTIALS = "updated_partials"
    UPDATED_SPEAKERS = "updated_speakers"
    UPDATED_WORD_TIMINGS = "updated_word_timings"
    FINALIZED = "finalized"

    # Content of segments
    ONLY_ACTIVE_SPEAKERS = "only_active_speakers"
    CONTAINS_INACTIVE_SPEAKERS = "contains_inactive_speakers"

    # More granular details on the word content
    HAS_PARTIAL = "has_partial"
    HAS_FINAL = "has_final"
    STARTS_WITH_FINAL = "starts_with_final"
    ENDS_WITH_FINAL = "ends_with_final"
    HAS_EOS = "has_eos"
    ENDS_WITH_EOS = "ends_with_eos"
    HAS_DISFLUENCY = "has_disfluency"
    STARTS_WITH_DISFLUENCY = "starts_with_disfluency"
    ENDS_WITH_DISFLUENCY = "ends_with_disfluency"
    HIGH_DISFLUENCY_COUNT = "high_disfluency_count"
    ENDS_WITH_PUNCTUATION = "ends_with_punctuation"
    VERY_SLOW_SPEAKER = "very_slow_speaker"
    SLOW_SPEAKER = "slow_speaker"
    FAST_SPEAKER = "fast_speaker"
    ONLY_PUNCTUATION = "only_punctuation"
    MULTIPLE_SPEAKERS = "multiple_speakers"
    NO_TEXT = "no_text"

    # End of utterance detection
    END_OF_UTTERANCE = "end_of_utterance"


# ==============================================================================
# CONFIGURATION MODELS
# ==============================================================================


class AdditionalVocabEntry(BaseModel):
    """Additional vocabulary entry.

    Parameters:
        content: The word to add to the dictionary.
        sounds_like: Similar words to the word.

    Examples:
        Adding a brand name:
            >>> vocab = AdditionalVocabEntry(
            ...     content="Speechmatics",
            ...     sounds_like=["speech mattics", "speech matics"]
            ... )

        Adding technical terms:
            >>> vocab_list = [
            ...     AdditionalVocabEntry(content="API", sounds_like=["A P I"]),
            ...     AdditionalVocabEntry(content="WebSocket", sounds_like=["web socket"])
            ... ]
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     additional_vocab=vocab_list
            ... )
    """

    content: str
    sounds_like: list[str] = Field(default_factory=list)


class SpeakerFocusConfig(BaseModel):
    """Speaker Focus Config.

    List of speakers to focus on, ignore and how to deal with speakers that are not
    in focus. These settings can be changed during a session. Other changes may require
    a new session.

    Parameters:
        focus_speakers: List of speaker IDs to focus on. When enabled, only these speakers are
            emitted as finalized frames and other speakers are considered passive. Words from
            other speakers are still processed, but only emitted when a focussed speaker has
            also said new words. A list of labels (e.g. `S1`, `S2`) or identifiers of known
            speakers (e.g. `speaker_1`, `speaker_2`) can be used.
            Defaults to [].

        ignore_speakers: List of speaker IDs to ignore. When enabled, these speakers are
            excluded from the transcription and their words are not processed. Their speech
            will not trigger any VAD or end of utterance detection. By default, any speaker
            with a label starting and ending with double underscores will be excluded (e.g.
            `__ASSISTANT__`).
            Defaults to [].

        focus_mode: Speaker focus mode for diarization. When set to `SpeakerFocusMode.RETAIN`,
            the STT engine will retain words spoken by other speakers (not listed in `ignore_speakers`)
            and process them as passive speaker frames. When set to `SpeakerFocusMode.IGNORE`,
            the STT engine will ignore words spoken by other speakers and they will not be processed.
            Defaults to `SpeakerFocusMode.RETAIN`.
    """

    focus_speakers: list[str] = Field(default_factory=list)
    ignore_speakers: list[str] = Field(default_factory=list)
    focus_mode: SpeakerFocusMode = SpeakerFocusMode.RETAIN


class SpeechSegmentEmitMode(str, Enum):
    """EMode for when to emit finalized segments.

    As transcription is processed, segments are emitted based on the selected emit mode. This gives
    the client more control in how to process incomplete and complete segments of speech.

    - `ON_SPEAKER_ENDED`: Emit segments when a speaker has ended. If a speaker change is detected
        during a turn, then multiple finalized segments may be emitted in sequence.

    - `ON_FINALIZED_SENTENCE`: Emit segments when a sentence has ended. A finalized segment is emitted
        as soon as a finalized end of sentence is detected. If a speaker continues to speak during
        a turn, then multiple finalized segments may be emitted during the turn.

    - `ON_END_OF_TURN`: No finalized segments will be emitted until the turn has been completed.
    """

    ON_SPEAKER_ENDED = "on_speaker_ended"
    ON_FINALIZED_SENTENCE = "on_finalized_sentence"
    ON_END_OF_TURN = "on_end_of_turn"


class SpeechSegmentConfig(BaseModel):
    """Configuration on how segments are emitted.

    Parameters:
        add_trailing_eos: Add trailing end of sentence to segments. When enabled, segments are
            emitted with missing trailing end of sentence added. Defaults to False.

        emit_mode: How to emit segments. Defaults to `SpeechSegmentEmitMode.ON_SPEAKER_ENDED`.
    """

    add_trailing_eos: bool = False
    emit_mode: SpeechSegmentEmitMode = SpeechSegmentEmitMode.ON_SPEAKER_ENDED


class SmartTurnConfig(BaseModel):
    """Smart turn configuration for the Speechmatics Voice Agent.

    This configuration is used to determine when a turn has completed. It is used to
    extract slices of recent audio for post-processing by end of thought models.

    Parameters:
        audio_buffer_length: Length of audio buffer to extract slices of recent audio for post-processing
            by end of thought models. Defaults to 0.0 seconds.

        smart_turn_threshold: Smart turn threshold. This is used to determine when a turn has completed.
            Only used when `end_of_utterance_mode` is `EndOfUtteranceMode.SMART_TURN`. Defaults to 0.75.

        slice_margin: Margin to add to the audio buffer to ensure that the end of thought models have
            enough audio to work with. Defaults to 0.05 seconds.

    Examples:
        >>> config = SmartTurnConfig(
        ...     audio_buffer_length=0.5,
        ...     smart_turn_threshold=0.75,
        ...     slice_margin=0.05
        ... )
    """

    audio_buffer_length: float = 0.0
    smart_turn_threshold: float = 0.75
    slice_margin: float = 0.05


class VoiceAgentConfig(BaseModel):
    """Voice Agent configuration.

    A framework-independent configuration object for the Speechmatics Voice Agent. This uses
    utility functions to create `TranscriptionConfig` and `AudioConfig` objects and also retain
    agent configuration for the `VoiceAgentClient`.

    Parameters:
        operating_point: Operating point for transcription accuracy vs. latency tradeoff. It is
            recommended to use `OperatingPoint.ENHANCED` for most use cases. Defaults to
            `OperatingPoint.ENHANCED`.

        domain: Domain for Speechmatics API. Defaults to `None`.

        language: Language code for transcription. Defaults to `en`.

        output_locale: Output locale for transcription, e.g. `en-GB`. Defaults to `None`.

        max_delay: Maximum delay in seconds for transcription. This forces the STT engine to
            speed up the processing of transcribed words and reduces the interval between partial
            and final results. Lower values can have an impact on accuracy. Defaults to `0.7`.

        end_of_utterance_silence_trigger: Maximum delay in seconds for end of utterance trigger.
            The delay is used to wait for any further transcribed words before emitting the final
            word frames. The value must be lower than max_delay.
            Defaults to `0.2`.

        end_of_utterance_max_delay: Maximum delay in seconds for end of utterance delay.
            The delay is used to wait for any further transcribed words before emitting the final
            word frames. The value must be greater than end_of_utterance_silence_trigger.
            Defaults to `10.0`.

        end_of_utterance_mode: End of utterance delay mode. When ADAPTIVE is used, the delay
            can be adjusted on the content of what the most recent speaker has said, such as
            rate of speech and whether they have any pauses or disfluencies. When FIXED is used,
            the delay is fixed to the value of `end_of_utterance_delay`. Use of NONE disables
            end of utterance detection and uses a fallback timer.
            Defaults to `EndOfUtteranceMode.FIXED`.

        additional_vocab: List of additional vocabulary entries. If you supply a list of
            additional vocabulary entries, the this will increase the weight of the words in the
            vocabulary and help the STT engine to better transcribe the words.
            Defaults to [].

        punctuation_overrides: Punctuation overrides. This allows you to override the punctuation
            in the STT engine. This is useful for languages that use different punctuation
            than English. See documentation for more information.
            Defaults to `None`.

        enable_diarization: Enable speaker diarization. When enabled, the STT engine will
            determine and attribute words to unique speakers. The speaker_sensitivity
            parameter can be used to adjust the sensitivity of diarization.
            Defaults to `False`.

        speaker_sensitivity: Diarization sensitivity. A higher value increases the sensitivity
            of diarization and helps when two or more speakers have similar voices.
            Defaults to `0.5`.

        max_speakers: Maximum number of speakers to detect. This forces the STT engine to cluster
            words into a fixed number of speakers. It should not be used to limit the number of
            speakers, unless it is clear that there will only be a known number of speakers.
            Defaults to `None`.

        prefer_current_speaker: Prefer current speaker ID. When set to true, groups of words close
            together are given extra weight to be identified as the same speaker.
            Defaults to False.

        speaker_config: SpeakerFocusConfig to configure the speakers to focus on, ignore and
            how to deal with speakers that are not in focus.

        known_speakers: List of known speaker labels and identifiers. If you supply a list of
            labels and identifiers for speakers, then the STT engine will use them to attribute
            any spoken words to that speaker. This is useful when you want to attribute words
            to a specific speaker, such as the assistant or a specific user. Labels and identifiers
            can be obtained from a running STT session and then used in subsequent sessions.
            Identifiers are unique to each Speechmatics account and cannot be used across accounts.
            Refer to our examples on the format of the known_speakers parameter.
            Defaults to [].

        include_results: Include word data in the response. This is useful for debugging and
            understanding the STT engine's behavior. Defaults to False.

        enable_preview_features: Enable preview features using a preview endpoint provided by
            Speechmatics. Defaults to False.

        transcription_update_preset: Emit segments when the text content or word timings change.
            Options are: `COMPLETE` (emit on changes to text content), `COMPLETE_PLUS_TIMING`
            (emit on changes to text content and word timings), `WORDS` (emit on changes to word
            content, without punctuation), `WORDS_PLUS_TIMING` (emit on changes to word content
            and word timings), and `TIMING` (emit on changes to word timings, not recommended).
            Defaults to `TranscriptionUpdatePreset.COMPLETE`.

        smart_turn_config: Smart turn configuration for the Speechmatics Voice Agent.
        speech_segment_config: Speech segment configuration for the Speechmatics Voice Agent.

        sample_rate: Audio sample rate for streaming. Defaults to `16000`.
        audio_encoding: Audio encoding format. Defaults to `AudioEncoding.PCM_S16LE`.

    Examples:
        Basic configuration:
            >>> config = VoiceAgentConfig(language="en")

        With diarization enabled:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     enable_diarization=True,
            ...     speaker_sensitivity=0.7
            ... )

        With custom vocabulary:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     additional_vocab=[
            ...         AdditionalVocabEntry(
            ...             content="Speechmatics",
            ...             sounds_like=["speech mattics"]
            ...         )
            ...     ]
            ... )

        Advanced configuration with speaker focus:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     enable_diarization=True,
            ...     speaker_config=SpeakerFocusConfig(
            ...         focus_speakers=["S1"],
            ...         focus_mode=SpeakerFocusMode.RETAIN
            ...     ),
            ...     end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE
            ... )

        With known speakers:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     enable_diarization=True,
            ...     known_speakers=[
            ...         SpeakerIdentifier(
            ...             label="Alice",
            ...             speaker_identifiers=["speaker_abc123"]
            ...         )
            ...     ]
            ... )

        Complete example with multiple features:
            >>> config = VoiceAgentConfig(
            ...     language="en",
            ...     operating_point=OperatingPoint.ENHANCED,
            ...     enable_diarization=True,
            ...     speaker_sensitivity=0.7,
            ...     max_speakers=3,
            ...     end_of_utterance_mode=EndOfUtteranceMode.SMART_TURN,
            ...     smart_turn_config=SmartTurnConfig(
            ...         smart_turn_threshold=0.8
            ...     ),
            ...     additional_vocab=[
            ...         AdditionalVocabEntry(content="API"),
            ...         AdditionalVocabEntry(content="WebSocket")
            ...     ],
            ...     speaker_config=SpeakerFocusConfig(
            ...         focus_speakers=["S1", "S2"]
            ...     )
            ... )
    """

    # Service configuration
    operating_point: OperatingPoint = OperatingPoint.ENHANCED
    domain: Optional[str] = None
    language: str = "en"
    output_locale: Optional[str] = None

    # Features
    max_delay: float = 0.7
    end_of_utterance_silence_trigger: float = 0.2
    end_of_utterance_max_delay: float = 10.0
    end_of_utterance_mode: EndOfUtteranceMode = EndOfUtteranceMode.FIXED
    additional_vocab: list[AdditionalVocabEntry] = Field(default_factory=list)
    punctuation_overrides: Optional[dict] = None

    # Diarization
    enable_diarization: bool = False
    speaker_sensitivity: float = 0.5
    max_speakers: Optional[int] = None
    prefer_current_speaker: bool = False
    speaker_config: SpeakerFocusConfig = Field(default_factory=SpeakerFocusConfig)
    known_speakers: list[SpeakerIdentifier] = Field(default_factory=list)

    # Advanced features
    include_results: bool = False
    enable_preview_features: bool = False
    transcription_update_preset: TranscriptionUpdatePreset = TranscriptionUpdatePreset.COMPLETE
    smart_turn_config: SmartTurnConfig = Field(default_factory=SmartTurnConfig)
    speech_segment_config: SpeechSegmentConfig = Field(default_factory=SpeechSegmentConfig)

    # Audio
    sample_rate: int = 16000
    audio_encoding: AudioEncoding = AudioEncoding.PCM_S16LE


# ==============================================================================
# SESSION & INFO MODELS
# ==============================================================================


class LanguagePackInfo(BaseModel):
    """Information about the language pack used in a session.

    Attributes:
        adapted (bool): Whether the language pack is adapted.
        itn (bool): Whether the language pack has ITN enabled.
        language_description (str): The language description.
        word_delimiter (str): The word delimiter.
        writing_direction (str): The writing direction ('ltr' or 'rtl').
    """

    adapted: bool = False
    itn: bool = True
    language_description: str = "English"
    word_delimiter: str = " "
    writing_direction: str = "ltr"


class ClientSessionInfo(BaseModel):
    """Information about the session.

    Attributes:
        config (VoiceAgentConfig): The configuration for the session.
        session_id (str): The session ID.
        base_time (datetime.datetime): The base time for the session.
        language_pack_info (LanguagePackInfo): The language pack info for the session.
    """

    config: VoiceAgentConfig
    session_id: str
    base_time: datetime.datetime
    language_pack_info: LanguagePackInfo


class SessionSpeaker(BaseModel):
    """Info on a speaker in a session.

    Attributes:
        speaker_id (str): The speaker ID.
        word_count (int): The word count for the speaker.
        last_heard (float): The last time the speaker was heard.
    """

    speaker_id: str
    word_count: int = 0
    last_heard: float = 0


class AnnotationResult(list):
    """Processing result."""

    @staticmethod
    def from_flags(*flags: AnnotationFlags) -> AnnotationResult:
        """Create an AnnotationResult from a list of flags."""
        r = AnnotationResult()
        r.add(*flags)
        return r

    def add(self, *flags: AnnotationFlags) -> None:
        """Add a flag(s) to the object."""
        for flag in flags:
            if flag not in self:
                self.append(flag.value)

    def remove(self, *flags: AnnotationFlags) -> None:
        """Remove a flag(s) from the object."""
        for flag in flags:
            if flag in self:
                super().remove(flag.value)

    def has(self, *flags: AnnotationFlags) -> bool:
        """Check if the object has all given flags."""
        return all(f.value in set(self) for f in flags)

    def any(self, *flags: AnnotationFlags) -> bool:
        """Check if the object has any of the given flags."""
        return any(f.value in set(self) for f in flags)

    def __eq__(self, other: object) -> bool:
        """Check if the object is equal to another."""
        if isinstance(other, AnnotationResult):
            return set(self) == set(other)
        return False


# ==============================================================================
# FRAGMENT & SEGMENT MODELS
# ==============================================================================


class SpeechFragment(BaseModel):
    """Fragment of a speech event.

    As the transcript is processed (partials and finals), a list of SpeechFragments
    objects are accumulated and then used to form SpeechSegments objects.

    Parameters:
        idx: Index of the fragment in the list (used for sorting).
        start_time: Start time of the fragment in seconds (from session start).
        end_time: End time of the fragment in seconds (from session start).
        language: Language of the fragment. Defaults to `en`.
        direction: Direction of the fragment. Defaults to `ltr`.
        type_: Type of the fragment. Defaults to `word`.
        is_eos: Whether the fragment is the end of a sentence. Defaults to `False`.
        is_final: Whether the fragment is the final fragment. Defaults to `False`.
        is_disfluency: Whether the fragment is a disfluency. Defaults to `False`.
        is_punctuation: Whether the fragment is a punctuation. Defaults to `False`.
        attaches_to: Whether the fragment attaches to the previous or next fragment (punctuation). Defaults to empty string.
        content: Content of the fragment. Defaults to empty string.
        speaker: Speaker of the fragment (if diarization is enabled). Defaults to `None`.
        confidence: Confidence of the fragment (0.0 to 1.0). Defaults to `1.0`.
        result: Raw result of the fragment from the TTS.
        annotation: Annotation for the fragment.
    """

    idx: int
    start_time: float
    end_time: float
    language: str = "en"
    direction: str = "ltr"
    type_: str = "word"
    is_eos: bool = False
    is_final: bool = False
    is_disfluency: bool = False
    is_punctuation: bool = False
    attaches_to: str = ""
    content: str = ""
    speaker: Optional[str] = None
    confidence: float = 1.0
    result: Optional[Any] = None
    annotation: Optional[AnnotationResult] = None

    model_config = {"arbitrary_types_allowed": True}


class SpeakerSegment(BaseModel):
    """SpeechFragment items grouped by speaker_id and whether the speaker is active.

    Parameters:
        speaker_id: The ID of the speaker.
        is_active: Whether the speaker is active (emits frame).
        timestamp: The timestamp of the frame.
        language: The language of the frame.
        fragments: The list of SpeechFragment items.
        text: The text of the segment.
        annotation: The annotation associated with the segment.
    """

    speaker_id: Optional[str] = None
    is_active: bool = False
    timestamp: Optional[str] = None
    language: Optional[str] = None
    fragments: list[SpeechFragment] = Field(default_factory=list)
    text: Optional[str] = None
    annotation: AnnotationResult = Field(default_factory=AnnotationResult)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def start_time(self) -> float:
        """Return the start time of the segment."""
        return self.fragments[0].start_time if self.fragments else 0.0

    @property
    def end_time(self) -> float:
        """Return the end time of the segment."""
        return self.fragments[-1].end_time if self.fragments else 0.0

    def model_dump(self, include_results: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to control fragments/results inclusion."""

        # Always exclude fragments from the base dump
        kwargs["exclude"] = {"fragments"}
        data: dict[str, Any] = super().model_dump(**kwargs)

        # Add timing information
        data["start_time"] = self.start_time
        data["end_time"] = self.end_time

        # Add results if requested
        if include_results:
            data["results"] = [f.result for f in self.fragments]

        # Return the dump
        return data


class SpeakerSegmentView(BaseModel):
    """View for speaker fragments.

    Parameters:
        session: ClientSessionInfo object.
        fragments: List of fragments.
        focus_speakers: List of speakers to focus on or None.
    """

    session: ClientSessionInfo
    fragments: list[SpeechFragment]
    segments: list[SpeakerSegment] = Field(default_factory=list)
    focus_speakers: Optional[list[str]] = None

    def __init__(
        self,
        session: ClientSessionInfo,
        fragments: list[SpeechFragment],
        focus_speakers: Optional[list[str]] = None,
        annotate_segments: bool = True,
        **data: Any,
    ) -> None:
        # Lazy import to avoid circular dependency
        from ._utils import FragmentUtils

        # Process fragments into a list of segments
        segments = FragmentUtils.segment_list_from_fragments(
            session=session,
            fragments=fragments,
            focus_speakers=focus_speakers,
            annotate_segments=annotate_segments,
        )

        super().__init__(session=session, fragments=fragments, segments=segments, focus_speakers=focus_speakers, **data)

    @property
    def start_time(self) -> float:
        return self.fragments[0].start_time if self.fragments else 0.0

    @property
    def end_time(self) -> float:
        return self.fragments[-1].end_time if self.fragments else 0.0

    @property
    def final_count(self) -> int:
        return sum(1 for frag in self.fragments if frag.is_final)

    @property
    def partial_count(self) -> int:
        return sum(1 for frag in self.fragments if not frag.is_final)

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def last_active_segment_index(self) -> int:
        idx = next(
            (i for i, segment in enumerate(reversed(self.segments)) if segment.is_active),
            None,
        )
        if idx is None:
            return -1
        return len(self.segments) - idx - 1

    def format_view_text(
        self,
        format: str = "|{speaker_id}|{text}|",
        separator: str = "",
        words_only: bool = False,
    ) -> str:
        """Format each segment into a single string.

        Args:
            format: Format string.
            separator: Separator string.
            words_only: Whether to include only word fragments.

        Returns:
            str: The formatted text.
        """
        # Lazy import to avoid circular dependency
        from ._utils import FragmentUtils

        return separator.join(
            FragmentUtils.format_segment_text(
                session=self.session,
                segment=segment,
                format=format,
                words_only=words_only,
            )
            for segment in self.segments
        )

    def trim(self, start_time: float, end_time: float, annotate_segments: bool = True) -> None:
        """Trim a segment view to a specific time range.

        Args:
            start_time: Start time in seconds.
            end_time: End time in seconds.
            annotate_segments: Whether to annotate segments.
        """
        # Lazy import to avoid circular dependency
        from ._utils import FragmentUtils

        self.fragments = [
            frag for frag in self.fragments if frag.start_time >= start_time and frag.end_time <= end_time
        ]
        self.segments = FragmentUtils.segment_list_from_fragments(
            session=self.session,
            fragments=self.fragments,
            focus_speakers=self.focus_speakers,
            annotate_segments=annotate_segments,
        )


class SpeakerVADStatus(BaseModel):
    """Emitted when a speaker starts or ends speaking.

    The speaker id is taken from the last word in the segment when
    the event is emitted.

    Parameters:
        is_active: Whether the speaker is active.
        speaker_id: The ID of the speaker.
        time: The time of the event (start for STARTED, end for ENDED).
    """

    is_active: bool
    speaker_id: Optional[str] = None
    time: Optional[float] = None
