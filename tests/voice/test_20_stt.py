"""Raw RT SDK transcription test using 8kHz audio.

Sends audio_02_8kHz.wav directly via the RT AsyncClient and logs all
server messages (except AUDIO_ADDED) to help debug sample-rate issues.
"""

import asyncio
import datetime
import json
import os
import time

import aiofiles
import pytest

from speechmatics.rt import AsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import ConversationConfig
from speechmatics.rt import ServerMessageType
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import TranscriptionConfig

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping STT tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL = os.getenv("SPEECHMATICS_RT_URL", "wss://eu2.rt.speechmatics.com/v2")
AUDIO_FILE = "./assets/audio_02c_8kHz.wav"
SAMPLE_RATE = 8000
CHUNK_SIZE = 160


@pytest.mark.asyncio
async def test_rt_transcription_8khz():
    """Transcribe 8kHz audio using the RT SDK directly.

    Logs all server messages (except AUDIO_ADDED) to stdout for debugging.
    """

    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Resolve audio file path
    audio_path = os.path.join(os.path.dirname(__file__), AUDIO_FILE)
    assert os.path.exists(audio_path), f"Audio file not found: {audio_path}"

    # RT client
    client = AsyncClient(api_key=API_KEY, url=URL)

    # Logging
    start_time = datetime.datetime.now()
    messages: list[dict] = []

    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        entry = {"ts": round(ts, 3), "payload": message}
        messages.append(entry)
        print(json.dumps(entry))

    # Register listeners for all message types except AUDIO_ADDED
    for msg_type in ServerMessageType:
        if msg_type != ServerMessageType.AUDIO_ADDED:
            client.on(msg_type, log_message)

    # Audio format
    audio_format = AudioFormat(
        encoding=AudioEncoding.PCM_S16LE,
        sample_rate=SAMPLE_RATE,
        chunk_size=CHUNK_SIZE,
    )

    # Transcription config
    transcription_config = TranscriptionConfig(
        language="en",
        operating_point="enhanced",
        diarization="speaker",
        additional_vocab=[{"content": "GeoRouter"}],
        enable_entities=False,
        audio_filtering_config={"volume_threshold": 0.0},
        max_delay=2.0,
        max_delay_mode="flexible",
        enable_partials=True,
        speaker_diarization_config=SpeakerDiarizationConfig(
            speaker_sensitivity=0.5,
            prefer_current_speaker=False,
        ),
        conversation_config=ConversationConfig(
            end_of_utterance_silence_trigger=0.25,
        ),
    )

    # Debug
    print(json.dumps(transcription_config.to_dict(), indent=2))
    print(json.dumps(audio_format.to_dict(), indent=2))

    # Start session
    await client.start_session(
        audio_format=audio_format,
        transcription_config=transcription_config,
    )

    # Send audio in real-time
    delay = CHUNK_SIZE / SAMPLE_RATE / 2  # 2 bytes per sample (int16)
    async with aiofiles.open(audio_path, "rb") as f:
        await f.seek(44)  # skip WAV header
        next_time = time.perf_counter() + delay
        while True:
            chunk = await f.read(CHUNK_SIZE)
            if not chunk:
                break
            await client.send_audio(chunk)
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            next_time += delay

    # Stop session and wait for EndOfTranscript
    await client.stop_session()

    # Basic assertions
    assert len(messages) > 0, "No messages received from server"

    # Check we got at least one final transcript
    finals = [m for m in messages if m["payload"].get("message") == "AddTranscript"]
    assert len(finals) > 0, "No final transcripts received"

    print(f"\n--- Summary: {len(messages)} messages, {len(finals)} final transcripts ---")
