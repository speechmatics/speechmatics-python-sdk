import asyncio
import os

from speechmatics.rt import AsyncMultiChannelClient, ServerMessageType

example_file = os.getenv(
    "AUDIO_FILE_PATH", os.path.join(os.path.dirname(__file__), "../example.wav")
)

async def main():
    sources = {
        "channel_one": open(example_file, "rb"),
        "channel_two": open(example_file, "rb"),
    }

    try:
        async with AsyncMultiChannelClient() as client:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_transcript(msg):
                channel = msg['results'][0]['channel']
                transcript = msg['metadata']['transcript']
                print(f"[{channel}]: {transcript}")

            await client.transcribe(sources)
    except Exception as e:
        print(f"Transcription error: {e}")
    finally:
        # Ensure all files are closed
        for source in sources.values():
            source.close()

asyncio.run(main())
