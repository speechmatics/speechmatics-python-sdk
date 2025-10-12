import datetime
import json
import os
import shutil
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file
from pydantic import BaseModel
from pydantic import Field

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._turn import SmartTurnDetector

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping smart turn tests in CI")


# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL: Optional[str] = os.getenv("SPEECHMATICS_SERVER_URL", "wss://preview.rt.speechmatics.com/v2")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]

# Detector
detector = SmartTurnDetector(auto_init=False, threshold=0.75)


class TranscriptionTest(BaseModel):
    id: str
    path: str
    sample_rate: int
    language: str
    vocab: list[str] = Field(default_factory=list)
    expected: list[bool] = Field(default_factory=list)


SAMPLES: list[TranscriptionTest] = [
    TranscriptionTest(
        id="01",
        path="./assets/audio_04_16kHz.wav",
        sample_rate=16000,
        language="en",
        # expected=[False, False, False, True],
    ),
    # TranscriptionTest(
    #     id="02",
    #     path="./assets/audio_05_16kHz.wav",
    #     sample_rate=16000,
    #     language="en",
    # ),
    # TranscriptionTest(
    #     id="03",
    #     path="./assets/audio_06_16kHz.wav",
    #     sample_rate=16000,
    #     language="en",
    # ),
]


@pytest.mark.asyncio
async def test_clean_tmp():
    """Clear tmp directory"""

    # Output directory
    tmp_dir = os.path.join(os.path.dirname(__file__), "./.tmp/turn")

    # Clean tmp
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Re-create
    os.makedirs(tmp_dir, exist_ok=True)
    assert os.path.exists(tmp_dir)


@pytest.mark.asyncio
async def test_onnx_model():
    """Download ONNX model"""

    # Initialize
    detector.setup()

    # Check exists
    assert detector.model_exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: f"{s.id}:{s.path}")
async def test_prediction(sample: TranscriptionTest):
    """Test transcription and prediction"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Start time
    start_time = datetime.datetime.now()

    # Results
    results: list[bool] = []

    # Client
    client = await get_client(
        api_key=api_key,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            max_delay=0.7,
            end_of_utterance_mode=EndOfUtteranceMode.SMART_TURN,
            end_of_utterance_silence_trigger=0.5,
            enable_diarization=True,
            sample_rate=sample.sample_rate,
        ),
    )

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        log = json.dumps({"ts": round(ts, 3), "payload": message})
        if SHOW_LOG:
            print(log)

    # Add listeners
    client.on(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    # client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, sample.path)

    # FOOTER
    if SHOW_LOG:
        print("---")
        print()
        print()

    # Close session
    await client.disconnect()
    assert not client._is_connected

    # Validate (if we have expected results)
    if sample.expected:
        assert results == sample.expected
