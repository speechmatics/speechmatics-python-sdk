"""Raw WebSocket transcription test using 8kHz audio.

Bypasses the RT SDK entirely and uses raw websockets to connect to the
Speechmatics endpoint. This isolates whether issues are server-side or
SDK-related.
"""

import asyncio
import datetime
import json
import os
import time
import wave

import pytest
import websockets

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping raw STT tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
URL = os.getenv("SPEECHMATICS_RT_URL", "wss://eu2.rt.speechmatics.com/v2")
AUDIO_FILE = os.getenv("AUDIO_FILE", "./assets/audio_01_16kHz.wav")
CHUNK_SIZE = 160
RECV_TIMEOUT = 5.0


@pytest.mark.asyncio
async def test_raw_ws_transcription_8khz():
    """Transcribe 8kHz audio using raw WebSocket (no SDK).

    Logs all server messages (except AudioAdded) to stdout for debugging.
    """

    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Resolve audio file path
    audio_path = os.path.join(os.path.dirname(__file__), AUDIO_FILE)
    assert os.path.exists(audio_path), f"Audio file not found: {audio_path}"

    # Load audio from WAV file
    with wave.open(audio_path, "rb") as wf:
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()
        n_channels = wf.getnchannels()
        audio_data = wf.readframes(wf.getnframes())

    # Only mono audio is supported for this test
    if n_channels != 1:
        pytest.skip(f"Skipping: expected mono audio, got {n_channels} channels")

    # Only 16-bit PCM is supported
    if sample_width != 2:
        pytest.skip(f"Skipping: expected 16-bit audio, got {sample_width * 8}-bit")

    # Debug
    print(f"processing audio file: {audio_path}")
    print(f" -> WAV: {sample_rate}Hz, {sample_width * 8}-bit, {n_channels}ch, {len(audio_data)} bytes")

    # Build the StartRecognition message sent over the WebSocket.
    # This is the exact JSON the server expects as the first message.
    start_recognition = {
        "message": "StartRecognition",
        "audio_format": {
            "type": "raw",
            "encoding": "pcm_s16le",
            "sample_rate": sample_rate,
        },
        "transcription_config": {
            "language": "en",
            "operating_point": "standard",
            "diarization": "speaker",
            "additional_vocab": [{"content": "GeoRouter"}],
            "enable_entities": False,
            "audio_filtering_config": {"volume_threshold": 0.0},
            "max_delay": 2.0,
            "max_delay_mode": "flexible",
            "enable_partials": True,
            "speaker_diarization_config": {
                "speaker_sensitivity": 0.5,
                "prefer_current_speaker": False,
            },
            "conversation_config": {
                "end_of_utterance_silence_trigger": 0.25,
            },
        },
    }

    # Log the config for debugging
    print(json.dumps(start_recognition, indent=2))

    # Track wall-clock time for log timestamps
    start_time = datetime.datetime.now()
    messages: list[dict] = []

    # Log messages from WebSocket
    def log_message(msg: dict):
        """Append message to buffer and print with wall-clock offset."""
        ts = (datetime.datetime.now() - start_time).total_seconds()
        entry = {"ts": round(ts, 3), "payload": msg}
        messages.append(entry)
        print(json.dumps(entry))

    # Connect via raw WebSocket with Bearer token auth
    async with websockets.connect(
        URL,
        additional_headers={"Authorization": f"Bearer {API_KEY}"},
    ) as ws:

        # First message must be StartRecognition
        await ws.send(json.dumps(start_recognition))

        # The server may send Info messages before RecognitionStarted,
        # so we loop until we see the expected handshake response
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
            if isinstance(raw, str):
                msg = json.loads(raw)
                log_message(msg)
                if msg.get("message") == "RecognitionStarted":
                    break

        # Signalled when the server sends EndOfTranscript
        eot_event = asyncio.Event()

        async def rx():
            """Background task to receive and log server messages."""
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
                    if isinstance(raw, str):
                        msg = json.loads(raw)
                        # AudioAdded is high-frequency and not useful for debugging
                        if msg.get("message") != "AudioAdded":
                            log_message(msg)
                        if msg.get("message") == "EndOfTranscript":
                            eot_event.set()
                            break
                except (asyncio.TimeoutError, websockets.ConnectionClosed):
                    break

        # RX task
        rx_task = asyncio.create_task(rx())

        # Stream audio from the in-memory buffer at real-time pace.
        # delay = duration of one chunk in seconds (bytes / rate / width)
        delay = CHUNK_SIZE / sample_rate / sample_width
        offset = 0
        next_time = time.perf_counter() + delay
        while offset < len(audio_data):
            chunk = audio_data[offset : offset + CHUNK_SIZE]
            offset += CHUNK_SIZE
            await ws.send(chunk)
            # Pace sending to match real-time playback speed
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            next_time += delay

        # Signal the server that no more audio will be sent
        await ws.send(json.dumps({"message": "EndOfStream", "last_seq_no": 0}))

        # Wait for the server to finish processing and send EndOfTranscript
        await asyncio.wait_for(eot_event.wait(), timeout=RECV_TIMEOUT)

        # Clean up the background receiver
        rx_task.cancel()
        try:
            await rx_task
        except asyncio.CancelledError:
            pass

    # Verify we received messages
    assert len(messages) > 0, "No messages received from server"

    # Verify at least one final transcript was produced
    finals = [m for m in messages if m["payload"].get("message") == "AddTranscript"]
    assert len(finals) > 0, "No final transcripts received"

    # Final report
    print(f"\n--- Summary: {len(messages)} messages, {len(finals)} final transcripts ---")
