import asyncio
import datetime
import json
import os

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AgentClientMessageType
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationKnownSpeaker
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import SpeakerSegment

api_key = os.getenv("SPEECHMATICS_API_KEY")
show_log = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]

speaker_ids: list[DiarizationKnownSpeaker] = []


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
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Client
    client = await get_client(
        api_key=api_key,
        url="wss://preview.rt.speechmatics.com/v1",
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
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
        log = json.dumps({"ts": ts, "audio_ts": audio_ts, "payload": message})
        messages.append(log)
        if show_log:
            print(log)

    # Log speakers result
    def save_speakers_result(message):
        speakers_event_received.set()
        for label, speaker_identifiers in message.get("results", {}).items():
            speaker_ids.append(
                DiarizationKnownSpeaker(
                    label=label,
                    speaker_identifiers=speaker_identifiers,
                )
            )

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)

    # Log SPEAKERS_RESULT
    client.once(AgentServerMessageType.SPEAKERS_RESULT, save_speakers_result)

    # HEADER
    if show_log:
        print()
        print()
        print("---")
        log_message({"message": "VoiceAgentConfig", **client._config.model_dump()})
        log_message({"message": "TranscriptionConfig", **client._transcription_config.to_dict()})
        log_message({"message": "AudioFormat", **client._audio_format.to_dict()})

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, "./assets/audio_02_8kHz.wav", progress_callback=log_bytes_sent)

    # Request the speakers result
    await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS})

    # Wait for the callback with timeout
    try:
        await asyncio.wait_for(speakers_event_received.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("SPEAKERS_RESULT event was not received within 5 seconds of audio finish")

    # FOOTER
    if show_log:
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
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Copy known speakers
    known_speakers = speaker_ids.copy()
    known_speakers[0].label = "Assistant"
    known_speakers[1].label = "John Doe"

    # Client
    client = await get_client(
        api_key=api_key,
        url="wss://preview.rt.speechmatics.com/v1",
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
            known_speakers=known_speakers,
        ),
    )

    # Create an event to track when the callback is called
    final_segments: list[dict] = []

    # Log final segments
    def log_final_segment(message):
        segments: list[SpeakerSegment] = message["segments"]
        final_segments.extend(segments)

    # Add listeners
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, "./assets/audio_02_8kHz.wav")

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    assert set(speakers) == set({"Assistant", "John Doe"})

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
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Copy known speakers
    known_speakers = speaker_ids.copy()
    known_speakers[0].label = "__ASSISTANT__"
    known_speakers[1].label = "John Doe"

    # Client
    client = await get_client(
        api_key=api_key,
        url="wss://preview.rt.speechmatics.com/v1",
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=1.0,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            sample_rate=8000,
            known_speakers=known_speakers,
        ),
    )

    # Create an event to track when the callback is called
    final_segments: list[dict] = []

    # Log final segments
    def log_final_segment(message):
        segments: list[SpeakerSegment] = message["segments"]
        final_segments.extend(segments)

    # Add listeners
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, "./assets/audio_02_8kHz.wav")

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    assert set(speakers) == set({"John Doe"})

    # Close session
    await client.disconnect()
    assert not client._is_connected
