"""
Async example showing real-time transcription.
"""

import asyncio
import os

from speechmatics.rt import AsyncClient, ServerMessageType, TranscriptResult

audio_file = os.getenv(
    "AUDIO_FILE_PATH", os.path.join(os.path.dirname(__file__), "../example.wav")
)


async def main() -> None:
    """Run async transcription example."""
    transcript_parts = []

    # Initialize client with API key from environment
    async with AsyncClient() as client:
        # Register a callback using the on() method as decorator
        @client.on(ServerMessageType.ADD_TRANSCRIPT)
        def handle_final_transcript(message):
            result = TranscriptResult.from_message(message)
            print(f"Final: {result.transcript}")
            transcript_parts.append(result.transcript)

        def handle_partial_transcript(message):
            result = TranscriptResult.from_message(message)
            print(f"Partial: {result.transcript}")

        # Register a callback using the on() method directly
        client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT, handle_partial_transcript)

        try:
            with open(audio_file, "rb") as audio:
                await client.transcribe(audio)

            print(f"\nComplete transcript: {''.join(transcript_parts)}")

        except FileNotFoundError:
            print(f"Audio file not found: {audio_file}")
            print("Set AUDIO_FILE_PATH environment variable to specify audio file")

        except Exception as e:
            print(f"Transcription error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
