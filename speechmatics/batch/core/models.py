"""
Models for the Speechmatics Batch SDK.

This module contains all data models, enums, and configuration classes used
throughout the Speechmatics Batch Speech Recognition SDK. These models
provide type-safe interfaces for configuration, job management, and
result handling based on the official Speechmatics API schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class JobType(str, Enum):
    """Job type enumeration."""

    TRANSCRIPTION = "transcription"
    ALIGNMENT = "alignment"


class JobStatus(str, Enum):
    """
    Status values for batch transcription jobs.

    These enum values represent the different states a job can be in
    during the batch transcription workflow.
    """

    RUNNING = "running"
    DONE = "done"
    REJECTED = "rejected"
    DELETED = "deleted"
    EXPIRED = "expired"


class OperatingPoint(str, Enum):
    """Operating point options for transcription."""

    ENHANCED = "enhanced"
    STANDARD = "standard"


class NotificationContents(str, Enum):
    """Notification content options."""

    SUMMARY = "summary"
    DETAILED = "detailed"


@dataclass
class TranscriptionConfig:
    """
    Configuration for transcription behavior and features.

    Attributes:
        language: ISO 639-1 language code (e.g., "en", "es", "fr").
        operating_point: Which acoustic model to use.
        output_locale: RFC-5646 language code for transcript output.
        diarization: Type of diarization to use. Options: "none", "speaker".
        additional_vocab: Additional vocabulary for better recognition.
        punctuation_overrides: Custom punctuation configuration.
        domain: Domain-specific language pack.
        enable_entities: Whether to enable entity detection.
        speaker_diarization_config: Configuration for speaker diarization.
        channel_diarization_labels: Labels for channel diarization.
        enable_partials: Enable partial transcript results.
        max_delay: Maximum delay for transcript delivery.
        max_delay_mode: Mode for handling max delay.
    """

    language: str | None = None
    operating_point: OperatingPoint | None = None
    output_locale: str | None = None
    diarization: str | None = None
    additional_vocab: list[dict[str, Any]] | None = None
    punctuation_overrides: dict[str, Any] | None = None
    domain: str | None = None
    enable_entities: bool | None = None
    speaker_diarization_config: dict[str, Any] | None = None
    channel_diarization_labels: list[str] | None = None
    enable_partials: bool | None = None
    max_delay: float | None = None
    max_delay_mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AlignmentConfig:
    """Configuration for alignment jobs."""

    language: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class NotificationConfig:
    """Configuration for job completion notifications."""

    url: str
    contents: NotificationContents | None = None
    auth_headers: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class TrackingConfig:
    """Configuration for job tracking metadata."""

    title: str | None = None
    reference: str | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class TranslationConfig:
    """Configuration for translation features."""

    target_languages: list[str]
    enable_partials: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LanguageIdentificationConfig:
    """Configuration for language identification."""

    expected_languages: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SummarizationConfig:
    """Configuration for summarization features."""

    content_type: str | None = None
    summary_length: str | None = None
    summary_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SentimentAnalysisConfig:
    """Configuration for sentiment analysis."""

    enable_sentiment: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TopicDetectionConfig:
    """Configuration for topic detection."""

    topics: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AutoChaptersConfig:
    """Configuration for automatic chapter generation."""

    enable_chapters: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AudioEventsConfig:
    """Configuration for audio event detection."""

    types: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class JobConfig:
    """
    Complete configuration for batch transcription jobs.

    This class defines the comprehensive job configuration including all
    available features and settings supported by the Speechmatics API.

    Attributes:
        type: Type of job (transcription or alignment).
        transcription_config: Configuration for transcription behavior.
        alignment_config: Configuration for alignment jobs.
        notification_config: Webhook notification configuration.
        tracking: Job tracking metadata.
        translation_config: Translation configuration.
        language_identification_config: Language identification settings.
        summarization_config: Summarization settings.
        sentiment_analysis_config: Sentiment analysis settings.
        topic_detection_config: Topic detection settings.
        auto_chapters_config: Auto chapters settings.
        audio_events_config: Audio events detection settings.
    """

    type: JobType
    transcription_config: TranscriptionConfig | None = None
    alignment_config: AlignmentConfig | None = None
    notification_config: NotificationConfig | None = None
    tracking: TrackingConfig | None = None
    translation_config: TranslationConfig | None = None
    language_identification_config: LanguageIdentificationConfig | None = None
    summarization_config: SummarizationConfig | None = None
    sentiment_analysis_config: SentimentAnalysisConfig | None = None
    topic_detection_config: TopicDetectionConfig | None = None
    auto_chapters_config: AutoChaptersConfig | None = None
    audio_events_config: AudioEventsConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert job config to dictionary for API submission."""
        config: dict[str, Any] = {"type": self.type.value}

        if self.transcription_config:
            config["transcription_config"] = self.transcription_config.to_dict()
        if self.alignment_config:
            config["alignment_config"] = self.alignment_config.to_dict()
        if self.notification_config:
            config["notification_config"] = self.notification_config.to_dict()
        if self.tracking:
            config["tracking"] = self.tracking.to_dict()
        if self.translation_config:
            config["translation_config"] = self.translation_config.to_dict()
        if self.language_identification_config:
            config["language_identification_config"] = self.language_identification_config.to_dict()
        if self.summarization_config:
            config["summarization_config"] = self.summarization_config.to_dict()
        if self.sentiment_analysis_config:
            config["sentiment_analysis_config"] = self.sentiment_analysis_config.to_dict()
        if self.topic_detection_config:
            config["topic_detection_config"] = self.topic_detection_config.to_dict()
        if self.auto_chapters_config:
            config["auto_chapters_config"] = self.auto_chapters_config.to_dict()
        if self.audio_events_config:
            config["audio_events_config"] = self.audio_events_config.to_dict()

        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobConfig:
        """Create JobConfig from dictionary."""
        job_type = JobType(data["type"])

        transcription_config = None
        if "transcription_config" in data:
            tc_data = data["transcription_config"]
            transcription_config = TranscriptionConfig(**tc_data)

        alignment_config = None
        if "alignment_config" in data:
            ac_data = data["alignment_config"]
            alignment_config = AlignmentConfig(**ac_data)

        notification_config = None
        if "notification_config" in data:
            nc_data = data["notification_config"]
            notification_config = NotificationConfig(**nc_data)

        tracking = None
        if "tracking" in data:
            tracking_data = data["tracking"]
            tracking = TrackingConfig(**tracking_data)

        translation_config = None
        if "translation_config" in data:
            tr_data = data["translation_config"]
            translation_config = TranslationConfig(**tr_data)

        language_identification_config = None
        if "language_identification_config" in data:
            li_data = data["language_identification_config"]
            language_identification_config = LanguageIdentificationConfig(**li_data)

        summarization_config = None
        if "summarization_config" in data:
            sum_data = data["summarization_config"]
            summarization_config = SummarizationConfig(**sum_data)

        sentiment_analysis_config = None
        if "sentiment_analysis_config" in data:
            sa_data = data["sentiment_analysis_config"]
            sentiment_analysis_config = SentimentAnalysisConfig(**sa_data)

        topic_detection_config = None
        if "topic_detection_config" in data:
            td_data = data["topic_detection_config"]
            topic_detection_config = TopicDetectionConfig(**td_data)

        auto_chapters_config = None
        if "auto_chapters_config" in data:
            ac_data = data["auto_chapters_config"]
            auto_chapters_config = AutoChaptersConfig(**ac_data)

        audio_events_config = None
        if "audio_events_config" in data:
            ae_data = data["audio_events_config"]
            audio_events_config = AudioEventsConfig(**ae_data)

        return cls(
            type=job_type,
            transcription_config=transcription_config,
            alignment_config=alignment_config,
            notification_config=notification_config,
            tracking=tracking,
            translation_config=translation_config,
            language_identification_config=language_identification_config,
            summarization_config=summarization_config,
            sentiment_analysis_config=sentiment_analysis_config,
            topic_detection_config=topic_detection_config,
            auto_chapters_config=auto_chapters_config,
            audio_events_config=audio_events_config,
        )


@dataclass
class JobError:
    """Represents a job processing error."""

    type: str
    message: str
    details: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobError:
        """Create JobError from dictionary."""
        return cls(type=data["type"], message=data["message"], details=data.get("details"))


@dataclass
class JobInfo:
    """
    Job information as it appears in transcript responses.

    This class represents the job metadata included in transcript
    responses, which has a different structure than JobDetails.

    Attributes:
        id: Unique job identifier.
        created_at: Job creation timestamp in UTC.
        data_name: Original filename of the submitted audio file.
        duration: Duration of the audio file in seconds.
        text_name: Name of the text file (if applicable).
        tracking: Tracking metadata with title, reference, tags, and details.
    """

    id: str
    created_at: str
    data_name: str
    duration: float | None = None
    text_name: str | None = None
    tracking: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobInfo:
        """Create JobInfo from API response dictionary."""
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            data_name=data["data_name"],
            duration=data.get("duration"),
            text_name=data.get("text_name"),
            tracking=data.get("tracking"),
        )


@dataclass
class JobDetails:
    """
    Complete information about a batch transcription job.

    This class represents the full job state and metadata as returned
    by the Speechmatics API, including timestamps, configuration, and
    error information.

    Attributes:
        id: Unique job identifier.
        status: Current job status.
        created_at: Job creation timestamp in UTC.
        data_name: Original filename of the submitted audio file.
        duration: Duration of the audio file in seconds.
        config: Complete job configuration used.
        errors: List of errors encountered during job processing.
    """

    id: str
    status: JobStatus
    created_at: str
    data_name: str
    duration: float | None = None
    config: JobConfig | None = None
    errors: list[JobError] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobDetails:
        """Create JobDetails from API response dictionary."""
        config = None
        if "config" in data and data["config"]:
            config = JobConfig.from_dict(data["config"])

        errors = None
        if "errors" in data and data["errors"]:
            errors = [JobError.from_dict(error) for error in data["errors"]]

        return cls(
            id=data["id"],
            status=JobStatus(data["status"]),
            created_at=data["created_at"],
            data_name=data["data_name"],
            duration=data.get("duration"),
            config=config,
            errors=errors,
        )


@dataclass
class RecognitionMetadata:
    """
    Metadata about the recognition process.

    This class contains comprehensive metadata returned with transcript
    responses, including configuration, errors, and processing information.

    Attributes:
        created_at: Creation timestamp in UTC.
        type: Type of processing (e.g., "alignment", "transcription").
        transcription_config: Configuration used for transcription.
        orchestrator_version: Version of the orchestrator service.
        translation_errors: List of translation processing errors.
        summarization_errors: List of summarization processing errors.
        sentiment_analysis_errors: List of sentiment analysis errors.
        topic_detection_errors: List of topic detection errors.
        auto_chapters_errors: List of auto chapters processing errors.
        alignment_config: Configuration used for alignment.
        output_config: Output formatting configuration.
        language_pack_info: Information about the language pack used.
        language_identification: Language identification results.
    """

    created_at: str
    type: str
    transcription_config: dict[str, Any] | None = None
    orchestrator_version: str | None = None
    translation_errors: list[dict[str, Any]] | None = None
    summarization_errors: list[dict[str, Any]] | None = None
    sentiment_analysis_errors: list[dict[str, Any]] | None = None
    topic_detection_errors: list[dict[str, Any]] | None = None
    auto_chapters_errors: list[dict[str, Any]] | None = None
    alignment_config: dict[str, Any] | None = None
    output_config: dict[str, Any] | None = None
    language_pack_info: dict[str, Any] | None = None
    language_identification: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecognitionMetadata:
        """Create RecognitionMetadata from dictionary."""
        return cls(
            created_at=data["created_at"],
            type=data["type"],
            transcription_config=data.get("transcription_config"),
            orchestrator_version=data.get("orchestrator_version"),
            translation_errors=data.get("translation_errors"),
            summarization_errors=data.get("summarization_errors"),
            sentiment_analysis_errors=data.get("sentiment_analysis_errors"),
            topic_detection_errors=data.get("topic_detection_errors"),
            auto_chapters_errors=data.get("auto_chapters_errors"),
            alignment_config=data.get("alignment_config"),
            output_config=data.get("output_config"),
            language_pack_info=data.get("language_pack_info"),
            language_identification=data.get("language_identification"),
        )


@dataclass
class Alternative:
    """Alternative transcription result."""

    content: str
    confidence: float | None = None
    language: str | None = None
    speaker: str | None = None
    words: list[dict[str, Any]] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alternative:
        """Create Alternative from dictionary."""
        return cls(
            content=data["content"],
            confidence=data.get("confidence"),
            language=data.get("language"),
            speaker=data.get("speaker"),
            words=data.get("words"),
        )


@dataclass
class RecognitionResult:
    """Individual recognition result with alternatives."""

    type: str
    start_time: float | None = None
    end_time: float | None = None
    channel: str | None = None
    alternatives: list[Alternative] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecognitionResult:
        """Create RecognitionResult from dictionary."""
        alternatives = None
        if "alternatives" in data and data["alternatives"]:
            alternatives = [Alternative.from_dict(alt) for alt in data["alternatives"]]

        return cls(
            type=data["type"],
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            channel=data.get("channel"),
            alternatives=alternatives,
        )


@dataclass
class Transcript:
    """
    Complete transcript result from a batch transcription job.

    This class represents the full transcript response including all
    metadata, recognition results, and optional analysis features.

    Attributes:
        format: Speechmatics JSON transcript format version.
        job: Job information and metadata.
        metadata: Recognition process metadata.
        results: List of recognition results with timing and alternatives.
        translations: Optional translations by language code.
        summary: Optional transcript summarization.
        sentiment_analysis: Optional sentiment analysis results.
        topics: Optional topic detection results.
        chapters: Optional auto-generated chapters.
        audio_events: Optional timestamped audio events.
        audio_event_summary: Optional audio event statistics.
    """

    format: str
    job: JobInfo
    metadata: RecognitionMetadata
    results: list[RecognitionResult]
    translations: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    sentiment_analysis: dict[str, Any] | None = None
    topics: dict[str, Any] | None = None
    chapters: list[dict[str, Any]] | None = None
    audio_events: list[dict[str, Any]] | None = None
    audio_event_summary: dict[str, Any] | None = None

    @property
    def transcript_text(self) -> str:
        """
        Extract the full transcript text from results with proper formatting.

        This method intelligently processes the transcript results to create
        properly formatted text, handling word delimiters, punctuation, and
        speaker changes based on language and configuration.

        Returns:
            Formatted transcript text with proper spacing and punctuation.
        """
        if not self.results:
            return ""

        # Get language pack info for word delimiter
        word_delimiter = " "  # Default
        if self.metadata and self.metadata.language_pack_info and "word_delimiter" in self.metadata.language_pack_info:
            word_delimiter = self.metadata.language_pack_info["word_delimiter"]

        # Group results by speaker and process
        transcript_parts = []
        current_speaker = None
        current_group: list[str] = []

        for result in self.results:
            if not result.alternatives:
                continue

            alternative = result.alternatives[0]
            content = alternative.content
            speaker = alternative.speaker

            # Handle speaker changes
            if speaker != current_speaker:
                # Process accumulated group for previous speaker
                if current_group:
                    text = self._join_content_items(current_group, word_delimiter)
                    if current_speaker:
                        transcript_parts.append(f"SPEAKER {current_speaker}: {text}")
                    else:
                        transcript_parts.append(text)
                    current_group = []

                current_speaker = speaker

            # Add content to current group
            if content:
                current_group.append(content)

        # Process final group
        if current_group:
            text = self._join_content_items(current_group, word_delimiter)
            if current_speaker:
                transcript_parts.append(f"SPEAKER {current_speaker}: {text}")
            else:
                transcript_parts.append(text)

        return "\n".join(transcript_parts)

    def _join_content_items(self, content_items: list[str], word_delimiter: str) -> str:
        """
        Join content items with appropriate spacing and punctuation handling.

        Args:
            content_items: List of content strings to join.
            word_delimiter: Delimiter to use between words.

        Returns:
            Properly formatted text string.
        """
        if not content_items:
            return ""

        result: list[str] = []

        for i, content in enumerate(content_items):
            if not content:
                continue

            # Check if this content is punctuation
            is_punctuation = content.strip() in ".,!?;:()[]{}\"'-"

            # Add delimiter before content unless:
            # - It's the first item
            # - It's punctuation
            # - Previous item ended with whitespace
            if i > 0 and not is_punctuation and result and not result[-1].endswith(" "):
                result.append(word_delimiter)

            result.append(content)

        return "".join(result).strip()

    @property
    def confidence(self) -> float | None:
        """Calculate average confidence from all results."""
        confidences = []
        for result in self.results:
            if result.alternatives:
                conf = result.alternatives[0].confidence
                if conf is not None:
                    confidences.append(conf)
        return sum(confidences) / len(confidences) if confidences else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transcript:
        """Create Transcript from API response dictionary."""
        job_data = data["job"]
        job_info = JobInfo.from_dict(job_data)

        metadata_data = data["metadata"]
        metadata = RecognitionMetadata.from_dict(metadata_data)

        results_data = data.get("results", [])
        results = [RecognitionResult.from_dict(result) for result in results_data]

        return cls(
            format=data["format"],
            job=job_info,
            metadata=metadata,
            results=results,
            translations=data.get("translations"),
            summary=data.get("summary"),
            sentiment_analysis=data.get("sentiment_analysis"),
            topics=data.get("topics"),
            chapters=data.get("chapters"),
            audio_events=data.get("audio_events"),
            audio_event_summary=data.get("audio_event_summary"),
        )


@dataclass
class ConnectionConfig:
    """
    Configuration for HTTP connection parameters.

    This class defines all connection-related settings including URL,
    authentication, and timeouts.

    Attributes:
        url: Base URL for the Speechmatics Batch API.
        api_key: Speechmatics API key for authentication.
        connect_timeout: Timeout in seconds for connection establishment.
        operation_timeout: Default timeout for API operations.
    """

    url: str = "https://asr.api.speechmatics.com/v2"
    api_key: str = ""
    connect_timeout: float = 30.0
    operation_timeout: float = 300.0
