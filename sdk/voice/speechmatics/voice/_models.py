#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#


import datetime
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from enum import IntFlag
from enum import auto
from typing import Any
from typing import Optional

from speechmatics.rt import AudioEncoding
from speechmatics.rt import OperatingPoint


class EndOfUtteranceMode(str, Enum):
    """End of turn delay options for transcription."""

    NONE = "none"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


class DiarizationFocusMode(str, Enum):
    """Speaker focus mode for diarization."""

    RETAIN = "retain"
    IGNORE = "ignore"


@dataclass
class AdditionalVocabEntry:
    """Additional vocabulary entry.

    Parameters:
        content: The word to add to the dictionary.
        sounds_like: Similar words to the word.
    """

    content: str
    sounds_like: list[str] = field(default_factory=list)


@dataclass
class DiarizationKnownSpeaker:
    """Known speakers for speaker diarization.

    Parameters:
        label: The label of the speaker.
        speaker_identifiers: One or more data strings for the speaker.
    """

    label: str
    speaker_identifiers: list[str]


@dataclass
class DiarizationSpeakerConfig:
    """Speaker Diarization Config.

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

        focus_mode: Speaker focus mode for diarization. When set to `DiarizationFocusMode.RETAIN`,
            the STT engine will retain words spoken by other speakers (not listed in `ignore_speakers`)
            and process them as passive speaker frames. When set to `DiarizationFocusMode.IGNORE`,
            the STT engine will ignore words spoken by other speakers and they will not be processed.
            Defaults to `DiarizationFocusMode.RETAIN`.
    """

    focus_speakers: list[str] = field(default_factory=list)
    ignore_speakers: list[str] = field(default_factory=list)
    focus_mode: DiarizationFocusMode = DiarizationFocusMode.RETAIN


@dataclass
class VoiceAgentConfig:
    """Voice Agent configuration.

    A framework-independent configuration object for the Speechmatics Voice Agent. This uses
    utility functions to create `TranscriptionConfig` and `AudioConfig` objects and also retain
    agent configuration for the `VoiceAgentClient`.

    Parameters:
        operating_point: Operating point for transcription accuracy vs. latency tradeoff. It is
            recommended to use OperatingPoint.ENHANCED for most use cases. Defaults to
            OperatingPoint.ENHANCED.

        domain: Domain for Speechmatics API. Defaults to None.

        language: Language code for transcription. Defaults to `en`.

        output_locale: Output locale for transcription, e.g. `en-GB`. Defaults to None.

        max_delay: Maximum delay in seconds for transcription. This forces the STT engine to
            speed up the processing of transcribed words and reduces the interval between partial
            and final results. Lower values can have an impact on accuracy. Defaults to 0.7.

        end_of_utterance_silence_trigger: Maximum delay in seconds for end of utterance trigger.
            The delay is used to wait for any further transcribed words before emitting the final
            word frames. The value must be lower than max_delay.
            Defaults to 0.2.

        end_of_utterance_max_delay: Maximum delay in seconds for end of utterance delay.
            The delay is used to wait for any further transcribed words before emitting the final
            word frames. The value must be greater than end_of_utterance_silence_trigger.
            Defaults to 10.0.

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
            Defaults to None.

        enable_diarization: Enable speaker diarization. When enabled, the STT engine will
            determine and attribute words to unique speakers. The speaker_sensitivity
            parameter can be used to adjust the sensitivity of diarization.
            Defaults to False.

        speaker_sensitivity: Diarization sensitivity. A higher value increases the sensitivity
            of diarization and helps when two or more speakers have similar voices.
            Defaults to 0.5.

        max_speakers: Maximum number of speakers to detect. This forces the STT engine to cluster
            words into a fixed number of speakers. It should not be used to limit the number of
            speakers, unless it is clear that there will only be a known number of speakers.
            Defaults to None.

        prefer_current_speaker: Prefer current speaker ID. When set to true, groups of words close
            together are given extra weight to be identified as the same speaker.
            Defaults to False.

        speaker_config: DiarizationSpeakerConfig to configure the speakers to focus on, ignore and
            how to deal with speakers that are not in focus.

        known_speakers: List of known speaker labels and identifiers. If you supply a list of
            labels and identifiers for speakers, then the STT engine will use them to attribute
            any spoken words to that speaker. This is useful when you want to attribute words
            to a specific speaker, such as the assistant or a specific user. Labels and identifiers
            can be obtained from a running STT session and then used in subsequent sessions.
            Identifiers are unique to each Speechmatics account and cannot be used across accounts.
            Refer to our examples on the format of the known_speakers parameter.
            Defaults to [].

        sample_rate: Audio sample rate for streaming. Defaults to 16000.
        audio_encoding: Audio encoding format. Defaults to AudioEncoding.PCM_S16LE.
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
    additional_vocab: list[AdditionalVocabEntry] = field(default_factory=list)
    punctuation_overrides: Optional[dict] = None

    # Diarization
    enable_diarization: bool = False
    speaker_sensitivity: float = 0.5
    max_speakers: Optional[int] = None
    prefer_current_speaker: bool = False
    speaker_config: DiarizationSpeakerConfig = field(default_factory=DiarizationSpeakerConfig)
    known_speakers: list[DiarizationKnownSpeaker] = field(default_factory=list)

    # Audio
    sample_rate: int = 16000
    audio_encoding: AudioEncoding = AudioEncoding.PCM_S16LE


class AgentClientMessageType(str, Enum):
    """Message types that can be sent from client to server.

    These enum values represent the different types of messages that the
    client can send to the Speechmatics RT API during a transcription session.

    Attributes:
        EndOfStream: Signals that no more audio data will be sent.
        GetSpeakers: Internal, Speechmatics only message. Allows the client to request speaker data.

    Examples:
        >>> # Ending the session
        >>> end_message = {
        ...     "message": AgentClientMessageType.END_OF_STREAM,
        ...     "last_seq_no": sequence_number
        ... }
    """

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
        SpeakingStarted: Speech has started.
        SpeakingEnded: Speech has ended.
        EndOfTurn: A turn has been detected (context-based prediction).
        AddSegments: A final segment has been detected.
        AddInterimSegments: An interim segment has been detected.
        SpeakersResult: Speakers result has been detected.
        Metrics: Metrics for the STT engine.
        SpeakerMetrics: Metrics relating to speakers.

    Examples:
        >>> # Register event handlers for different message types
        >>> @client.on(AgentServerMessageType.INTERIM_SEGMENTS)
        >>> def handle_interim(message):
        ...     segments: list[SpeakerSegment] = message['segments']
        ...     print(f"Interim: {segments}")
        >>>
        >>> @client.on(AgentServerMessageType.FINAL_SEGMENTS)
        >>> def handle_final(message):
        ...     segments: list[SpeakerSegment] = message['segments']
        ...     print(f"Final: {segments}")
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

    # VAD messages
    SPEAKING_STARTED = "SpeakingStarted"
    SPEAKING_ENDED = "SpeakingEnded"
    END_OF_TURN = "EndOfTurn"

    # Turn / segment messages
    ADD_SEGMENTS = "AddSegments"
    ADD_INTERIM_SEGMENTS = "AddInterimSegments"

    # Speaker messages
    SPEAKERS_RESULT = "SpeakersResult"

    # Metrics
    METRICS = "Metrics"
    TTFB_METRICS = "TTFBMetrics"
    SPEAKER_METRICS = "SpeakerMetrics"


class AnnotationFlags(IntFlag):
    """Flags to apply when processing speech / objects."""

    # High-level segment updates
    NEW = auto()
    UPDATED_FULL = auto()
    UPDATED_FULL_LCASE = auto()
    UPDATED_STRIPPED = auto()
    UPDATED_STRIPPED_LCASE = auto()
    UPDATED_FINALS = auto()
    UPDATED_PARTIALS = auto()
    UPDATED_SPEAKERS = auto()

    # Content of segments
    ONLY_ACTIVE_SPEAKERS = auto()
    CONTAINS_INACTIVE_SPEAKERS = auto()

    # More granular details on the word content
    HAS_PARTIAL = auto()
    HAS_FINAL = auto()
    STARTS_WITH_FINAL = auto()
    ENDS_WITH_FINAL = auto()
    HAS_EOS = auto()
    ENDS_WITH_EOS = auto()
    HAS_DISFLUENCY = auto()
    STARTS_WITH_DISFLUENCY = auto()
    ENDS_WITH_DISFLUENCY = auto()
    HIGH_DISFLUENCY_COUNT = auto()
    ENDS_WITH_PUNCTUATION = auto()
    VERY_SLOW_SPEAKER = auto()
    SLOW_SPEAKER = auto()
    FAST_SPEAKER = auto()
    ONLY_PUNCTUATION = auto()
    MULTIPLE_SPEAKERS = auto()
    NO_TEXT = auto()

    # End of utterance detection
    END_OF_UTTERANCE = auto()


@dataclass
class AnnotationResult:
    """Processing result."""

    flags: int = 0

    def __init__(self, *flags: AnnotationFlags):
        """Initialize the object.

        Args:
            flags: The initial flags to set.
        """
        self.flags = 0
        for flag in flags:
            self.add(flag)

    def has(self, *flags: AnnotationFlags) -> bool:
        """Check if the object has all given flags."""
        return all(self.flags & flag == flag for flag in flags)

    def any(self, *flags: AnnotationFlags) -> bool:
        """Check if the object has any of the given flags."""
        return any(self.flags & flag == flag for flag in flags)

    def add(self, flag: AnnotationFlags) -> None:
        """Add a flag to the object."""
        self.flags |= flag

    def remove(self, flag: AnnotationFlags) -> None:
        """Remove a flag from the object."""
        self.flags &= ~flag

    def __eq__(self, o: object) -> bool:
        """Check if the object is equal to another."""
        if isinstance(o, AnnotationResult):
            return self.flags == o.flags
        elif isinstance(o, (AnnotationFlags, int)):
            return self.flags == o
        return False

    def __str__(self) -> str:
        """String representation of the flags."""
        flags: list[str] = []
        for flag in AnnotationFlags:
            if self.flags & flag == flag and flag.name is not None:
                flags.append(flag.name)
        return f"{type(self).__name__}({', '.join(flags)})"


@dataclass
class SpeechFragment:
    """Fragment of a speech event.

    As the transcript is processed (partials and finals), a list of SpeechFragments
    objects are accumulated and then used to form SpeechSegments objects.

    Parameters:
        idx: Index of the fragment in the list (used for sorting).
        start_time: Start time of the fragment in seconds (from session start).
        end_time: End time of the fragment in seconds (from session start).
        language: Language of the fragment. Defaults to `en`.
        _type: Type of the fragment. Defaults to `word`.
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
    _type: str = "word"
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


@dataclass
class SpeakerSegment:
    """SpeechFragment items grouped by speaker_id and whether the speaker is active.

    Parameters:
        speaker_id: The ID of the speaker.
        is_active: Whether the speaker is active (emits frame).
        timestamp: The timestamp of the frame.
        language: The language of the frame.
        fragments: The list of SpeechFragment items.
        annotation: The annotation associated with the segment.
    """

    speaker_id: Optional[str] = None
    is_active: bool = False
    timestamp: Optional[str] = None
    language: Optional[str] = None
    fragments: list[SpeechFragment] = field(default_factory=list)
    annotation: AnnotationResult = field(default_factory=AnnotationResult)

    @property
    def start_time(self) -> float:
        """Return the start time of the segment."""
        return self.fragments[0].start_time

    @property
    def end_time(self) -> float:
        """Return the end time of the segment."""
        return self.fragments[-1].end_time

    def __str__(self) -> str:
        """Return a string representation of the object."""
        meta = {
            "speaker_id": self.speaker_id,
            "timestamp": self.timestamp,
            "language": self.language,
            "annotation": str(self.annotation),
            "text": self.format_text(),
        }
        return f"SpeakerSegment({', '.join(f'{k}={v}' for k, v in meta.items())})"

    def format_text(self, format: Optional[str] = None, words_only: bool = False) -> str:
        """Wrap text with speaker ID in an optional f-string format.

        Supported format variables:
            speaker_id: The ID of the speaker.
            text: The text of the fragment.
            ts: The timestamp of the fragment.
            lang: The language of the fragment.

        Args:
            format: Format to wrap the text with.
            words_only: Whether to include only word fragments.

        Returns:
            str: The wrapped text.
        """
        # Cumulative contents
        content = ""

        # Select fragments to include
        if not words_only:
            fragments = self.fragments
        else:
            fragments = [frag for frag in self.fragments if frag._type == "word"]

        # Assemble the text
        for frag in fragments:
            if content == "" or frag.attaches_to == "previous":
                content += frag.content
            else:
                content += " " + frag.content

        # Format the text, if format is provided
        if format is None:
            return content
        return format.format(
            **{
                "speaker_id": self.speaker_id,
                "text": content,
                "ts": self.timestamp,
                "lang": self.language,
            }
        )


@dataclass
class SpeakerSegmentView:
    """View for speaker fragments.

    Parameters:
        fragments: List of fragments.
        base_time: Base time for the fragments.
        focus_speakers: List of speakers to focus on or None.
    """

    fragments: list[SpeechFragment]
    segments: list[SpeakerSegment]

    def __init__(
        self,
        fragments: list[SpeechFragment],
        base_time: datetime.datetime,
        focus_speakers: Optional[list[str]] = None,
        annotate_segments: bool = True,
    ):
        self.fragments = fragments
        self.base_time = base_time
        self.focus_speakers = focus_speakers

        # Process fragments into a list of segments
        self.segments = FragmentUtils.segment_list_from_fragments(
            base_time, fragments, focus_speakers, annotate_segments
        )

    @property
    def start_time(self) -> float:
        return self.fragments[0].start_time

    @property
    def end_time(self) -> float:
        return self.fragments[-1].end_time

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

    def format_text(
        self,
        format: str = "|{speaker_id}|{text}|",
        separator: str = "",
        words_only: bool = False,
    ) -> str:
        return separator.join(segment.format_text(format, words_only) for segment in self.segments)

    def trim(self, start_time: float, end_time: float, annotate_segments: bool = True) -> None:
        self.fragments = [
            frag for frag in self.fragments if frag.start_time >= start_time and frag.end_time <= end_time
        ]
        self.segments = FragmentUtils.segment_list_from_fragments(
            self.base_time, self.fragments, focus_speakers=self.focus_speakers, annotate_segments=annotate_segments
        )


@dataclass
class SpeakerVADStatus:
    """Emitted when a speaker starts or ends speaking.

    The speaker id is taken from the last word in the segment when
    the event is emitted.

    Parameters:
        is_active: Whether the speaker is active.
        speaker_id: The ID of the speaker.
    """

    is_active: bool
    speaker_id: Optional[str] = None


class FragmentUtils:
    """Set of utility functions for working with SpeechFragment and SpeakerSegment objects."""

    @staticmethod
    def segment_list_from_fragments(
        base_time: datetime.datetime,
        fragments: list[SpeechFragment],
        focus_speakers: Optional[list[str]] = None,
        annotate_segments: bool = True,
    ) -> list[SpeakerSegment]:
        """Create SpeakerSegment objects from a list of SpeechFragment objects.

        Args:
            base_time: Base time for the fragments.
            fragments: List of SpeechFragment objects.
            focus_speakers: List of speakers to focus on or None.
            annotate_segments: Whether to annotate segments.

        Returns:
            List of SpeakerSegment objects.
        """
        # Speaker groups
        current_speaker: Optional[str] = None
        speaker_groups: list[list[SpeechFragment]] = [[]]

        # Group by speakers
        for frag in fragments:
            if frag.speaker != current_speaker:
                current_speaker = frag.speaker
                if speaker_groups[-1]:
                    speaker_groups.append([])
            speaker_groups[-1].append(frag)

        # Create SpeakerFragments objects
        segments: list[SpeakerSegment] = []
        for group in speaker_groups:
            sd = FragmentUtils.segment_from_fragments(
                base_time, group, focus_speakers=focus_speakers, annotate=annotate_segments
            )
            if sd:
                segments.append(sd)

        # Return the grouped SpeakerFragments objects
        return segments

    @staticmethod
    def segment_from_fragments(
        base_time: datetime.datetime,
        fragments: list[SpeechFragment],
        focus_speakers: Optional[list[str]] = None,
        annotate: bool = True,
    ) -> Optional[SpeakerSegment]:
        """Take a group of fragments and piece together into SpeakerSegment.

        Each fragment for a given speaker is assembled into a string,
        taking into consideration whether words are attached to the
        previous or next word (notably punctuation). This ensures that
        the text does not have extra spaces. This will also check for
        any straggling punctuation from earlier utterances that should
        be removed.

        Args:
            base_time: The base time for the segment.
            fragments: List of SpeechFragment objects.
            focus_speakers: List of speakers to focus on.
            annotate: Whether to annotate the segment.

        Returns:
            SpeakerSegment: The object for the group.
        """
        # Check for starting fragments that are attached to previous
        if fragments and fragments[0].attaches_to == "previous":
            fragments = fragments[1:]

        # Check for trailing fragments that are attached to next
        if fragments and fragments[-1].attaches_to == "next":
            fragments = fragments[:-1]

        # Check there are results
        if not fragments:
            return None

        # Get the timing extremes
        start_time = min(frag.start_time for frag in fragments)

        # Timestamp
        ts = (base_time + datetime.timedelta(seconds=start_time)).isoformat(timespec="milliseconds")

        # Determine if the speaker is considered active
        is_active = True
        if focus_speakers:
            is_active = fragments[0].speaker in focus_speakers

        # New SpeakerSegment
        segment = SpeakerSegment(
            speaker_id=fragments[0].speaker,
            timestamp=ts,
            language=fragments[0].language,
            fragments=fragments,
            is_active=is_active,
        )

        # Annotate
        if annotate:
            segment.annotation = FragmentUtils._annotate_segment(segment)

        # Return the SpeakerSegment object
        return segment

    @staticmethod
    def _annotate_segment(segment: SpeakerSegment) -> AnnotationResult:
        """Annotate the segment.

        This will annotate the segment with any additional information.
        """
        # Annotation result
        result = AnnotationResult()

        # References
        segment_length: int = len(segment.fragments)
        first_fragment: SpeechFragment = segment.fragments[0]
        last_fragment: SpeechFragment = segment.fragments[-1]
        penultimate_fragment: Optional[SpeechFragment] = segment.fragments[-2] if segment_length > 1 else None

        # Count of words
        words = [frag for frag in segment.fragments if frag._type == "word"]
        word_count = len(words)
        if word_count == 0:
            result.add(AnnotationFlags.NO_TEXT)

        # Only punctuation
        if all(frag.is_punctuation for frag in segment.fragments):
            result.add(AnnotationFlags.ONLY_PUNCTUATION)

        # Partials and finals
        if any(not frag.is_final for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_PARTIAL)

        # Finals
        if any(frag.is_final for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_FINAL)
        if first_fragment.is_final:
            result.add(AnnotationFlags.STARTS_WITH_FINAL)
        if last_fragment.is_final:
            result.add(AnnotationFlags.ENDS_WITH_FINAL)

        # End of sentence
        if last_fragment.is_eos:
            result.add(AnnotationFlags.ENDS_WITH_EOS)

        # Punctuation
        if last_fragment.is_punctuation:
            result.add(AnnotationFlags.ENDS_WITH_PUNCTUATION)

        # Disfluency
        if any(frag.is_disfluency for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_DISFLUENCY)
        if first_fragment.is_disfluency:
            result.add(AnnotationFlags.STARTS_WITH_DISFLUENCY)
        if last_fragment.is_disfluency:
            result.add(AnnotationFlags.ENDS_WITH_DISFLUENCY)
        if (
            penultimate_fragment
            and result.any(AnnotationFlags.ENDS_WITH_EOS, AnnotationFlags.ENDS_WITH_PUNCTUATION)
            and penultimate_fragment.is_disfluency
        ):
            result.add(AnnotationFlags.ENDS_WITH_DISFLUENCY)

        # Rate of speech
        if len(words) > 1:
            # Calculate the approximate words-per-minute (for last 5 words)
            last_5_words = words[-5:]
            wpm = len(last_5_words) / ((last_5_words[-1].end_time - last_5_words[0].start_time) / 60.0)

            # Categorize the speaker
            if wpm < 100:
                result.add(AnnotationFlags.VERY_SLOW_SPEAKER)
            elif wpm < 200:
                result.add(AnnotationFlags.SLOW_SPEAKER)
            elif wpm > 350:
                result.add(AnnotationFlags.FAST_SPEAKER)

        # Return the annotation result
        return result

    @staticmethod
    def compare_views(view1: SpeakerSegmentView, view2: Optional[SpeakerSegmentView]) -> AnnotationResult:
        """Compare two SpeakerSegmentView objects and return the differences.

        Args:
            view1: The first SpeakerSegmentView object to compare.
            view2: The second SpeakerSegmentView object to compare to or None.

        Returns:
            AnnotationResult: The annotation result.
        """
        # Result
        result = AnnotationResult()

        # If we have a previous view, compare it
        if view2 and view2.segment_count > 0:
            # Compare full string
            view1_full_str: str = view1.format_text()
            view2_full_str: str = view2.format_text()
            if view1_full_str != view2_full_str:
                result.add(AnnotationFlags.UPDATED_FULL)
            if view1_full_str.lower() != view2_full_str.lower():
                result.add(AnnotationFlags.UPDATED_FULL_LCASE)

            # Stripped string (without punctuation)
            view1_stripped_str: str = view1.format_text(words_only=True)
            view2_stripped_str: str = view2.format_text(words_only=True)
            if view1_stripped_str != view2_stripped_str:
                result.add(AnnotationFlags.UPDATED_STRIPPED)
            if view1_stripped_str.lower() != view2_stripped_str.lower():
                result.add(AnnotationFlags.UPDATED_STRIPPED_LCASE)

            # Partials, finals and speakers
            if view1.final_count != view2.final_count:
                result.add(AnnotationFlags.UPDATED_FINALS)
            if view1.partial_count != view2.partial_count:
                result.add(AnnotationFlags.UPDATED_PARTIALS)
            if view1.segment_count != view2.segment_count:
                result.add(AnnotationFlags.UPDATED_SPEAKERS)

        # Assume this is new
        elif view1.segment_count > 0:
            result.add(AnnotationFlags.NEW)

        # TODO - contents of LAST segment?

        # Return the result
        return result
