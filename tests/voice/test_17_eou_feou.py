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
from speechmatics.voice._models import EndOfTurnConfig
from speechmatics.voice._models import VoiceActivityConfig
from speechmatics.voice._models import VoiceAgentConfig
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
    start_time: float = 0.0
    end_time: float = 0.0


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
                "id": "07b",
                "path": "./assets/audio_07b_16kHz.wav",
                "sample_rate": 16000,
                "language": "en",
                "segments": [
                    {"text": "Hello.", "start_time": 1.05, "end_time": 1.67},
                    {"text": "Tomorrow.", "start_time": 3.5, "end_time": 4.1},
                    {"text": "Wednesday.", "start_time": 6.05, "end_time": 6.73},
                    {"text": "Of course. That's fine.", "start_time": 8.8, "end_time": 9.96},
                    {"text": "Behind.", "start_time": 12.03, "end_time": 12.73},
                    {"text": "In front.", "start_time": 14.84, "end_time": 15.52},
                    {"text": "Do you think so?", "start_time": 17.54, "end_time": 18.32},
                    {"text": "Brilliant.", "start_time": 20.55, "end_time": 21.08},
                    {"text": "Banana.", "start_time": 22.98, "end_time": 23.53},
                    {"text": "When?", "start_time": 25.49, "end_time": 25.96},
                    {"text": "Today.", "start_time": 27.66, "end_time": 28.15},
                    {"text": "This morning.", "start_time": 39.91, "end_time": 30.47},
                    {"text": "Goodbye.", "start_time": 32.21, "end_time": 32.68},
                ],
            },
            {
                "id": "08",
                "path": "./assets/audio_08_16kHz.wav",
                "sample_rate": 16000,
                "language": "en",
                "segments": [
                    {"text": "Hello.", "start_time": 0.4, "end_time": 0.75},
                    {"text": "Goodbye.", "start_time": 2.12, "end_time": 2.5},
                    {"text": "Banana.", "start_time": 3.84, "end_time": 4.27},
                    {"text": "Breakaway.", "start_time": 5.62, "end_time": 6.42},
                    {"text": "Before.", "start_time": 7.76, "end_time": 8.16},
                    {"text": "After.", "start_time": 9.56, "end_time": 10.05},
                ],
            },
        ]
    }
)

# VAD_DELAYS: list[float] = [0.1, 0.15, 0.18, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6]
# VAD_DELAYS: list[float] = [0.3, 0.4]
# VAD_DELAYS: list[float] = [0.4]# VAD_DELAYS: list[float] = [0.4]
# VAD_DELAYS: list[float] = [0.18]
VAD_DELAYS: list[float] = [0.18]

# Margin
MARGIN_S = 0.5
CER_THRESHOLD = 0.95


@pytest.mark.asyncio
@pytest.mark.parametrize("delay", VAD_DELAYS)
@pytest.mark.parametrize("sample", SAMPLES.samples, ids=lambda s: f"{s.id}:{s.path}")
async def test_turn_feou(sample: TranscriptionTest, delay: float):
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

    # Config
    config = VoiceAgentConfigPreset.ADAPTIVE(
        VoiceAgentConfig(
            vad_config=VoiceActivityConfig(enabled=True, silence_duration=delay),
            end_of_turn_config=EndOfTurnConfig(min_end_of_turn_delay=0.025, use_forced_eou=True),
        )
    )
    # config = VoiceAgentConfigPreset.FIXED()
    # config = VoiceAgentConfigPreset.ADAPTIVE()

    # Dump config
    if SHOW_LOG:
        print(f"\nTest with {delay}s silence duration\n")
        print(config.to_json(exclude_defaults=True, exclude_none=True, exclude_unset=True, indent=2))

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=config,
    )

    # Finalized segment
    def add_segments(message):
        segments = message["segments"]
        for s in segments:
            segments_received.append(s)

    # EOT detected
    def eot_detected(message):
        nonlocal eot_count
        eot_count += 1

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        log = json.dumps({"ts": round(ts, 3), "payload": message})
        print(log)

    # Add listeners
    if SHOW_LOG:
        message_types = [m for m in AgentServerMessageType if m != AgentServerMessageType.AUDIO_ADDED]
        # message_types = [AgentServerMessageType.ADD_SEGMENT]
        for message_type in message_types:
            client.on(message_type, log_message)

    # Custom listeners
    client.on(AgentServerMessageType.END_OF_TURN, eot_detected)
    client.on(AgentServerMessageType.ADD_SEGMENT, add_segments)

    # HEADER
    if SHOW_LOG:
        print()
        print("--- AUDIO START ---")
        print()

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip("Failed to connect to server")

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, sample.path)

    # Close session
    await client.disconnect()
    assert not client._is_connected

    # FOOTER
    if SHOW_LOG:
        print()
        print("--- AUDIO END ---")
        print()

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

        # Find a matching segment by timing (±50ms tolerance)
        matched_segment = None
        matched_segment_idx = None
        for seg_idx, expected_seg in enumerate(sample.segments):
            if (
                abs(start_time - expected_seg.start_time) <= MARGIN_S
                and abs(end_time - expected_seg.end_time) <= MARGIN_S
            ):
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
        if cer > CER_THRESHOLD:
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
