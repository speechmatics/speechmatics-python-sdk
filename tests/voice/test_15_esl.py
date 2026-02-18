import asyncio
import os

import pytest
from _utils import get_client
from _utils import log_client_messages
from _utils import send_audio_file

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import OperatingPoint
from speechmatics.voice import SpeechSegmentConfig
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._presets import VoiceAgentConfigPreset

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping transcription tests in CI")

# Skip if ESL tests is not enabled
pytestmark = pytest.mark.skipif(os.getenv("TEST_ESL", "0").lower() not in ["1", "true"], reason="Skipping ESL tests")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL = os.getenv("TEST_ESL_URL", "ws://localhost:8080/v2")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


@pytest.mark.asyncio
async def test_esl():
    """Local ESL inference."""

    # Client
    client = await get_client(
        api_key=API_KEY,
        url=URL,
        connect=False,
        config=VoiceAgentConfigPreset.FIXED(
            VoiceAgentConfig(
                operating_point=OperatingPoint.STANDARD,
                max_delay=1.0,
                speech_segment_config=SpeechSegmentConfig(emit_sentences=True, add_trailing_eos=False),
            )
        ),
    )

    # Add listeners
    log_client_messages(
        client,
        [
            AgentServerMessageType.RECOGNITION_STARTED,
            AgentServerMessageType.INFO,
            AgentServerMessageType.DIAGNOSTICS,
            AgentServerMessageType.ADD_SEGMENT,
            AgentServerMessageType.END_OF_UTTERANCE,
        ],
    )

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
