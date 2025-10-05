import asyncio
import json
import os
import random
import shutil
import wave
from typing import Optional

import aiofiles
import pytest
from _utils import get_client
from _utils import send_audio_file
from _utils import send_silence

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._audio import AudioBuffer


@pytest.mark.asyncio
async def test_clean_tmp():
    """Clear tmp directory"""

    # Output directory
    tmp_dir = os.path.join(os.path.dirname(__file__), "./.tmp")

    # Clean tmp
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Re-create
    os.makedirs(tmp_dir, exist_ok=True)
    assert os.path.exists(tmp_dir)


@pytest.mark.asyncio
async def test_buffer():
    """Test AudioBuffer"""

    # Audio info
    sample_rate = 16000
    sample_width = 2
    frame_size = 160
    frame_bytes = frame_size * sample_width

    # Create buffer
    buffer = AudioBuffer(sample_rate=sample_rate, frame_size=frame_size, sample_width=sample_width, total_seconds=10.0)

    # Check zeros
    assert buffer.total_frames == 0
    assert buffer.total_time == 0.0
    assert buffer.size == 0

    # Add in 20 seconds of data
    for _ in range(int(20.0 * sample_rate / frame_size)):
        await buffer.put_frame(b"\x00" * frame_bytes)

    # Check values
    assert buffer.total_frames == int(20.0 * sample_rate / frame_size)
    assert buffer.total_time == 20.0
    assert buffer.size == int(10.0 * sample_rate / frame_size)

    # Check frame >< time conversion
    assert buffer._get_frame_from_time(buffer._get_time_from_frame(1234)) == 1234

    # Get data from more than 10 seconds ago
    data = await buffer.get_frames(2.5, 7.5)
    assert len(data) == 0

    # Get a 5 second slice from 12.5 seconds in
    data = await buffer.get_frames(12.5, 17.5)
    assert len(data) == int(5.0 * sample_rate / frame_size) * frame_bytes


@pytest.mark.asyncio
async def test_buffer_bytes():
    """Test AudioBuffer with byte payloads"""

    # Audio info
    sample_rate = 16000
    sample_width = 2
    frame_size = 160
    frame_bytes = frame_size * sample_width

    # Create buffer
    buffer = AudioBuffer(sample_rate=sample_rate, frame_size=frame_size, sample_width=sample_width, total_seconds=10.0)

    # Check zeros
    assert buffer.total_frames == 0
    assert buffer.total_time == 0.0
    assert buffer.size == 0

    # 20 seconds of frames
    twenty_second_frame_count = int(20.0 * sample_rate / frame_size)

    # Fill with random payloads of data
    while buffer.total_frames < twenty_second_frame_count - 1:
        await buffer.put_bytes(b"\x00" * random.randint(1, frame_bytes))

    # Add one last frame of zeros
    await buffer.put_frame(b"\xff" * frame_bytes)

    # Check values
    assert buffer.total_frames == int(20.0 * sample_rate / frame_size)
    assert buffer.total_time == 20.0
    assert buffer.size == int(10.0 * sample_rate / frame_size)

    # Check frame >< time conversion
    assert buffer._get_frame_from_time(buffer._get_time_from_frame(1234)) == 1234

    # Get data from more than 10 seconds ago
    data = await buffer.get_frames(2.5, 7.5)
    assert len(data) == 0

    # Get a 5 second slice from 12.5 seconds in
    data = await buffer.get_frames(12.5, 17.5)
    assert len(data) == int(5.0 * sample_rate / frame_size) * frame_bytes

    # Get most recent frame
    start_time = buffer.total_time - (frame_size / sample_rate)
    end_time = buffer.total_time

    # Extract data
    data = await buffer.get_frames(start_time, end_time)

    # Test
    assert len(data) == int((end_time - start_time) * sample_rate / frame_size) * frame_bytes


@pytest.mark.asyncio
async def test_load_audio_file():
    """Test loading audio file into buffer"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # File
    file = "audio_01_16kHz"

    # Check file exists
    input_file = os.path.join(os.path.dirname(__file__), f"./assets/{file}.wav")
    assert os.path.exists(input_file)

    # Output file
    output_file = os.path.join(os.path.dirname(__file__), f"./.tmp/{file}_slice.wav")
    output_folder = os.path.dirname(output_file)
    os.makedirs(output_folder, exist_ok=True)
    assert os.path.exists(output_folder)

    # Audio info
    sample_rate = 16000
    sample_width = 2
    frame_size = 160
    frame_bytes = frame_size * sample_width

    # Create buffer
    buffer = AudioBuffer(sample_rate=sample_rate, frame_size=frame_size, sample_width=sample_width, total_seconds=35.0)

    # Load the file
    async with aiofiles.open(input_file, "rb") as wav_file:
        await wav_file.seek(44)
        while True:
            chunk = await wav_file.read(frame_bytes)
            if not chunk:
                break
            await buffer.put_frame(chunk)

    # Slice
    slice_start = 3.52
    slice_end = 6.96

    # Get a 5 second slice
    data = await buffer.get_frames(slice_start, slice_end)

    # Lengths - calculate expected using same logic as buffer
    start_frame = buffer._get_frame_from_time(slice_start)
    end_frame = buffer._get_frame_from_time(slice_end)

    # Check length
    assert len(data) == (end_frame - start_frame) * frame_bytes

    # Write bytes to a temporary WAV file
    with wave.open(output_file, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(data)


@pytest.mark.asyncio
async def test_transcribe_and_slice():
    """Load, transcribe and slice an audio file"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Input file
    file = "audio_01_16kHz"

    # Check file exists
    input_file = os.path.join(os.path.dirname(__file__), f"./assets/{file}.wav")
    assert os.path.exists(input_file)

    # Output directory
    output_folder = os.path.join(os.path.dirname(__file__), "./.tmp")
    os.makedirs(output_folder, exist_ok=True)
    assert os.path.exists(output_folder)

    # Exceptions
    exceptions: Exception = []

    # Save a slice
    async def save_slice(
        start_time: float, end_time: float, prefix: str = "slice", json_data: Optional[str] = None
    ) -> None:
        try:
            output_file = os.path.join(output_folder, f"{file}_{prefix}_{start_time:.2f}_{end_time:.2f}")
            data = await client._audio_buffer.get_frames(start_time, end_time)
            with wave.open(f"{output_file}.wav", "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(client._audio_buffer._sample_rate)
                wav_file.writeframes(data)
            if json_data:
                with open(f"{output_file}.json", "w") as json_file:
                    json_file.write(json_data)
        except Exception as e:
            exceptions.append(e)

    # Client
    client = await get_client(
        api_key=api_key,
        connect=False,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=0.2,
            max_delay=0.7,
            end_of_utterance_mode=EndOfUtteranceMode.FIXED,
            enable_diarization=True,
            enable_audio_buffer=True,
            dditional_vocab=[
                AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"]),
            ],
        ),
    )

    # Check audio buffer is enabled
    assert client._audio_buffer

    # Bytes logger
    def final_segment(message):
        try:
            segments = message.get("segments", [])
            assert segments

            for segment in segments:
                start_time = segment["start_time"]
                end_time = segment["end_time"]
                speaker_id = segment["speaker_id"]
                asyncio.create_task(
                    save_slice(
                        start_time=start_time,
                        end_time=end_time,
                        prefix=speaker_id,
                        json_data=json.dumps(segment, indent=2),
                    )
                )

        except Exception as e:
            exceptions.append(e)

    # Add listeners
    client.on(AgentServerMessageType.ADD_SEGMENT, final_segment)

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Send audio
    await send_audio_file(client, input_file)
    await send_silence(client, 2.0)

    # Close session
    await client.disconnect()
    assert not client._is_connected

    # Check exceptions
    assert not exceptions
