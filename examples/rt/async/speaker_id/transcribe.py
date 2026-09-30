import asyncio
import logging
import json

from speechmatics.rt import SpeakerIdentifier
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import (
    AsyncClient,
    OperatingPoint,
    TranscriptionConfig,
    ServerMessageType
)


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Run async transcription example."""

    with open('./speakers.json') as f:
        speaker_identifiers = [SpeakerIdentifier(**s) for s in json.load(f)]

    transcription_config = TranscriptionConfig(
        operating_point=OperatingPoint.ENHANCED,
        diarization="speaker",
        max_delay=4,
        speaker_diarization_config=SpeakerDiarizationConfig(
            speakers=speaker_identifiers,
        )
    )

    # Initialize client with API key from environment
    async with AsyncClient() as client:
        try:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_finals(msg):
                print(f"Final: {msg['metadata']['speaker']} {msg['metadata']['transcript']}")

            # Transcribe audio file
            with open("./examples/conversation.wav", "rb") as audio_file:
                await client.transcribe(
                    audio_file,
                    transcription_config=transcription_config,
                )
        except Exception as e:
            print(f"Transcription error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
