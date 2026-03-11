import datetime
import json
import os
import re
from dataclasses import field
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import SpeakerFocusConfig
from speechmatics.voice import SpeakerFocusMode
from speechmatics.voice import SpeechSegmentConfig
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import BaseModel
from speechmatics.voice._models import SpeakerSegment

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping diarization tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


class SpeakerTest(BaseModel):
    id: str
    path: str
    sample_rate: int = 16000
    sample_size: int = 2
    segment_regex: list[str] = field(default_factory=list)
    config: Optional[VoiceAgentConfig] = None
    speaker_config: Optional[SpeakerFocusConfig] = None
    speakers_present: list[str] = field(default_factory=list)


SAMPLES: list[SpeakerTest] = [
    SpeakerTest(
        id="multiple_speakers",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["^Welcome to GeoRouter", "Buckingham", "clarify", "Notting Hill", "Rickmansworth"],
        speakers_present=["S1", "S2"],
    ),
    SpeakerTest(
        id="focus_s2",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["^Welcome to GeoRouter", "Buckingham", "clarify", "Notting Hill"],
        speaker_config=SpeakerFocusConfig(
            focus_speakers=["S2"],
        ),
        speakers_present=["S1", "S2"],
    ),
    SpeakerTest(
        id="only_s2",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["Buckingham", "Notting Hill"],
        speaker_config=SpeakerFocusConfig(
            focus_speakers=["S2"],
            focus_mode=SpeakerFocusMode.IGNORE,
        ),
        speakers_present=["S2"],
    ),
    SpeakerTest(
        id="ignore_s2",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["^Welcome to GeoRouter", "clarify", "Rickmansworth"],
        speaker_config=SpeakerFocusConfig(
            ignore_speakers=["S2"],
        ),
        speakers_present=["S1"],
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: f"{s.id}:{s.path}")
async def test_multiple_speakers(sample: SpeakerTest):
    """Test transcription.

    This test will:
        - log messages
        - transcribe audio with diarization config
        - validate the segments received
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Config
    config = sample.config or VoiceAgentConfig(
        end_of_utterance_silence_trigger=1.0,
        max_delay=2.0,
        end_of_utterance_mode=EndOfUtteranceMode.FIXED,
        additional_vocab=[
            AdditionalVocabEntry(content="GeoRouter"),
        ],
        speech_segment_config=SpeechSegmentConfig(emit_sentences=False),
    )

    # Diarization options
    if sample.speaker_config:
        config.speaker_config = sample.speaker_config

    # Standard features
    config.enable_diarization = True
    config.sample_rate = sample.sample_rate

    # Client
    client = await get_client(
        api_key=API_KEY,
        connect=False,
        config=config,
    )

    # Debug
    if SHOW_LOG:
        print(config.to_json(exclude_none=True, exclude_defaults=True, exclude_unset=True, indent=2))
        print(json.dumps(client._transcription_config.to_dict(), indent=2))

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0
    final_segments: list[dict] = []

    # Start time
    start_time = datetime.datetime.now()

    # Bytes logger
    def log_bytes_sent(bytes):
        nonlocal bytes_sent
        bytes_sent += bytes

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        audio_ts = bytes_sent / sample.sample_rate / sample.sample_size
        log = json.dumps({"ts": round(ts, 3), "audio_ts": round(audio_ts, 2), "payload": message})
        messages.append(log)
        if SHOW_LOG:
            print(log)

    # Log final segments
    def log_final_segment(message):
        segments: list[SpeakerSegment] = message["segments"]
        final_segments.extend(segments)

    # Log end of turn
    def log_end_of_turn(message):
        final_segments.extend([{"speaker_id": "--", "text": "_TURN_"}])

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.once(AgentServerMessageType.INFO, log_message)
    client.on(AgentServerMessageType.WARNING, log_message)
    client.on(AgentServerMessageType.ERROR, log_message)
    client.on(AgentServerMessageType.DIAGNOSTICS, log_message)

    # Transcript
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)

    # Turn events
    client.on(AgentServerMessageType.VAD_STATUS, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.START_OF_TURN, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)
    client.on(AgentServerMessageType.END_OF_TURN_PREDICTION, log_message)
    client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)

    # Log ADD_SEGMENT + END_OF_TURN
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)
    client.on(AgentServerMessageType.END_OF_TURN, log_end_of_turn)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")
        log_message({"message": "Sample", **sample.to_dict()})
        log_message({"message": "VoiceAgentConfig", **client._config.to_dict()})
        log_message({"message": "TranscriptionConfig", **client._transcription_config.to_dict()})
        log_message({"message": "AudioFormat", **client._audio_format.to_dict()})

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(
        client,
        sample.path,
        sample_rate=sample.sample_rate,
        sample_size=sample.sample_size,
        progress_callback=log_bytes_sent,
    )

    # Close session
    await client.disconnect()

    # FOOTER
    if SHOW_LOG:
        print("---")
        print()
        print()

    # Print all final_segments
    if SHOW_LOG:
        print("Final segments:")
        for idx, segment in enumerate(final_segments):
            print(f"{idx}: [{segment.get('speaker_id')}] {segment.get('text')}")
        print()

    # Accumulate errors
    errors: list[str] = []

    # Check number of final segments
    if len(final_segments) < len(sample.segment_regex):
        errors.append(f"Expected at least {len(sample.segment_regex)} segments, got {len(final_segments)}")

    # Check final segments against regex
    if SHOW_LOG:
        print("Checking final segments against regex:")
    for idx, _test in enumerate(sample.segment_regex):
        text = final_segments[idx].get("text") if idx < len(final_segments) else None
        match = text and re.search(_test, text, flags=re.IGNORECASE | re.MULTILINE)
        if SHOW_LOG:
            print(f'{idx}: {"✅" if match else "❌"} - `{_test}` -> `{text}`')
        if not match:
            errors.append(f"Segment {idx}: expected /{_test}/ but got '{text}'")

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    if set(speakers) != set(sample.speakers_present):
        errors.append(f"Speakers: expected {set(sample.speakers_present)} but got {set(speakers)}")

    # Report all errors
    assert not errors, "\n".join(errors)
