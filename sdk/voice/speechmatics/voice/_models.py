#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any
from typing import Literal
from typing import Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

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


class MaxDelayMode(str, Enum):
    """Max delay mode options for transcription."""

    FIXED = "fixed"
    FLEXIBLE = "flexible"


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


class AgentServerMessageType(str, Enum):
    """Message types that can be received from the server / agent.

    These enum values represent the different types of messages that the
    Speechmatics RT API / Voice Agent SDK can send to the client.

    Attributes:
        RecognitionStarted: Server response to 'StartRecognition',
            acknowledging that a recognition session has started.
        EndOfTranscript: Indicates the server has finished sending all messages.
        Info: Informational messages from the server.
        Warning: Warning messages that don't stop transcription.
        Error: Error messages indicating transcription failure.
        AudioAdded: Server response to 'AddAudio', indicating
            that audio has been added successfully.
        Diagnostics: Diagnostic messages for development and troubleshooting.
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
        SmartTurn: Smart turn metadata.
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
    AUDIO_ADDED = "AudioAdded"
    DIAGNOSTICS = "Diagnostics"

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

    # Turn messages
    VAD_STATUS = "VadStatus"
    START_OF_TURN = "StartOfTurn"
    END_OF_TURN_PREDICTION = "EndOfTurnPrediction"
    END_OF_TURN = "EndOfTurn"
    SMART_TURN_RESULT = "SmartTurnResult"

    # Speaker messages
    SPEAKERS_RESULT = "SpeakersResult"

    # Metrics
    SESSION_METRICS = "SessionMetrics"
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
    UPDATED_WORD_TIMINGS = "updated_word_timings"
    FINALIZED = "finalized"

    # Annotations changed
    UPDATED_ANNOTATIONS = "updated_annotations"

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
    HAS_PAUSE = "has_pause"
    ENDS_WITH_PAUSE = "ends_with_pause"

    # End of utterance detection
    END_OF_UTTERANCE = "end_of_utterance"

    # VAD
    VAD_ACTIVE = "vad_active"
    VAD_INACTIVE = "vad_inactive"
    VAD_STARTED = "vad_started"
    VAD_STOPPED = "vad_stopped"

    # Smart Turn
    SMART_TURN_ACTIVE = "smart_turn_active"
    SMART_TURN_INACTIVE = "smart_turn_inactive"
    SMART_TURN_TRUE = "smart_turn_true"
    SMART_TURN_FALSE = "smart_turn_false"


# ==============================================================================
# CONFIGURATION MODELS
# ==============================================================================


class BaseModel(PydanticBaseModel):
    """Base configuration model."""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_dict(cls, data: dict, **kwargs: Any) -> Self:
        """Convert a dictionary to a config object."""
        return cls.model_validate(data, **kwargs)  # type: ignore[no-any-return]

    def to_dict(
        self, exclude_none: bool = True, exclude_defaults: bool = False, exclude_unset: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        """Convert the model to a dictionary."""
        return super().model_dump(  # type: ignore[no-any-return]
            mode="json",
            exclude_none=exclude_none,
            exclude_defaults=exclude_defaults,
            exclude_unset=exclude_unset,
            **kwargs,
        )

    @classmethod
    def from_json(cls, json_data: str, **kwargs: Any) -> Self:
        """Convert a JSON string to a config object."""
        return cls.model_validate_json(json_data, **kwargs)  # type: ignore[no-any-return]

    def to_json(
        self, exclude_none: bool = True, exclude_defaults: bool = False, exclude_unset: bool = False, **kwargs: Any
    ) -> str:
        """Convert the model to a JSON string."""
        return self.model_dump_json(  # type: ignore[no-any-return]
            exclude_none=exclude_none, exclude_defaults=exclude_defaults, exclude_unset=exclude_unset, **kwargs
        )


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
    sounds_like: Optional[list[str]] = None


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


class SpeechSegmentConfig(BaseModel):
    """Configuration on how segments are emitted.

    Parameters:
        add_trailing_eos: Add trailing end of sentence to segments. When enabled, segments are
            emitted with missing trailing end of sentence added. Defaults to False.

        emit_sentences: Emit segments when a sentence has ended. A finalized segment is emitted
            as soon as a finalized end of sentence is detected. If a speaker continues to speak during
            a turn, then multiple finalized segments may be emitted during the turn.

        pause_mark: Add pause mark to segments. When set, a pause fragment will be added to the segment
            when a pause is detected using the string provided. For example, `...` would add this text
            into the formatted output for a segment as `Hello ... how are you?`.
            Defaults to None.
    """

    add_trailing_eos: bool = False
    emit_sentences: bool = True
    pause_mark: Optional[str] = None


class EndOfTurnPenaltyItem(BaseModel):
    """End of turn penalty item.

    Parameters:
        penalty: Penalty value.
        annotation: List of annotations to apply the penalty to.
        is_not: Whether the penalty should be applied when the annotation is not present.
    """

    penalty: float
    annotation: list[AnnotationFlags]
    is_not: bool = False


class EndOfTurnConfig(BaseModel):
    """Configuration for end of turn.

    Parameters:
        base_multiplier: Base multiplier for end of turn delay.
        min_end_of_turn_delay: Minimum end of turn delay.
        penalties: List of end of turn penalty items.
        use_forced_eou: Whether to use forced end of utterance detection.
    """

    base_multiplier: float = 1.0
    min_end_of_turn_delay: float = 0.01
    penalties: list[EndOfTurnPenaltyItem] = Field(
        default_factory=lambda: [
            # Increase delay
            EndOfTurnPenaltyItem(penalty=3.0, annotation=[AnnotationFlags.VERY_SLOW_SPEAKER]),
            EndOfTurnPenaltyItem(penalty=2.0, annotation=[AnnotationFlags.SLOW_SPEAKER]),
            EndOfTurnPenaltyItem(penalty=2.5, annotation=[AnnotationFlags.ENDS_WITH_DISFLUENCY]),
            EndOfTurnPenaltyItem(penalty=1.1, annotation=[AnnotationFlags.HAS_DISFLUENCY]),
            EndOfTurnPenaltyItem(
                penalty=2.0,
                annotation=[AnnotationFlags.ENDS_WITH_EOS],
                is_not=True,
            ),
            # Decrease delay
            EndOfTurnPenaltyItem(
                penalty=0.5, annotation=[AnnotationFlags.ENDS_WITH_FINAL, AnnotationFlags.ENDS_WITH_EOS]
            ),
            # Smart Turn + VAD
            EndOfTurnPenaltyItem(penalty=0.2, annotation=[AnnotationFlags.SMART_TURN_TRUE]),
            EndOfTurnPenaltyItem(
                penalty=0.2, annotation=[AnnotationFlags.VAD_STOPPED, AnnotationFlags.SMART_TURN_INACTIVE]
            ),
        ]
    )
    use_forced_eou: bool = False


class VoiceActivityConfig(BaseModel):
    """Configuration for voice activity detection.

    Parameters:
        enabled: Whether voice activity detection is enabled.
        silence_duration: Duration of silence in seconds before considering speech ended.
        threshold: Threshold for voice activity detection.
    """

    enabled: bool = False
    silence_duration: float = 0.18
    threshold: float = 0.35


class SmartTurnConfig(BaseModel):
    """Smart turn configuration for the Speechmatics Voice Agent.

    This configuration is used to determine when a turn has completed. It is used to
    extract slices of recent audio for post-processing by end of thought models.

    Parameters:
        enabled: Whether smart turn is enabled.
        smart_turn_threshold: Smart turn threshold. Defaults to 0.5.
        max_audio_length: Maximum length of audio to analyze in seconds. Defaults to 8.0.

    Examples:
        >>> config = SmartTurnConfig(
        ...     audio_buffer_length=15.0,
        ...     smart_turn_threshold=0.5,
        ...     slice_margin=0.05
        ... )
    """

    enabled: bool = False
    smart_turn_threshold: float = 0.5
    max_audio_length: float = 8.0


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

        enable_entities: Enable entity detection. When enabled, the STT engine will
            detect and attribute words to entities. This is useful for languages that use
            different entities than English. See documentation for more information.
            Defaults to `False`.

        max_delay_mode: Determines whether the threshold specified in max_delay can be exceeded
            if a potential entity is detected. Flexible means if a potential entity
            is detected, then the max_delay can be overriden until the end of that
            entity. Fixed means that max_delay specified ignores any potential
            entity that would not be completed within that threshold.
            Defaults to `MaxDelayMode.FLEXIBLE`.

        include_partials: Include partial segment fragments (words) in the output of
            AddPartialSegment messages. Partial fragments from the STT will always be used for
            speaker activity detection. If `include_results` is enabled, then partials will
            always be included in the segment fragment list. This setting is used only for
            the formatted text output of individual segments.
            Defaults to `True`.

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

        transcription_update_preset: Emit segments when the text content or word timings change.
            Options are: `COMPLETE` (emit on changes to text content), `COMPLETE_PLUS_TIMING`
            (emit on changes to text content and word timings), `WORDS` (emit on changes to word
            content, without punctuation), `WORDS_PLUS_TIMING` (emit on changes to word content
            and word timings), and `TIMING` (emit on changes to word timings, not recommended).
            Defaults to `TranscriptionUpdatePreset.COMPLETE`.

        end_of_turn_config: End of turn configuration for the Speechmatics Voice Agent.

        vad_config: Voice activity detection configuration for the Speechmatics Voice Agent.

        smart_turn_config: Smart turn configuration for the Speechmatics Voice Agent.

        speech_segment_config: Speech segment configuration for the Speechmatics Voice Agent.

        audio_buffer_length: Length of internal rolling audio buffer in seconds. Defaults to `0.0`.

        advanced_engine_control: Internal use only.

        sample_rate: Audio sample rate for streaming. Defaults to `16000`.
        audio_encoding: Audio encoding format. Defaults to `AudioEncoding.PCM_S16LE`.
        chunk_size: Audio chunk size in frames. Defaults to `160`.

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
            ...     end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            ...     smart_turn_config=SmartTurnConfig(
            ...         enabled=True
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
    max_delay: float = 1.0
    end_of_utterance_silence_trigger: float = 0.5
    end_of_utterance_max_delay: float = 10.0
    end_of_utterance_mode: EndOfUtteranceMode = EndOfUtteranceMode.FIXED
    additional_vocab: list[AdditionalVocabEntry] = Field(default_factory=list)
    punctuation_overrides: Optional[dict] = None
    enable_entities: bool = False
    max_delay_mode: MaxDelayMode = MaxDelayMode.FLEXIBLE
    include_partials: bool = True

    # Diarization
    enable_diarization: bool = False
    speaker_sensitivity: float = 0.5
    max_speakers: Optional[int] = None
    prefer_current_speaker: bool = False
    speaker_config: SpeakerFocusConfig = Field(default_factory=SpeakerFocusConfig)
    known_speakers: list[SpeakerIdentifier] = Field(default_factory=list)

    # Advanced features
    include_results: bool = False
    transcription_update_preset: TranscriptionUpdatePreset = TranscriptionUpdatePreset.COMPLETE
    end_of_turn_config: EndOfTurnConfig = Field(default_factory=EndOfTurnConfig)
    vad_config: Optional[VoiceActivityConfig] = None
    smart_turn_config: Optional[SmartTurnConfig] = None
    speech_segment_config: SpeechSegmentConfig = Field(default_factory=SpeechSegmentConfig)
    audio_buffer_length: float = 0.0

    # Advanced engine configuration
    advanced_engine_control: Optional[dict[str, Any]] = None

    # Audio
    sample_rate: int = 16000
    audio_encoding: AudioEncoding = AudioEncoding.PCM_S16LE
    chunk_size: int = 160

    # Validation
    @model_validator(mode="after")  # type: ignore[misc]
    def validate_config(self) -> Self:
        """Validate the configuration."""

        # Validation errors
        errors: list[str] = []

        # End of utterance mode cannot be EXTERNAL if smart turn is enabled
        if self.end_of_utterance_mode == EndOfUtteranceMode.EXTERNAL and self.smart_turn_config:
            errors.append("EXTERNAL mode cannot be used in conjunction with SmartTurnConfig")

        # Cannot have FIXED and forced end of utterance enabled without VAD being enabled
        if (self.end_of_utterance_mode == EndOfUtteranceMode.FIXED and self.end_of_turn_config.use_forced_eou) and not (
            self.vad_config and self.vad_config.enabled
        ):
            errors.append("FIXED mode cannot be used in conjunction with forced end of utterance without VAD enabled")

        # Cannot use VAD with external end of utterance mode
        if self.end_of_utterance_mode == EndOfUtteranceMode.EXTERNAL and (self.vad_config and self.vad_config.enabled):
            errors.append("EXTERNAL mode cannot be used in conjunction with VAD being enabled")

        # Check end_of_utterance_max_delay is greater than end_of_utterance_silence_trigger
        if self.end_of_utterance_max_delay < self.end_of_utterance_silence_trigger:
            errors.append("end_of_utterance_max_delay must be greater than end_of_utterance_silence_trigger")

        # If diarization is not enabled, then max_speakers cannot be set
        if not self.enable_diarization and self.max_speakers:
            errors.append("max_speakers cannot be set when enable_diarization is False")

        # If diarization is not enabled, then SpeakerFocusConfig.focus_speakers and SpeakerFocusConfig.ignore_speakers must be empty
        if not self.enable_diarization and (self.speaker_config.focus_speakers or self.speaker_config.ignore_speakers):
            errors.append(
                "SpeakerFocusConfig.focus_speakers and SpeakerFocusConfig.ignore_speakers must be empty when enable_diarization is False"
            )

        # Check sample rate
        if self.sample_rate not in [8000, 16000]:
            errors.append("sample_rate must be 8000 or 16000")

        # Raise error if any validation errors
        if errors:
            raise ValueError(f"{len(errors)} config error(s): {'; '.join(errors)}")

        # Return validated config
        return self


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
        volume (Optional[float]): The average volume of the speaker (mean of last 50 values).
    """

    speaker_id: str
    word_count: int = 0
    last_heard: float = 0
    volume: Optional[float] = None
    final_word_count: int = Field(default=0, exclude=True)
    volume_history: list[float] = Field(default_factory=list, exclude=True)

    def update_volume(self, new_volume: float) -> None:
        """Update volume with average from last N values.

        Args:
            new_volume: The new volume value to add.
        """
        # Track volume history (last N values)
        self.volume_history.append(new_volume)
        while len(self.volume_history) > 10:
            self.volume_history.pop(0)

        # Calculate average from history
        self.volume = round(sum(self.volume_history) / len(self.volume_history), 1)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SessionSpeaker):
            return False
        return (
            self.speaker_id == other.speaker_id
            and self.word_count == other.word_count
            and self.last_heard == other.last_heard
            and self.volume == other.volume
        )


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
        volume: Volume of the fragment (0.0 to 100.0). Defaults to `None`.
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
    volume: Optional[float] = None
    result: Optional[Any] = None
    annotation: Optional[AnnotationResult] = None

    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


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
        is_eou: Whether the fragment is the end of an utterance. Defaults to `False`.
    """

    speaker_id: Optional[str] = None
    is_active: bool = False
    timestamp: Optional[str] = None
    language: Optional[str] = None
    fragments: list[SpeechFragment] = Field(default_factory=list)
    text: Optional[str] = None
    annotation: AnnotationResult = Field(default_factory=AnnotationResult)
    is_eou: bool = False

    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)

    @property
    def start_time(self) -> float:
        """Return the start time of the segment."""
        return self.fragments[0].start_time if self.fragments else 0.0

    @property
    def end_time(self) -> float:
        """Return the end time of the segment."""
        return self.fragments[-1].end_time if self.fragments else 0.0

    def to_dict(
        self,
        exclude_none: bool = True,
        exclude_defaults: bool = False,
        exclude_unset: bool = False,
        include_results: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Override model_dump to control fragments/results inclusion."""

        # Always exclude fragments from the base dump
        exclude = kwargs.get("exclude", set())
        if isinstance(exclude, set):
            exclude.add("fragments")
        else:
            exclude = {"fragments"}
        kwargs["exclude"] = exclude

        # Get the base dump
        data: dict[str, Any] = super().model_dump(
            exclude_none=exclude_none, exclude_defaults=exclude_defaults, exclude_unset=exclude_unset, **kwargs
        )

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

        # Initialize with the computed values
        data.update(
            {
                "session": session,
                "fragments": fragments,
                "segments": segments,
                "focus_speakers": focus_speakers,
            }
        )
        super().__init__(**data)

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

    def has_no_active_segments_remaining(self) -> bool:
        return self.last_active_segment_index == -1

    def format_view_text(
        self,
        format: str = "|{speaker_id}|{text}|",
        separator: str = "",
        words_only: bool = False,
        include_partials: bool = True,
    ) -> str:
        """Format each segment into a single string.

        Args:
            format: Format string.
            separator: Separator string.
            words_only: Whether to include only word fragments.
            include_partials: Whether to include partial fragments in the output.

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
                include_partials=include_partials,
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


# ==============================================================================
# MESSAGES / PAYLOADS
# ==============================================================================


class BaseMessage(BaseModel):
    """Base model for all messages."""

    message: str

    @classmethod
    def from_message(cls, data: dict, **kwargs: Any) -> Self:
        """Convert a message dictionary to a message object.

        Alias for from_dict() for semantic clarity when working with messages.
        """
        return cls.from_dict(data, **kwargs)


class MessageTimeMetadata(BaseModel):
    """Metadata for segment messages.

    Parameters:
        time: The time of the event.
        start_time: The start time of the segment.
        end_time: The end time of the segment.
        processing_time: The processing time of the segment.
    """

    time: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    processing_time: Optional[float] = None


class ErrorMessage(BaseMessage):
    """Emitted when an error occurs.

    Parameters:
        message: The message type.
        reason: The reason for the error.
    """

    message: AgentServerMessageType = AgentServerMessageType.ERROR
    reason: str


class SessionMetricsMessage(BaseMessage):
    """Emitted when metrics are calculated.

    Parameters:
        message: The message type.
        total_time: The total time in seconds.
        total_time_str: The total time in HH:MM:SS format.
        total_bytes: The total bytes sent to the STT engine.
        processing_time: The latest processing time in seconds.
    """

    message: AgentServerMessageType = AgentServerMessageType.SESSION_METRICS
    total_time: float
    total_time_str: str
    total_bytes: int
    processing_time: float


class SpeakerStatusMessage(BaseMessage):
    """Emitted when a speaker starts or ends speaking.

    The speaker id is taken from the last word in the segment when
    the event is emitted.

    Parameters:
        message: The message type.
        is_active: Whether the speaker is active.
        speaker_id: The ID of the speaker.
        time: The time of the event (start for STARTED, end for ENDED).
    """

    message: Literal[AgentServerMessageType.SPEAKER_STARTED, AgentServerMessageType.SPEAKER_ENDED]
    is_active: bool
    speaker_id: Optional[str] = None
    time: Optional[float] = None


class VADStatusMessage(BaseMessage):
    """Emitted when voice activity detection status changes.

    Parameters:
        message: The message type.
        is_speech: Whether speech is detected.
        probability: The probability of speech.
        transition_duration_ms: The duration of the transition in milliseconds.
        metadata: The time metadata.
    """

    message: AgentServerMessageType = AgentServerMessageType.VAD_STATUS
    metadata: MessageTimeMetadata
    is_speech: bool
    probability: float
    transition_duration_ms: float


class TurnStartEndResetMessage(BaseMessage):
    """Emitted when a turn starts, ends or is reset.

    Parameters:
        turn_id: The ID of the turn.
        is_active: Whether the turn is active.
    """

    message: Literal[
        AgentServerMessageType.START_OF_TURN,
        AgentServerMessageType.END_OF_TURN,
    ]
    turn_id: int
    metadata: MessageTimeMetadata


class TurnPredictionMetadata(BaseModel):
    """Metadata for turn prediction messages.

    Parameters:
        ttl: The time to live of the prediction in seconds.
    """

    ttl: float
    reasons: list[str] = Field(default_factory=list, exclude=False)

    model_config = ConfigDict(extra="ignore")


class TurnPredictionMessage(BaseMessage):
    """Emitted when a turn prediction is made."""

    message: AgentServerMessageType = AgentServerMessageType.END_OF_TURN_PREDICTION
    turn_id: int
    metadata: TurnPredictionMetadata


class SpeakerMetricsMessage(BaseMessage):
    """Emitted when the speaker metrics are updated.

    Parameters:
        speakers: List of speakers.
    """

    message: AgentServerMessageType = AgentServerMessageType.SPEAKER_METRICS
    speakers: list[SessionSpeaker]


class SegmentMessageSegmentFragment(BaseModel):
    """Speech fragment for segment messages.

    Parameters:
        start_time: The start time of the fragment.
        end_time: The end time of the fragment.
        language: The language of the fragment.
        direction: The direction of the fragment.
        type_: The type of the fragment.
        content: The content of the fragment.
        attaches_to: The ID of the fragment that this fragment attaches to.
    """

    start_time: float
    end_time: float
    language: str = "en"
    direction: str = "ltr"
    type: str = Field(default="word", alias="type_")
    content: str = ""
    attaches_to: str = ""
    is_eos: bool = False

    model_config = ConfigDict(extra="ignore")


class SegmentMessageSegment(BaseModel):
    """Partial or final segment.

    Parameters:
        speaker_id: The ID of the speaker.
        is_active: Whether the speaker is active (emits frame).
        timestamp: The timestamp of the frame.
        language: The language of the frame.
        text: The text of the segment.
        fragments: The fragments associated with the segment.
        annotation: The annotation associated with the segment (optional).
        is_eou: Whether the segment is an end of utterance.
        metadata: The metadata associated with the segment.
    """

    speaker_id: Optional[str] = None
    is_active: bool = False
    timestamp: Optional[str] = None
    language: Optional[str] = None
    text: Optional[str] = None
    fragments: Optional[list[SegmentMessageSegmentFragment]] = None
    annotation: list[AnnotationFlags] = Field(default_factory=list, exclude=False)
    is_eou: bool = False
    metadata: MessageTimeMetadata

    model_config = ConfigDict(extra="ignore")


class SegmentMessage(BaseMessage):
    """Emitted when a segment is added to the session."""

    message: Literal[AgentServerMessageType.ADD_PARTIAL_SEGMENT, AgentServerMessageType.ADD_SEGMENT]
    segments: list[SegmentMessageSegment]
    metadata: MessageTimeMetadata
