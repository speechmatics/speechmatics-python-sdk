"""
Async example showing batch transcription.
"""

import asyncio
import os

from speechmatics.batch import AsyncClient
from speechmatics.batch import JobConfig
from speechmatics.batch import JobType
from speechmatics.batch import Transcript
from speechmatics.batch import TranscriptionConfig

audio_file = os.getenv("AUDIO_FILE_PATH", os.path.join(os.path.dirname(__file__), "../example1.wav"))


async def main() -> None:
    """Run async batch transcription example."""

    # Initialize client with API key from environment
    async with AsyncClient(api_key=os.getenv("SPEECHMATICS_API_KEY")) as client:
        try:
            print(f"Submitting job for: {audio_file}")

            # Submit transcription job
            config = JobConfig(
                type=JobType.TRANSCRIPTION,
                transcription_config=TranscriptionConfig(language="en", enable_entities=True),
            )

            job = await client.submit_job(audio_file, config=config)

            print(f"Job submitted: {job.id}")
            print("Waiting for completion...")

            # Wait for job to complete
            result = await client.wait_for_completion(
                job.id,
                polling_interval=2.0,
                timeout=300.0,
            )

            print("Transcription completed!")
            if isinstance(result, Transcript):
                print(f"Transcript: {result.transcript_text}")
            else:
                print(f"Transcript: {result}")

        except FileNotFoundError:
            print(f"Audio file not found: {audio_file}")
            print("Set AUDIO_FILE_PATH environment variable to specify audio file")

        except Exception as e:
            print(f"Transcription failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
