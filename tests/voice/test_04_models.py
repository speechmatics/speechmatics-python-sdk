import asyncio
import datetime
import json
import os
from typing import Any
from typing import Optional

import pytest
from _utils import ConversationLog
from _utils import get_client

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import AnnotationFlags
from speechmatics.voice._models import AnnotationResult


@pytest.mark.asyncio
async def test_annotation_result():
    """Test AnnotationResult.

    - create new annotation
    - add, remove, check for flags
    - serialize to JSON
    """

    # Create a new annotation
    annotation = AnnotationResult.from_flags(AnnotationFlags.NO_TEXT, AnnotationFlags.HAS_DISFLUENCY)
    assert annotation is not None

    # Add extra flag
    annotation.add(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Has a flag
    assert annotation.has(AnnotationFlags.NO_TEXT)
    assert annotation.has(AnnotationFlags.HAS_DISFLUENCY)
    assert annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Remove a flag
    annotation.remove(AnnotationFlags.MULTIPLE_SPEAKERS)
    assert not annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Add existing flag
    annotation.add(AnnotationFlags.NO_TEXT)
    assert annotation.has(AnnotationFlags.NO_TEXT)
    assert str(annotation) == "['no_text', 'has_disfluency']"

    # Add multiple flags
    annotation.add(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)
    assert annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)

    # Remove multiple flags
    annotation.remove(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)
    assert not annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)

    # Compare
    assert annotation == AnnotationResult([AnnotationFlags.HAS_DISFLUENCY, AnnotationFlags.NO_TEXT])

    # Compare with non AnnotationResult
    assert annotation != "string"
    assert annotation != 123

    # String representation
    assert str(annotation) == "['no_text', 'has_disfluency']"
    assert str({"annotation": annotation}) == "{'annotation': ['no_text', 'has_disfluency']}"
    assert json.dumps({"annotation": annotation}) == '{"annotation": ["no_text", "has_disfluency"]}'


@pytest.mark.asyncio
async def test_speech_fragments():
    """Test SpeechFragment.

    - create fragment(s)
    - check output from processing conversation
    - serialize to JSON
    """

    # Test conversation
    log = ConversationLog(os.path.join(os.path.dirname(__file__), "./assets/chat2.jsonl"))
    chat = log.get_conversation(
        ["Info", "RecognitionStarted", "AddPartialTranscript", "AddTranscript", "EndOfUtterance"]
    )

    # Start time
    start_time = datetime.datetime.now()

    # Create a client
    client = await get_client(api_key="NONE", connect=False)
    assert client is not None

    # Start the queue
    client._start_stt_queue()

    # Event to wait
    event_rx: asyncio.Event = asyncio.Event()
    last_message: Optional[dict[str, Any]] = None

    # Reset message
    def message_reset():
        nonlocal last_message
        last_message = None
        event_rx.clear()

    # Message receiver
    def message_rx(message: dict[str, Any]):
        nonlocal last_message
        last_message = message
        event_rx.set()

    # Send a message from the conversation
    async def send_message(idx: int, count: int = 1, use_ttl: bool = True):
        for i in range(count):
            # Get the message from the chat
            message = chat[idx + i]

            # Wait for TTL to expire
            if use_ttl:
                ttl = (start_time + datetime.timedelta(seconds=message["ts"])) - datetime.datetime.now()
                if ttl.total_seconds() > 0:
                    await asyncio.sleep(ttl.total_seconds())
            else:
                await asyncio.sleep(0.05)

            # Emit the message
            client.emit(message["payload"]["message"], message["payload"])

    # Add listener for first interim segment
    message_reset()
    client.once(AgentServerMessageType.ADD_PARTIAL_SEGMENT, message_rx)

    # Inject first partial
    await send_message(0, count=6, use_ttl=False)

    # Wait for first segment
    try:
        await asyncio.wait_for(event_rx.wait(), timeout=5.0)
        assert last_message is not None
    except asyncio.TimeoutError:
        pytest.fail("ADD_PARTIAL_SEGMENT event was not received within 5 seconds")

    # Check the right message was received
    assert last_message.get("message") == AgentServerMessageType.ADD_PARTIAL_SEGMENT

    # Check the segment
    segments = last_message.get("segments", [])
    assert len(segments) == 1
    seg0 = segments[0]
    assert seg0["speaker_id"] == "S1"
    assert seg0["text"] == "Welcome"
    assert f"{seg0['speaker_id']}: {seg0['text']}" == "S1: Welcome"

    # Add listener for final segment
    message_reset()
    client.once(AgentServerMessageType.ADD_SEGMENT, message_rx)

    # Send a more partials and finals
    await send_message(5, count=8, use_ttl=False)

    # Wait for final segment
    try:
        await asyncio.wait_for(event_rx.wait(), timeout=5.0)
        assert last_message is not None
    except asyncio.TimeoutError:
        pytest.fail("ADD_SEGMENT event was not received within 5 seconds")

    # Check the right message was received
    assert last_message.get("message") == AgentServerMessageType.ADD_SEGMENT

    # Check the segment
    segments = last_message.get("segments", [])
    assert len(segments) == 1
    seg0 = segments[0]
    assert seg0["speaker_id"] == "S1"
    assert seg0["text"] == "Welcome to Speechmatics."
    assert f"{seg0['speaker_id']}: {seg0['text']}" == "S1: Welcome to Speechmatics."

    # Stop the queue
    client._stop_stt_queue()


@pytest.mark.asyncio
async def test_end_of_utterance_fixed():
    """Test EndOfUtterance from STT engine.

    - send converstaion messages (fast)
    - wait for `EndOfUtterance` message
    """

    # Test conversation
    log = ConversationLog(os.path.join(os.path.dirname(__file__), "./assets/chat2.jsonl"))
    chat = log.get_conversation(
        ["Info", "RecognitionStarted", "AddPartialTranscript", "AddTranscript", "EndOfUtterance"]
    )

    # Start time
    start_time = datetime.datetime.now()

    # Create a client
    client = await get_client(api_key="NONE", connect=False)
    assert client is not None

    # Start the queue
    client._start_stt_queue()

    # Event to wait
    event_rx: asyncio.Event = asyncio.Event()
    last_message: Optional[dict[str, Any]] = None

    # Message receiver
    def message_rx(message: dict[str, Any]):
        nonlocal last_message
        last_message = message
        event_rx.set()

    # Send a message from the conversation
    async def send_message(idx: int, count: int = 1, use_ttl: bool = True):
        for i in range(count):
            # Get the message from the chat
            message = chat[idx + i]

            # Wait for TTL to expire
            if use_ttl:
                ttl = (start_time + datetime.timedelta(seconds=message["ts"])) - datetime.datetime.now()
                if ttl.total_seconds() > 0:
                    await asyncio.sleep(ttl.total_seconds())
            else:
                await asyncio.sleep(0.005)

            # Emit the message
            client.emit(message["payload"]["message"], message["payload"])

    # Add listener for first interim segment
    client.once(AgentServerMessageType.END_OF_TURN, message_rx)

    # Inject conversation
    await send_message(0, count=14, use_ttl=False)

    # Wait for EndOfTurn
    try:
        await asyncio.wait_for(event_rx.wait(), timeout=5.0)
        assert last_message is not None
    except asyncio.TimeoutError:
        pytest.fail("END_OF_TURN event was not received within 5 seconds")

    # Check the right message was received
    assert last_message.get("message") == AgentServerMessageType.END_OF_TURN


@pytest.mark.asyncio
async def test_external_vad():
    """Test EndOfUtterance from STT engine.

    - send converstaion messages (realtime)
    - finalizes based on external VAD (e.g. Pipecat's `UserStoppedSpeakingFrame` frame)
    """

    # Test conversation
    log = ConversationLog(os.path.join(os.path.dirname(__file__), "./assets/chat2.jsonl"))
    chat = log.get_conversation(
        ["Info", "RecognitionStarted", "AddPartialTranscript", "AddTranscript", "EndOfUtterance"]
    )

    # Start time
    start_time = datetime.datetime.now()

    # Adaptive timeout
    adaptive_timeout = 1.0

    # Create a client
    client = await get_client(
        api_key="NONE",
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=adaptive_timeout, end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL
        ),
    )
    assert client is not None

    # Start the queue
    client._start_stt_queue()
    # Event to wait
    event_rx: asyncio.Event = asyncio.Event()
    last_message: Optional[dict[str, Any]] = None

    # Message receiver
    def message_rx(message: dict[str, Any]):
        nonlocal last_message
        last_message = message
        event_rx.set()

    # Send a message from the conversation
    async def send_message(idx: int, count: int = 1, use_ttl: bool = True):
        for i in range(count):
            # Get the message from the chat
            message = chat[idx + i]

            # Wait for TTL to expire
            if use_ttl:
                ttl = (start_time + datetime.timedelta(seconds=message["ts"])) - datetime.datetime.now()
                if ttl.total_seconds() > 0:
                    await asyncio.sleep(ttl.total_seconds())
            else:
                await asyncio.sleep(0.005)

            # Emit the message
            client.emit(message["payload"]["message"], message["payload"])

    # Inject conversation
    await send_message(0, count=12, use_ttl=False)

    # Momentary pause
    await asyncio.sleep(0.5)

    # Add listener for first interim segment
    client.once(AgentServerMessageType.ADD_SEGMENT, message_rx)

    # Pause for a moment
    await asyncio.sleep(0.5)

    # Send finalize
    client.finalize()

    # Wait for AddSegments
    try:
        await asyncio.wait_for(event_rx.wait(), timeout=4)
        assert last_message is not None
    except asyncio.TimeoutError:
        pytest.fail("ADD_SEGMENT event was not received within 4 seconds")

    # Check the right message was received
    assert last_message.get("message") == AgentServerMessageType.ADD_SEGMENT

    # Check the segment
    segments = last_message.get("segments", [])
    assert len(segments) == 1
    seg0 = segments[0]
    assert seg0["speaker_id"] == "S1"
    assert seg0["text"] == "Welcome to Speechmatics"
    assert f"{seg0['speaker_id']}: {seg0['text']}" == "S1: Welcome to Speechmatics"

    # Stop the queue
    client._stop_stt_queue()


@pytest.mark.asyncio
async def test_end_of_utterance_adaptive_vad():
    """Test EndOfUtterance from STT engine.

    - send converstaion messages (realtime)
    - wait for `EndOfUtterance` message from SDK (adaptive)
    - check the interval to receive the EndOfUtterance message is within 25% of expected
    """

    # Test conversation
    log = ConversationLog(os.path.join(os.path.dirname(__file__), "./assets/chat2.jsonl"))
    chat = log.get_conversation(
        ["Info", "RecognitionStarted", "AddPartialTranscript", "AddTranscript", "EndOfUtterance"]
    )

    # Start time
    start_time = datetime.datetime.now()

    # Adaptive timeout
    adaptive_timeout = 0.5

    # Create a client
    client = await get_client(
        api_key="NONE",
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=adaptive_timeout, end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE
        ),
    )
    assert client is not None

    # Start the queue
    client._start_stt_queue()

    # Event to wait
    eot_received: asyncio.Event = asyncio.Event()
    last_message: Optional[dict[str, Any]] = None

    # Time for last final (used to calculate the interval)
    last_final_time: Optional[float] = None
    receive_interval: Optional[float] = None

    # Transcript receiver
    def transcript_rx(message: dict[str, Any]):
        if not eot_received.is_set():
            nonlocal last_final_time
            last_final_time = datetime.datetime.now()

    # End of turn receiver
    def eot_rx(message: dict[str, Any]):
        nonlocal last_message
        nonlocal receive_interval
        last_message = message
        receive_interval = (datetime.datetime.now() - last_final_time).total_seconds()
        eot_received.set()

    # Send a message from the conversation
    async def send_message(idx: int, count: int = 1, use_ttl: bool = True):
        for i in range(count):
            # Get the message from the chat
            message = chat[idx + i]

            # Wait for TTL to expire
            if use_ttl:
                ttl = (start_time + datetime.timedelta(seconds=message["ts"])) - datetime.datetime.now()
                if ttl.total_seconds() > 0:
                    await asyncio.sleep(ttl.total_seconds())
            else:
                await asyncio.sleep(0.005)

            # Emit the message
            client.emit(message["payload"]["message"], message["payload"])

    # Add listener for partials (as these will trigger the adaptive timer))
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, transcript_rx)

    # Add listener for end of turn
    client.once(AgentServerMessageType.END_OF_TURN, eot_rx)

    # Inject conversation up to the penultimate final from the STT
    await send_message(0, count=12, use_ttl=True)

    # Check we have had a final
    assert last_final_time is not None

    # Timing info
    timeout = adaptive_timeout * 1.5

    # Wait for EndOfUtterance
    try:
        await asyncio.wait_for(eot_received.wait(), timeout=timeout)
        assert last_message is not None
    except asyncio.TimeoutError:
        pytest.fail(f"END_OF_TURN event was not received within {timeout} seconds")

    # Check the right message was received
    assert last_message.get("message") == AgentServerMessageType.END_OF_TURN

    # Check the interval was within +/- 25% of the adaptive trigger of 0.5 the timeout (see client code)
    expected_min_interval = adaptive_timeout * 0.5 * 0.75
    expected_max_interval = adaptive_timeout * 0.5 * 1.25
    assert receive_interval >= expected_min_interval
    assert receive_interval <= expected_max_interval

    # Stop the queue
    client._stop_stt_queue()
