import asyncio
import datetime
import json
import os
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentClientMessageType
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import SpeakerIdentifier
from speechmatics.voice import SpeechSegmentConfig
from speechmatics.voice import SpeechSegmentEmitMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import SpeakerSegment

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping speaker id tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL: Optional[str] = os.getenv("SPEECHMATICS_SERVER_URL", "wss://preview.rt.speechmatics.com/v2")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]

# List of know speakers during tests
speaker_ids: list[SpeakerIdentifier] = []


@pytest.mark.asyncio
async def test_extract_speaker_ids():
    """Test speaker id extraction.

    This test will:
        - transcribe audio with diarization config
        - get speaker ids for the two speakers
        - uses legacy format until out of preview!
        - this MUST use a preview endpoint
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=API_KEY,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
            additional_vocab=[
                AdditionalVocabEntry(content="GeoRouter"),
            ],
        ),
    )

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0

    # Flag
    speakers_event_received = asyncio.Event()

    # Start time
    start_time = datetime.datetime.now()

    # Bytes logger
    def log_bytes_sent(bytes):
        nonlocal bytes_sent
        bytes_sent += bytes

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        audio_ts = bytes_sent / 8000
        log = json.dumps({"ts": round(ts, 3), "audio_ts": round(audio_ts, 2), "payload": message})
        messages.append(log)
        if SHOW_LOG:
            print(log)

    # Log speakers result
    def save_speakers_result(message):
        for speaker in message.get("speakers", []):
            label: str = speaker.get("label")
            speaker_identifiers: list[str] = speaker.get("speaker_identifiers", [])

            if not label or not speaker_identifiers:
                continue

            speaker_ids.append(
                SpeakerIdentifier(
                    label=label,
                    speaker_identifiers=speaker_identifiers,
                )
            )

        speakers_event_received.set()

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)

    # Log SPEAKERS_RESULT
    client.once(AgentServerMessageType.SPEAKERS_RESULT, save_speakers_result)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")
        log_message({"message": "VoiceAgentConfig", **client._config.model_dump()})
        log_message({"message": "TranscriptionConfig", **client._transcription_config.to_dict()})
        log_message({"message": "AudioFormat", **client._audio_format.to_dict()})

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip(f"Failed to connect to server: {URL}")

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, "./assets/audio_02_8kHz.wav", sample_rate=8000, progress_callback=log_bytes_sent)

    # Request the speakers result
    await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS})

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(speakers_event_received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("SPEAKERS_RESULT event was not received within 5 seconds of audio finish")

    # FOOTER
    if SHOW_LOG:
        print("---")
        print()
        print()

    # Check speaker IDs
    assert speaker_ids
    assert len(speaker_ids) == 2

    # Close session
    await client.disconnect()
    assert not client._is_connected


@pytest.mark.asyncio
async def test_known_speakers():
    """Test using known speakers.

    This test will:
        - use known speakers
        - check names for speakers
        - this MUST use a preview endpoint
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Copy known speakers
    known_speakers = speaker_ids.copy()
    known_speakers[0].label = "Assistant"
    known_speakers[1].label = "John Doe"

    # Client
    client = await get_client(
        api_key=API_KEY,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
            known_speakers=known_speakers,
            speech_segment_config=SpeechSegmentConfig(emit_mode=SpeechSegmentEmitMode.ON_END_OF_TURN),
            additional_vocab=[
                AdditionalVocabEntry(content="GeoRouter"),
            ],
        ),
    )

    # Finalised segments
    final_segments: list[dict] = []

    # Log final segments
    def log_final_segment(message):
        segments: list[SpeakerSegment] = message["segments"]
        final_segments.extend(segments)

    # Add listeners
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip(f"Failed to connect to server: {URL}")

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(
        client,
        "./assets/audio_02_8kHz.wav",
        sample_rate=8000,
    )

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    assert set(speakers) == set({"Assistant", "John Doe"})

    # Should be 5 segments
    assert len(final_segments) == 5

    # Close session
    await client.disconnect()
    assert not client._is_connected


@pytest.mark.asyncio
async def test_ignoring_assistant():
    """Test ignoring the assistant.

    This test will:
        - use known speakers
        - set assistant to `__ASSISTANT__`
        - this MUST use a preview endpoint
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Copy known speakers
    known_speakers = speaker_ids.copy()
    known_speakers[0].label = "__ASSISTANT__"
    known_speakers[1].label = "John Doe"

    # Client
    client = await get_client(
        api_key=API_KEY,
        url=URL,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
            known_speakers=known_speakers,
            speech_segment_config=SpeechSegmentConfig(emit_mode=SpeechSegmentEmitMode.ON_END_OF_TURN),
            additional_vocab=[
                AdditionalVocabEntry(content="GeoRouter"),
            ],
        ),
    )

    # Finalised segments
    final_segments: list[dict] = []

    # Log final segments
    def log_final_segment(message):
        segments: list[SpeakerSegment] = message["segments"]
        final_segments.extend(segments)

    # Add listeners
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)

    # Connect
    try:
        await client.connect()
    except Exception:
        pytest.skip(f"Failed to connect to server: {URL}")

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(
        client,
        "./assets/audio_02_8kHz.wav",
        sample_rate=8000,
    )

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    assert set(speakers) == set({"John Doe"})

    # Should be only 2 segments
    assert len(final_segments) == 2

    # No segment should contain `Rickmansworth`
    for segment in final_segments:
        assert "Rickmansworth" not in segment.get("text", "")

    # Close session
    await client.disconnect()
    assert not client._is_connected
