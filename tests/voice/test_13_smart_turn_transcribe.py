import asyncio
import datetime
import json
import os
import shutil
import wave
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
        expected=[False, False, False, True],
    ),
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
            end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL,
            enable_diarization=True,
            sample_rate=sample.sample_rate,
            audio_buffer_length=10.0,
        ),
    )

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        log = json.dumps({"ts": round(ts, 3), "payload": message})
        if SHOW_LOG:
            print(log)

    # Save the slice
    async def save_slice(audio: bytes, output_file: str):
        """Save audio to a temporary WAV file"""

        # Write bytes to a temporary WAV file
        with wave.open(output_file, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample.sample_rate)
            wav_file.writeframes(audio)

    # Extract audio
    async def predict_turn(event_time: float):
        """Extract audio on speaker end event.

        Evaluate whether the person has finished speaking:
        - take the 'time'
        - get audio or 8 seconds leading up to this time
        - evaluate using the detector
        """

        # Get audio
        event_audio = await client._audio_buffer.get_frames(event_time - 8.0, event_time)

        # Save slice
        if SHOW_LOG:
            await save_slice(
                event_audio, os.path.join(os.path.dirname(__file__), f"./.tmp/turn/{sample.id}_{event_time:.2f}.wav")
            )

        # Evaluate
        result = await detector.predict(
            event_audio, language=sample.language, sample_rate=sample.sample_rate, sample_width=2
        )

        # Debug
        if SHOW_LOG:
            print()
            print(" --> SPEAKER_ENDED <--")
            print("  - event_time:", event_time)
            print("  - event_audio:", len(event_audio))
            print("  - result:", result)
            print()

        # Validate
        results.append(result.prediction)

    # Prediction handler
    def handle_speaker_ended(message):
        event_time = message.get("status", {}).get("time", 0)
        asyncio.create_task(predict_turn(event_time + 0.05))

    # Add listeners
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # Listener for prediction
    client.on(AgentServerMessageType.SPEAKER_ENDED, handle_speaker_ended)

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

    # Validate
    assert results == sample.expected
