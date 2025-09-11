import datetime
import json
import os

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig

api_key = os.getenv("SPEECHMATICS_API_KEY")


@pytest.mark.asyncio
async def test_log_messages():
    """Test transcription.

    This test will:
        - log messages
    """

    # Client
    client = await get_client(
        api_key=api_key,
        connect=True,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=0.2, max_delay=0.7, end_of_utterance_mode=EndOfUtteranceMode.FIXED
        ),
    )

    # Check we are connected
    assert client._is_connected

    # Create an event to track when the callback is called
    messages: list[str] = []

    # Start time
    start_time = datetime.datetime.now()

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        log = {"ts": ts, "payload": message}
        messages.append(json.dumps(log))
        print(json.dumps(log))

    # Add listeners
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
    client.on(AgentServerMessageType.ADD_INTERIM_SEGMENTS, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENTS, log_message)
    client.on(AgentServerMessageType.SPEAKING_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKING_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # Load the audio file `./assets/audio_01.wav`
    audio_file = "./assets/audio_01.wav"
    print()
    print(f"Loading audio file: {audio_file}")
    print("---")
    await send_audio_file(client, audio_file)
    print("---")
    print()

    # Close session
    await client.disconnect()
    assert not client._is_connected
