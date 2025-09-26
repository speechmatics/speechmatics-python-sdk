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
show_log = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


@pytest.mark.asyncio
async def test_log_messages():
    """Test transcription.

    This test will:
        - log messages
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=0.2,
            max_delay=0.7,
            end_of_utterance_mode=EndOfUtteranceMode.FIXED,
            enable_diarization=True,
        ),
    )

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0

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
        log = json.dumps({"ts": ts, "audio_ts": audio_ts, "payload": message})
        messages.append(log)
        if show_log:
            print(log)

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.once(AgentServerMessageType.INFO, log_message)
    client.on(AgentServerMessageType.WARNING, log_message)
    client.on(AgentServerMessageType.ERROR, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # Load the audio file `./assets/audio_01_16kHz.wav`
    audio_file = "./assets/audio_01_16kHz.wav"

    # HEADER
    if show_log:
        print()
        print()
        print("---")
        log_message({"message": "AudioFile", "path": audio_file})
        log_message({"message": "VoiceAgentConfig", **client._config.model_dump()})
        log_message({"message": "TranscriptionConfig", **client._transcription_config.to_dict()})
        log_message({"message": "AudioFormat", **client._audio_format.to_dict()})

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, audio_file, progress_callback=log_bytes_sent)

    # FOOTER
    if show_log:
        print("---")
        print()
        print()

    # Close session
    await client.disconnect()
    assert not client._is_connected
