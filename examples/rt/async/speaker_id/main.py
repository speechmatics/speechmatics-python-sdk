import asyncio
import logging

from speechmatics.rt import ServerMessageType
from speechmatics.rt import (
    AsyncClient,
    AudioEncoding,
    AudioFormat,
    OperatingPoint,
    TranscriptionConfig,
)


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Run async transcription example."""

    transcription_config = TranscriptionConfig(
        max_delay=0.8,
        operating_point=OperatingPoint.ENHANCED,
        diarization="speaker",
    )

    # Initialize client with API key from environment
    async with AsyncClient() as client:
        try:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_finals(msg):
                print(f"Final: {msg['metadata']['transcript']}")

            @client.on(ServerMessageType.SPEAKERS_RESULT)
            def handle_speakers_result(msg):
                print(msg)

            # Transcribe audio file
            with open("./examples/example.wav", "rb") as audio_file:
                await client.transcribe(
                    audio_file,
                    transcription_config=transcription_config,
                    get_speakers=True,
                )
        except Exception as e:
            print(f"Transcription error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
