import datetime
import json
import os
import re
from dataclasses import field
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file
from pydantic import BaseModel

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationFocusMode
from speechmatics.voice import DiarizationSpeakerConfig
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import SpeakerSegment

API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


class SpeakerTest(BaseModel):
    id: str
    path: str
    sample_rate: int = 16000
    sample_size: int = 2
    segment_regex: list[str] = field(default_factory=list)
    config: Optional[VoiceAgentConfig] = None
    speaker_config: Optional[DiarizationSpeakerConfig] = None
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
        speaker_config=DiarizationSpeakerConfig(
            focus_speakers=["S2"],
        ),
        speakers_present=["S1", "S2"],
    ),
    SpeakerTest(
        id="only_s2",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["Buckingham", "Notting Hill"],
        speaker_config=DiarizationSpeakerConfig(
            focus_speakers=["S2"],
            focus_mode=DiarizationFocusMode.IGNORE,
        ),
        speakers_present=["S2"],
    ),
    SpeakerTest(
        id="ignore_s2",
        path="./assets/audio_02_8kHz.wav",
        sample_rate=8000,
        segment_regex=["^Welcome to GeoRouter", "clarify", "Rickmansworth"],
        speaker_config=DiarizationSpeakerConfig(
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
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Config
    config = sample.config or VoiceAgentConfig(
        end_of_utterance_silence_trigger=1.0,
        max_delay=2.0,
        end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
        additional_vocab=[
            AdditionalVocabEntry(content="GeoRouter"),
        ],
    )

    # Diarization options
    if sample.speaker_config:
        config.speaker_config = sample.speaker_config

    # Standard features
    config.enable_diarization = True
    config.sample_rate = sample.sample_rate

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=config,
    )

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

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.once(AgentServerMessageType.INFO, log_message)
    client.on(AgentServerMessageType.WARNING, log_message)
    client.on(AgentServerMessageType.ERROR, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # Log ADD_SEGMENT
    client.on(AgentServerMessageType.ADD_SEGMENT, log_final_segment)

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")
        log_message({"message": "Sample", **sample.model_dump()})
        log_message({"message": "VoiceAgentConfig", **client._config.model_dump()})
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

    # FOOTER
    if SHOW_LOG:
        print("---")
        print()
        print()

    # Check final segments against regex
    for idx, _test in enumerate(sample.segment_regex):
        print(f"`{_test}` -> `{final_segments[idx].get('text')}`")
        assert re.search(_test, final_segments[idx].get("text"), flags=re.IGNORECASE | re.MULTILINE)

    # Check only speakers present
    speakers = [segment.get("speaker_id") for segment in final_segments]
    assert set(speakers) == set(sample.speakers_present)

    # Close session
    await client.disconnect()
    assert not client._is_connected
