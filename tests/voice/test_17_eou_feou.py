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
from speechmatics.voice._models import VoiceActivityConfig
from speechmatics.voice._models import VoiceAgentConfig
from speechmatics.voice._presets import VoiceAgentConfigPreset
from speechmatics.voice._utils import TextUtils

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping smart turn tests in CI")
pytestmark = pytest.mark.skipif(API_KEY is None, reason="Skipping when no API key is provided")


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


# Audio files and expected segments
SAMPLES: TranscriptionTests = TranscriptionTests.from_dict(
    {
        "samples": [
            # {
            #     "id": "07b",
            #     "path": "./assets/audio_07b_16kHz.wav",
            #     "sample_rate": 16000,
            #     "language": "en",
            #     "segments": [
            #         {"text": "Hello.", "start_time": 1.05, "end_time": 1.67},
            #         {"text": "Tomorrow.", "start_time": 3.5, "end_time": 4.1},
            #         {"text": "Wednesday.", "start_time": 6.05, "end_time": 6.73},
            #         {"text": "Of course. That's fine.", "start_time": 8.8, "end_time": 9.96},
            #         {"text": "Behind.", "start_time": 12.03, "end_time": 12.73},
            #         {"text": "In front.", "start_time": 14.84, "end_time": 15.52},
            #         {"text": "Do you think so?", "start_time": 17.54, "end_time": 18.32},
            #         {"text": "Brilliant.", "start_time": 20.55, "end_time": 21.08},
            #         {"text": "Banana.", "start_time": 22.98, "end_time": 23.53},
            #         {"text": "When?", "start_time": 25.49, "end_time": 25.96},
            #         {"text": "Today.", "start_time": 27.66, "end_time": 28.15},
            #         {"text": "This morning.", "start_time": 29.91, "end_time": 30.47},
            #         {"text": "Goodbye.", "start_time": 32.21, "end_time": 32.68},
            #     ],
            # },
            # {
            #     "id": "08",
            #     "path": "./assets/audio_08_16kHz.wav",
            #     "sample_rate": 16000,
            #     "language": "en",
            #     "segments": [
            #         {"text": "Hello.", "start_time": 0.4, "end_time": 0.75},
            #         {"text": "Goodbye.", "start_time": 2.12, "end_time": 2.5},
            #         {"text": "Banana.", "start_time": 3.84, "end_time": 4.27},
            #         {"text": "Breakaway.", "start_time": 5.62, "end_time": 6.42},
            #         {"text": "Before.", "start_time": 7.76, "end_time": 8.16},
            #         {"text": "After.", "start_time": 9.56, "end_time": 10.05},
            #     ],
            # },
            {
                "id": "09",
                "path": "./assets/audio_09_16kHz.wav",
                "sample_rate": 16000,
                "language": "en",
                "segments": [
                    {"text": "How are you getting on, buddy?", "start_time": 0.74, "end_time": 1.70},
                ],
            },
        ]
    }
)

# VAD delay
VAD_DELAY_S: list[float] = [0.18, 0.22]

# Endpoints
ENDPOINTS: list[str] = [
    # "wss://eu-west-2-research.speechmatics.cloud/v2",
    "wss://eu.rt.speechmatics.com/v2",
    # "wss://us.rt.speechmatics.com/v2",
]

# Margin
MARGIN_S = 0.5
CER_THRESHOLD = 0.15


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("sample", SAMPLES.samples, ids=lambda s: f"{s.id}:{s.path}")
async def test_turn_fixed_eou(endpoint: str, sample: TranscriptionTest):
    """Test transcription and prediction using FIXED without FEOU"""

    # Config
    config = VoiceAgentConfigPreset.FIXED()

    # Dump config
    if SHOW_LOG:
        print(f"\nTest `{sample.path}` with preset FIXED -> {endpoint}\n")
        print(config.to_json(exclude_defaults=True, exclude_none=True, exclude_unset=True, indent=2))

    # Run test
    await run_test(endpoint, sample, config)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("sample", SAMPLES.samples, ids=lambda s: f"{s.id}")
@pytest.mark.parametrize("vad_delay", VAD_DELAY_S)
async def test_turn_adaptive_feou(endpoint: str, sample: TranscriptionTest, vad_delay: float):
    """Test transcription and prediction using ADAPTIVE with FEOU"""

    # Config
    config = VoiceAgentConfigPreset.ADAPTIVE(
        VoiceAgentConfig(
            vad_config=VoiceActivityConfig(enabled=True, silence_duration=vad_delay),
        )
    )

    # Dump config
    if SHOW_LOG:
        print(f"\nTest `{sample.path}` with preset ADAPTIVE with VAD delay of {vad_delay}s -> {endpoint}\n")
        print(config.to_json(exclude_defaults=True, exclude_none=True, exclude_unset=True, indent=2))

    # Run test
    await run_test(endpoint, sample, config)


async def run_test(endpoint: str, sample: TranscriptionTest, config: VoiceAgentConfig):
    """Run a test with the given sample and config."""

    # Padding
    if SHOW_LOG:
        print("--- TEST START ---")
        print()

    # Client
    client = await get_client(
        url=endpoint,
        api_key=API_KEY,
        connect=False,
        config=config,
    )

    # Results
    eot_count: int = 0
    segments_received: list[dict] = []
    partials_received: set[str] = set()
    finals_received: set[str] = set()

    # Start time
    start_time = datetime.datetime.now()

    # Finalized segment
    def add_segments(message):
        segments = message["segments"]
        for s in segments:
            segments_received.append(s)

    # EOT detected
    def eot_detected(message):
        nonlocal eot_count
        eot_count += 1

    # Extract words
    def extract_words(message) -> list[str]:
        return [
            alt.get("content", None)
            for result in message.get("results", [])
            if result.get("type") == "word"
            for alt in result.get("alternatives", [])
        ]

    # Partials
    def rx_partial(message):
        words = extract_words(message)
        partials_received.update(w.lower() for w in words if w)

    # Finals
    def rx_finals(message):
        words = extract_words(message)
        finals_received.update(w.lower() for w in words if w)

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
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, rx_partial)
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, rx_partial)

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
        print(f"\nPartial words = {json.dumps(sorted(partials_received), indent=2)}\n")
        print(f"\nFinal words = {json.dumps(sorted(finals_received), indent=2)}\n")
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

        print(f"[{idx}] `{normalized_expected}` -> `{normalized_received}` (CER: {cer:.1%})")

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
        error_message = "\n=== ERRORS ===\n" + "\n".join(errors)
        if SHOW_LOG:
            print(error_message)
        pytest.fail(error_message)

    # Padding
    if SHOW_LOG:
        print()
        print("--- TEST END ---")
        print()
