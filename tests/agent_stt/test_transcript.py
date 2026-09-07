from speechmatics.agent_stt import Segment
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TimedEvent
from speechmatics.agent_stt import Transcript


def segment_message(transcript, start=0.0, end=1.0, speaker=None, is_final=True):
    segment = {"transcript": transcript}
    if speaker is not None:
        segment["speaker"] = speaker
    return {
        "message": ServerMessageType.ADD_SEGMENT if is_final else ServerMessageType.ADD_PARTIAL_SEGMENT,
        "segment": segment,
        "metadata": {"start_time": start, "end_time": end},
    }


def test_segment_from_message():
    segment = Segment.from_message(segment_message("Hello world", 1.0, 2.5, speaker="S1"))
    assert segment == Segment(transcript="Hello world", start_time=1.0, end_time=2.5, speaker="S1", is_final=True)


def test_partial_segment_is_not_final():
    assert Segment.from_message(segment_message("Hello", is_final=False)).is_final is False


def test_segment_without_speaker():
    assert Segment.from_message(segment_message("Hello")).speaker is None


def test_timed_event_from_start_time():
    event = TimedEvent.from_message({"message": "StartOfTurn", "metadata": {"start_time": 1.25}})
    assert event == TimedEvent(message="StartOfTurn", time=1.25)


def test_timed_event_from_end_time():
    event = TimedEvent.from_message({"message": "EndOfTurn", "metadata": {"end_time": 3.5}})
    assert event == TimedEvent(message="EndOfTurn", time=3.5)


def test_finals_accumulate():
    transcript = Transcript()
    transcript.add_segment(segment_message("Hello there."))
    transcript.add_segment(segment_message("How are you?"))
    assert transcript.text() == "Hello there. How are you?"
    assert len(transcript.segments) == 2


def test_partial_replaced_and_cleared_by_final():
    transcript = Transcript()
    transcript.add_partial_segment(segment_message("Hel", is_final=False))
    transcript.add_partial_segment(segment_message("Hello wor", is_final=False))
    assert transcript.partial is not None
    assert transcript.partial.transcript == "Hello wor"
    assert transcript.text() == ""

    transcript.add_segment(segment_message("Hello world."))
    assert transcript.partial is None
    assert transcript.text() == "Hello world."


def test_text_including_partial():
    transcript = Transcript()
    transcript.add_segment(segment_message("Hello."))
    transcript.add_partial_segment(segment_message("How are", is_final=False))
    assert transcript.text() == "Hello."
    assert transcript.text(include_partial=True) == "Hello. How are"


def test_text_with_speaker_labels():
    transcript = Transcript()
    transcript.add_segment(segment_message("Hello.", speaker="S1"))
    transcript.add_segment(segment_message("Hi.", speaker="S2"))
    transcript.add_segment(segment_message("No speaker."))
    assert transcript.text(speaker_labels=True) == "S1: Hello. S2: Hi. No speaker."


def test_delimiter_from_language_pack():
    transcript = Transcript()
    transcript.set_delimiter("")
    transcript.add_segment(segment_message("你好"))
    transcript.add_segment(segment_message("世界"))
    assert transcript.text() == "你好世界"


def test_empty_segments_skipped():
    transcript = Transcript()
    transcript.add_segment(segment_message("Hello."))
    transcript.add_segment(segment_message(""))
    assert transcript.text() == "Hello."


def test_events_recorded():
    transcript = Transcript()
    message = segment_message("Hello.")
    transcript.record(message)
    transcript.record({"message": "SomeFutureMessage", "payload": 1})
    assert transcript.events == [message, {"message": "SomeFutureMessage", "payload": 1}]


def test_event_recording_can_be_disabled():
    transcript = Transcript(record_events=False)
    transcript.record(segment_message("Hello."))
    assert transcript.events == []


def test_timeline():
    transcript = Transcript()
    transcript.add_timed_event({"message": "SpeechStarted", "metadata": {"start_time": 0.5}})
    transcript.add_timed_event({"message": "EndOfTurn", "metadata": {"end_time": 2.0}})
    assert [event.message for event in transcript.timeline] == ["SpeechStarted", "EndOfTurn"]


def test_reset_keeps_delimiter():
    transcript = Transcript()
    transcript.set_delimiter("")
    transcript.add_segment(segment_message("Hello."))
    transcript.record(segment_message("Hello."))
    transcript.reset()
    assert transcript.segments == []
    assert transcript.events == []
    assert transcript.delimiter == ""
