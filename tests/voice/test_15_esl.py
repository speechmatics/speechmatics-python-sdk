import os

import pytest
from _utils import get_client, log_client_messages, send_audio_file
import asyncio
from speechmatics.voice._presets import VoiceAgentConfigPreset

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL = "ws://localhost:8080/v2"
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


@pytest.mark.asyncio
async def test_esl():
    """Local ESL inference."""

    # Client
    client = await get_client(api_key=API_KEY, url=URL, connect=False, config=VoiceAgentConfigPreset.FAST())

    # Add listeners
    log_client_messages(client)

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Load the audio file `./assets/audio_01_16kHz.wav`
    await send_audio_file(client, "./assets/audio_01_16kHz.wav")

    # Wait 5 seconds
    await asyncio.sleep(5)

    # Close session
    await client.disconnect()
    assert not client._is_connected
