import asyncio
import datetime
import os
from typing import Any
from typing import Optional

import pytest
from _utils import ConversationLog
from _utils import get_client

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig


@pytest.mark.skip(reason="Not fully implemented!")
@pytest.mark.asyncio
async def test_end_of_thought():
    """Use inference for end of thought.

    - send the utterance
    - predict end of thought
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
            end_of_utterance_silence_trigger=adaptive_timeout,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=False,
        ),
    )
    assert client is not None

    # Start the queue
    client._start_stt_queue()

    # Event to wait
    had_speaking_ended: asyncio.Event = asyncio.Event()
    last_message: Optional[dict[str, Any]] = None

    # Message receiver
    def message_rx(message: dict[str, Any]):
        nonlocal last_message
        last_message = message

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
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, message_rx)
    client.once(AgentServerMessageType.SPEAKER_ENDED, lambda message: had_speaking_ended.set())

    # Inject conversation
    await send_message(0, count=12, use_ttl=False)

    # Wait for EndOfUtterance
    try:
        await asyncio.wait_for(had_speaking_ended.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.fail("SPEAKER_ENDED event was not received within 10 seconds")

    # Check the last message was expected
    assert last_message is not None
    assert last_message.get("message") == AgentServerMessageType.ADD_PARTIAL_SEGMENT

    # Segment
    segment = last_message.get("segments", [])[0]
    assert segment is not None

    # Debug
    # print(segment["text"])

    # Stop the queue
    client._stop_stt_queue()
