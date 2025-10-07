import asyncio
import json
import os
import shutil
import wave
from typing import Optional

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import TranscriptionUpdatePreset


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
async def test_transcribe_and_slice():
    """Load, transcribe and slice an audio file"""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Input file
    file = "audio_04_16kHz"

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
            data = await client._audio_buffer.get_frames(start_time, end_time, fade_out=0.01)
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
            end_of_utterance_silence_trigger=0.5,
            max_delay=2.0,
            end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
            enable_diarization=True,
            audio_buffer_length=8.0,
            transcription_update_preset=TranscriptionUpdatePreset.COMPLETE,
        ),
    )

    # Check audio buffer is enabled
    assert client._audio_buffer

    # Log raw messages
    def log_raw(message):
        print(message)

    # Final segment
    def final_segment(message):
        print(message)
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
                        prefix=f"final_{speaker_id}",
                        json_data=json.dumps(segment, indent=2),
                    )
                )

        except Exception as e:
            exceptions.append(e)

    # Partial segment
    def partial_segment(message):
        print(message)
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
                        prefix=f"partial_{speaker_id}",
                        json_data=json.dumps(segment, indent=2),
                    )
                )

        except Exception as e:
            exceptions.append(e)

    # Add listeners
    # client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_raw)
    # client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_raw)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, partial_segment)
    client.on(AgentServerMessageType.ADD_SEGMENT, final_segment)

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Send audio
    await send_audio_file(client, input_file)

    # Close session
    await client.disconnect()
    assert not client._is_connected

    # Check exceptions
    assert not exceptions
