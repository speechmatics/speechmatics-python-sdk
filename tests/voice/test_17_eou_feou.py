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
from speechmatics.voice._utils import TextUtils

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping smart turn tests in CI")


# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


class TranscriptionSpeaker(BaseModel):
    text: str
    speaker_id: str = "S1"
    start_time: float = 0.0  # Expected start time in seconds
    end_time: float = 0.0  # Expected end time in seconds


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
            # {
            #     "id": "07",
            #     "path": "./assets/audio_07b_16kHz.wav",
            #     "sample_rate": 16000,
            #     "language": "en",
            #     "segments": [
            #         {"text": "Hello."},
            #         {"text": "So tomorrow."},
            #         {"text": "Wednesday."},
            #         {"text": "Of course. That's fine."},
            #         {"text": "Because."},
            #         {"text": "In front."},
            #         {"text": "Do you think so?"},
            #         {"text": "Brilliant."},
            #         {"text": "Banana."},
            #         {"text": "When?"},
            #         {"text": "Today."},
            #         {"text": "This morning."},
            #         {"text": "Goodbye."},
            #     ],
            # },
            {
                "id": "08",
                "path": "./assets/audio_08_16kHz.wav",
                "sample_rate": 16000,
                "language": "en",
                "segments": [
                    {"text": "Hello.", "start_time": 0.24, "end_time": 0.8},
                    {"text": "Goodbye.", "start_time": 1.64, "end_time": 2.2},
                    {"text": "Banana.", "start_time": 2.96, "end_time": 3.44},
                    {"text": "Breakaway.", "start_time": 4.2, "end_time": 5.12},
                    {"text": "Before.", "start_time": 5.92, "end_time": 6.52},
                    {"text": "After.", "start_time": 7.44, "end_time": 8.0},
                ],
            },
        ]
    }
)


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES.samples, ids=lambda s: f"{s.id}:{s.path}")
async def test_turn_feou(sample: TranscriptionTest):
    """Test transcription and prediction"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Start time
    start_time = datetime.datetime.now()

    # Results
    eot_count: int = 0
    segments_received: list[dict] = []

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=VoiceAgentConfigPreset.ADAPTIVE(),
    )

    # SOT detected
    def sot_detected(message):
        if SHOW_LOG:
            print("✅ START_OF_TURN: {turn_id}".format(**message))

    # Finalized segment
    def add_segments(message):
        segments = message["segments"]
        for s in segments:
            segments_received.append(s)
            if SHOW_LOG:
                print('🚀 ADD_SEGMENT: {speaker_id} @ "{text}"'.format(**s))

    # EOT detected
    def eot_detected(message):
        nonlocal eot_count
        eot_count += 1
        if SHOW_LOG:
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

    # Check segment count
    expected_count = len(sample.segments)
    actual_count = len(segments_received)

    # Collect assertion errors
    errors: list[str] = []

    # Track which expected segments have been matched
    matched_expected_segments: set[int] = set()

    # Check segment count mismatch
    if expected_count != actual_count:
        errors.append(f"\nExpected {expected_count} segments, but got {actual_count}")

    # Validate each segment
    for idx, segment in enumerate(segments_received):

        # Extract segment data
        text = segment.get("text", "")
        speaker_id = segment.get("speaker_id", "")
        metadata = segment.get("metadata", {})
        start_time = metadata.get("start_time")
        end_time = metadata.get("end_time")

        # Check timing metadata
        if start_time is None or end_time is None:
            errors.append(f"[{idx}] Missing timing metadata for '{text}'")
            continue

        # Margin
        margin = 0.25
        cer_threshold = 0.95

        # Find a matching segment by timing (±50ms tolerance)
        matched_segment = None
        matched_segment_idx = None
        for seg_idx, expected_seg in enumerate(sample.segments):
            if abs(start_time - expected_seg.start_time) <= margin and abs(end_time - expected_seg.end_time) <= margin:
                matched_segment = expected_seg
                matched_segment_idx = seg_idx
                break

        # Validate we have a matching segment
        if not matched_segment:
            errors.append(
                f"  [{idx}] No matching segment for '{text}' " f"(start: {start_time:.2f}s, end: {end_time:.2f}s)"
            )
            continue

        # Mark this expected segment as matched
        matched_expected_segments.add(matched_segment_idx)

        # Check speaker ID
        if speaker_id != matched_segment.speaker_id:
            errors.append(
                f"  [{idx}] Speaker mismatch: expected '{matched_segment.speaker_id}', "
                f"got '{speaker_id}' for '{text}'"
            )

        # Check text ends with punctuation (`.`, `?`, `!`)
        if text and text[-1] not in ".!?":
            errors.append(f"[{idx}] Missing punctuation: '{text}' (should end with . ! or ?)")

        # Check text similarity using normalized comparison
        normalized_received = TextUtils.normalize(text)
        normalized_expected = TextUtils.normalize(matched_segment.text)

        # Calculate the CER
        cer = TextUtils.cer(normalized_expected, normalized_received)

        # Check CER
        if cer > cer_threshold:
            errors.append(
                f"  [{idx}] Text mismatch (CER: {cer:.1%}):\n"
                f"     Expected: '{matched_segment.text}'\n"
                f"     Got:      '{text}'"
            )

    # Check if all expected segments were matched
    unmatched_indices = set(range(expected_count)) - matched_expected_segments
    if unmatched_indices:
        errors.append("\nExpected segments not received:")
        for seg_idx in sorted(unmatched_indices):
            seg = sample.segments[seg_idx]
            errors.append(f"  [{seg_idx}] '{seg.text}' ({seg.start_time:.2f}s - {seg.end_time:.2f}s)")

    # Report all errors
    if errors:
        error_message = "\nSegment validation failed:\n" + "\n".join(errors)
        if SHOW_LOG:
            print(error_message)
        pytest.fail(error_message)
