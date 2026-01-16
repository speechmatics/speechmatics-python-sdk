import datetime
import json
import os

import pytest
from _utils import get_client
from _utils import send_audio_file
from pydantic import Field

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice._models import BaseModel
from speechmatics.voice._presets import VoiceAgentConfigPreset

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping smart turn tests in CI")


# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


class TranscriptionSpeaker(BaseModel):
    text: str
    speaker_id: int = "S1"


class TranscriptionTest(BaseModel):
    id: str
    path: str
    sample_rate: int
    language: str
    segments: list[TranscriptionSpeaker]
    additional_vocab: list[AdditionalVocabEntry] = Field(default_factory=list)


class TranscriptionTests(BaseModel):
    samples: list[TranscriptionTest]


SAMPLES: TranscriptionTests = TranscriptionTests.from_dict(
    {
        "samples": [
            {
                "id": "07",
                "path": "./assets/audio_07b_16kHz.wav",
                "sample_rate": 16000,
                "language": "en",
                "segments": [
                    {"text": "Hello."},
                    {"text": "So tomorrow."},
                    {"text": "Wednesday."},
                    {"text": "Of course. That's fine."},
                    {"text": "Because."},
                    {"text": "In front."},
                    {"text": "Do you think so?"},
                    {"text": "Brilliant."},
                    {"text": "Banana."},
                    {"text": "When?"},
                    {"text": "Today."},
                    {"text": "This morning."},
                    {"text": "Goodbye."},
                ],
            },
        ]
    }
)


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES.samples, ids=lambda s: f"{s.id}:{s.path}")
async def test_prediction(sample: TranscriptionTest):
    """Test transcription and prediction"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Start time
    start_time = datetime.datetime.now()

    # Results
    eot_count: int = 0
    segment_transcribed: list[str] = []

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=VoiceAgentConfigPreset.ADAPTIVE(),
    )

    # SOT detected
    def sot_detected(message):
        nonlocal eot_count
        eot_count += 1
        print("✅ START_OF_TURN: {turn_id}".format(**message))

    # Finalized segment
    def add_segments(message):
        segments = message["segments"]
        for s in segments:
            segment_transcribed.append(s["text"])
            print('🚀 ADD_SEGMENT: {speaker_id} @ "{text}"'.format(**s))

    # EOT detected
    def eot_detected(message):
        nonlocal eot_count
        eot_count += 1
        print("🏁 END_OF_TURN: {turn_id}\n".format(**message))

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        log = json.dumps({"ts": round(ts, 3), "payload": message})
        if SHOW_LOG:
            print(log)

    # # Add listeners
    # for message_type in AgentServerMessageType:
    #     if message_type not in [AgentServerMessageType.AUDIO_ADDED]:
    #         client.on(message_type, log_message)

    # Custom listeners
    client.on(AgentServerMessageType.START_OF_TURN, sot_detected)
    client.on(AgentServerMessageType.END_OF_TURN, eot_detected)
    client.on(AgentServerMessageType.ADD_SEGMENT, add_segments)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip("Failed to connect to server")

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

    # Debug count
    print(f"EOT count: {eot_count}")
    print(f"Segment transcribed: {len(segment_transcribed)}")

    # Check the length of the results
    assert len(segment_transcribed) == len(sample.segments)

    # Validate (if we have expected results)
    for idx, result in enumerate(segment_transcribed):
        assert result.lower() == sample.segments[idx].text.lower()
