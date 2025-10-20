import asyncio
import logging
import os
import json

from speechmatics.rt import (
    AsyncClient,
    OperatingPoint,
    TranscriptionConfig,
    ServerMessageType,
)


logging.basicConfig(level=logging.INFO)


speakers: list[dict] = []


async def generate_ids(voice_file: str) -> None:
    """Run async transcription example."""

    transcription_config = TranscriptionConfig(
        operating_point=OperatingPoint.ENHANCED,
        diarization="speaker",
    )

    # Initialize client with API key from environment
    async with AsyncClient() as client:
        try:
            @client.on(ServerMessageType.SPEAKERS_RESULT)
            def handle_speakers_result(msg):
                new_speakers = msg.get('speakers', [])
                new_speakers[0]["label"] = voice_file
                speakers.append(new_speakers[0])

            # Transcribe audio file
            with open(os.path.join(voices_folder, voice_file), "rb") as audio_file:
                await client.transcribe(
                    audio_file,
                    transcription_config=transcription_config,
                    get_speakers=True,
                )
        except Exception as e:
            print(f"Transcription error: {e}")


if __name__ == "__main__":
    voices_folder = "./examples/rt/async/speaker_id/voices"
    voice_files = [f for f in os.listdir(voices_folder) if os.path.isfile(os.path.join(voices_folder, f))]

    for voice_file in voice_files:
        asyncio.run(generate_ids(voice_file))

    with open('./speakers.json', 'w') as f:
        json.dump(speakers, f)
