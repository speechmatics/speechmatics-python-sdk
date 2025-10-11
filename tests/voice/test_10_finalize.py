import asyncio
import datetime
import json
import os
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file
from _utils import send_silence

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig

API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL: Optional[str] = "wss://jamesw.lab.speechmatics.io/v2"
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]
AUDIO_FILE = "./assets/audio_03_16kHz.wav"


@pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping in CI")
@pytest.mark.asyncio
async def test_finalize():
    """Test finalization.

    This test will:
        - play a short audio clip
        - finalize the segment
        - this MUST use a preview / dev endpoint
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=api_key,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=0.7,
            max_delay=1.2,
            end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
            enable_preview_features=True,
        ),
    )

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0

    # Flag
    eot_received = asyncio.Event()

    # Start time
    start_time = datetime.datetime.now()

    # Bytes logger
    def log_bytes_sent(bytes):
        nonlocal bytes_sent
        bytes_sent += bytes

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        audio_ts = bytes_sent / 16000 / 2
        log = json.dumps({"ts": round(ts, 3), "audio_ts": round(audio_ts, 2), "payload": message})
        messages.append(log)
        if SHOW_LOG:
            print(log)

    # EOT received
    def eot_received_callback(message):
        eot_received.set()

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # End of Turn
    client.once(AgentServerMessageType.END_OF_TURN, eot_received_callback)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")
        log_message({"message": "VoiceAgentConfig", **client._config.model_dump()})
        log_message({"message": "TranscriptionConfig", **client._transcription_config.to_dict()})
        log_message({"message": "AudioFormat", **client._audio_format.to_dict()})

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip(f"Failed to connect to server: {URL}")

    # Check we are connected
    assert client._is_connected

    # Set chunk size
    chunk_size = 160

    # Send words twice with silence in-between
    await send_audio_file(client, AUDIO_FILE, chunk_size=chunk_size, progress_callback=log_bytes_sent)
    await send_silence(client, 1.0, chunk_size=chunk_size, progress_callback=log_bytes_sent)
    await send_audio_file(client, AUDIO_FILE, chunk_size=chunk_size, progress_callback=log_bytes_sent)

    # Send silence in a thread
    asyncio.create_task(
        send_silence(
            client, 10.0, chunk_size=chunk_size, progress_callback=log_bytes_sent, terminate_event=eot_received
        )
    )

    # Wait for 0.25 seconds
    await asyncio.sleep(0.25)

    # Request the speakers result
    finalize_trigger_time = datetime.datetime.now()
    client.finalize()

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(eot_received.wait(), timeout=5.0)
        finalize_latency = (datetime.datetime.now() - finalize_trigger_time).total_seconds() * 1000
    except asyncio.TimeoutError:
        pytest.fail("END_OF_TURN event was not received within 5 seconds of audio finish")

    # FOOTER
    if SHOW_LOG:
        print(f"--- latency {finalize_latency:.2f} ms")
        print()
        print()

    # Debug result
    print(f"{finalize_latency:.2f}ms")

    # Make sure latency is within bounds
    assert finalize_latency > 50
    assert finalize_latency < 500

    # Close session
    await client.disconnect()
    assert not client._is_connected
