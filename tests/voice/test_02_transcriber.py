import asyncio
import os

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import VoiceAgentConfig

api_key = os.getenv("SPEECHMATICS_API_KEY")


@pytest.mark.asyncio
async def test_transcribe_partial():
    """Test transcription.

    This test will:
        - send audio data to the API server
        - wait for the first partial transcript (within 10 seconds)
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=api_key,
        connect=True,
        config=VoiceAgentConfig(
            additional_vocab=[
                AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"]),
            ]
        ),
    )

    # Check we are connected
    assert client._is_connected

    # Create an event to track when the callback is called
    event_received = asyncio.Event()
    received_message = None

    # Callback function for connection
    def on_partial_received(message):
        nonlocal received_message
        received_message = message
        event_received.set()

    # Add listener for PARTIALS
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, on_partial_received)

    # Load the audio file `./assets/audio_01.wav`
    await send_audio_file(client, "./assets/audio_01.wav", event_received)

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(event_received.wait(), timeout=5.0)
        assert received_message is not None
    except asyncio.TimeoutError:
        pytest.fail("ADD_PARTIAL_TRANSCRIPT event was not received within 5 seconds of audio finish")

    # Close session
    await client.disconnect()
    assert not client._is_connected


@pytest.mark.asyncio
async def test_transcribe_final():
    """Test transcription.

    This test will:
        - send audio data to the API server
        - wait for the first final transcript (within 10 seconds)
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(api_key=api_key, connect=True)

    # Check we are connected
    assert client._is_connected

    # Create an event to track when the callback is called
    event_received = asyncio.Event()
    received_message = None

    # Callback function for connection
    def on_final_received(message):
        nonlocal received_message
        received_message = message
        event_received.set()

    # Add listener for PARTIALS
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, on_final_received)

    # Load the audio file `./assets/audio_01.wav`
    await send_audio_file(client, "./assets/audio_01.wav", event_received)

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(event_received.wait(), timeout=5.0)
        assert received_message is not None
    except asyncio.TimeoutError:
        pytest.fail("ADD_TRANSCRIPT event was not received within 5 seconds of audio finish")

    # Close session
    await client.disconnect()
    assert not client._is_connected


@pytest.mark.asyncio
async def test_partial_segment():
    """Test transcription.

    This test will:
        - send audio data to the API server
        - wait for the first partial segment (within 10 seconds)
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(api_key=api_key, connect=True, config=VoiceAgentConfig())

    # Check we are connected
    assert client._is_connected

    # Create an event to track when the callback is called
    event_received = asyncio.Event()

    # Callback function for connection
    def on_segment_received(message):
        # Segments from the message
        segments = message.get("segments", [])

        # We need at least one segment
        if not segments:
            return

        # Get the first segment's text
        transcription = segments[0]["text"]

        # Check transcription starts with `Welcome to Speechmatics`
        if not transcription.lower().startswith("welcome to speech"):
            return

        # Set the event
        event_received.set()

    # Add listener for PARTIALS
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, on_segment_received)

    # Load the audio file `./assets/audio_01.wav`
    await send_audio_file(client=client, audio_file="./assets/audio_01.wav", terminate_event=event_received)

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(event_received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("ADD_PARTIAL_SEGMENT event was not received within 5 seconds of audio finish")

    # Close session
    await client.disconnect()
    assert not client._is_connected
