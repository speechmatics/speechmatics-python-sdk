import asyncio
import logging
from contextlib import ExitStack

from speechmatics.rt import AsyncMultiChannelClient
from speechmatics.rt import ServerMessageType

logging.basicConfig(level=logging.INFO)


async def main():
    # ExitStack guarantees every opened file is closed, even if a later open() fails
    with ExitStack() as stack:
        sources = {
            "channel_one": stack.enter_context(open("channel_one.pcm", "rb")),
            "channel_two": stack.enter_context(open("channel_two.pcm", "rb")),
        }

        try:
            async with AsyncMultiChannelClient() as client:

                @client.on(ServerMessageType.ADD_TRANSCRIPT)
                def handle_transcript(msg):
                    channel = msg.get("channel")
                    transcript = msg["metadata"]["transcript"]
                    print(f"[{channel}]: {transcript}")

                await client.transcribe(sources)
        except Exception as e:
            print(f"Transcription error: {e}")


asyncio.run(main())
