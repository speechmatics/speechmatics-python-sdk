import asyncio
import logging

from speechmatics.rt import AsyncMultiChannelClient, ServerMessageType

logging.basicConfig(level=logging.INFO)

async def main():
    sources = {
        "channel_one": open("channel_one.pcm", "rb"),
        "channel_two": open("channel_two.pcm", "rb"),
    }

    try:
        async with AsyncMultiChannelClient() as client:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_transcript(msg):
                channel = msg.get('channel')
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
