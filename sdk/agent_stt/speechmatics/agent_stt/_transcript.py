from __future__ import annotations

from typing import Any
from typing import Optional

from ._models import DEFAULT_WORD_DELIMITER
from ._models import Segment
from ._models import TimedEvent


class Transcript:
    """
    Accumulates a session's output: final segments, the live partial, speech/turn events
    and the raw message log.

    A session's transcript is the concatenation of its final segments, so the text reads the
    same way an RT session's does, one segment at a time instead of one word group at a time.

    Args:
        record_events: Whether to keep every raw server message in `events`. Messages this SDK
            version does not model are still captured there.
        delimiter: Separator used between segments. Replaced by the language pack's word
            delimiter once RecognitionStarted arrives.

    Examples:
        >>> transcript = Transcript()
        >>> transcript.add_segment({"message": "AddSegment",
        ...                        "segment": {"transcript": "Hello world"},
        ...                        "metadata": {"start_time": 0.0, "end_time": 1.0}})
        >>> transcript.text()
        'Hello world'
    """

    def __init__(self, *, record_events: bool = True, delimiter: str = DEFAULT_WORD_DELIMITER) -> None:
        self._record_events = record_events
        self._delimiter = delimiter
        self._segments: list[Segment] = []
        self._partial: Optional[Segment] = None
        self._events: list[dict[str, Any]] = []
        self._timeline: list[TimedEvent] = []

    @property
    def segments(self) -> list[Segment]:
        """The final segments received so far, in order."""
        return list(self._segments)

    @property
    def partial(self) -> Optional[Segment]:
        """The segment currently being built, or None when there is nothing in flight."""
        return self._partial

    @property
    def events(self) -> list[dict[str, Any]]:
        """Every raw server message received, in order, when recording is enabled."""
        return list(self._events)

    @property
    def timeline(self) -> list[TimedEvent]:
        """The speech and turn events received so far, in order."""
        return list(self._timeline)

    @property
    def delimiter(self) -> str:
        """The separator used between segments."""
        return self._delimiter

    def set_delimiter(self, delimiter: str) -> None:
        """Set the separator between segments, from the language pack's word delimiter."""
        self._delimiter = delimiter

    def record(self, message: dict[str, Any]) -> None:
        """Append a raw server message to the event log."""
        if self._record_events:
            self._events.append(message)

    def add_segment(self, message: dict[str, Any]) -> Segment:
        """Add a final segment from an AddSegment message and clear the live partial."""
        segment = Segment.from_message(message)
        self._segments.append(segment)
        self._partial = None
        return segment

    def add_partial_segment(self, message: dict[str, Any]) -> Segment:
        """Replace the live partial with the one in an AddPartialSegment message."""
        self._partial = Segment.from_message(message)
        return self._partial

    def add_timed_event(self, message: dict[str, Any]) -> TimedEvent:
        """Add a speech or turn event to the timeline."""
        event = TimedEvent.from_message(message)
        self._timeline.append(event)
        return event

    def text(self, *, include_partial: bool = False, speaker_labels: bool = False) -> str:
        """
        Render the transcript.

        Args:
            include_partial: Append the segment currently in flight.
            speaker_labels: Prefix each segment with its speaker label, where one is attributed.

        Returns:
            The final segments joined by the session's delimiter.
        """
        segments = list(self._segments)
        if include_partial and self._partial is not None:
            segments.append(self._partial)

        parts = []
        for segment in segments:
            if not segment.transcript:
                continue
            if speaker_labels and segment.speaker:
                parts.append(f"{segment.speaker}: {segment.transcript}")
            else:
                parts.append(segment.transcript)
        return self._delimiter.join(parts)

    def reset(self) -> None:
        """Drop all accumulated state, keeping the delimiter."""
        self._segments.clear()
        self._partial = None
        self._events.clear()
        self._timeline.clear()

    def __str__(self) -> str:
        return self.text()
