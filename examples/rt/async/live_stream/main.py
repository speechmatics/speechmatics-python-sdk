import asyncio
import logging

from speechmatics.rt import (
    AsyncClient,
    ServerMessageType,
    TranscriptionConfig,
    AudioFormat,
)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    async with AsyncClient(api_key="YOUR_API_KEY") as client:
        # 1. open a live stream
        stream = await client.start_stream(
            transcription_config=TranscriptionConfig(max_delay=0.8),
            audio_format=AudioFormat(encoding="pcm_s16le"),
        )

        # 2. register event handlers
        @client.on(ServerMessageType.ADD_TRANSCRIPT)
        def on_transcript(msg: dict) -> None:
            print(msg)

        # 3. push audio frames as you receive them
        try:
            for _ in range(10):  # demo – 10 dummy frames
                await stream.write(b"\x00" * 4096)
        finally:
            await stream.aclose()
            await stream.wait()  # optional: wait for EndOfTranscript


if __name__ == "__main__":
    asyncio.run(main())
