import asyncio
import logging

import numpy as np
import sounddevice as sd
from speechmatics.tts import AsyncClient, OutputFormat, Voice

logger = logging.getLogger(__name__)

# Configuration
TEXT = "Welcome to the future of audio generation from text! This audio is a demo of the async streaming Speechmatics' text to speech API."
VOICE = Voice.JACK
OUTPUT_FORMAT = OutputFormat.RAW_PCM_16000

# Audio Parameters
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1  # Mono audio
CHUNK_SIZE = 2048  # Size of byte chunks (will be 2048 16-bit samples)

# Sentinel value to signal end of stream
END_OF_STREAM = object()

# Core Async Functions

# 1. Producer:
async def audio_generator(audio_queue: asyncio.Queue, text: str, voice: str, output_format: str) -> None:
    try:
        buffer = bytearray()
        async with AsyncClient() as client, await client.generate(
            text=text,
            voice=voice,
            output_format=output_format
        ) as response:
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                if chunk:
                    buffer.extend(chunk)
                    if len(buffer) >= CHUNK_SIZE:
                        bytes_to_put = len(buffer) - (len(buffer) % 2)
                        await audio_queue.put(buffer[:bytes_to_put])
                        buffer = buffer[bytes_to_put:]
            if buffer:
                await audio_queue.put(bytes(buffer))
            logger.info("Generator: All audio bytes streamed to queue.")
    except Exception as e:
        logger.error("Generator Error: %s", e, exc_info=True)
        raise
    finally:
        await audio_queue.put(END_OF_STREAM)

# 2. Consumer:
async def audio_player(play_queue: asyncio.Queue) -> None:
    current_buffer = bytearray()
    try:
        with sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            blocksize=CHUNK_SIZE // 2,
            latency='low',
        ) as stream:
            while True:
                chunk = await play_queue.get()
                if chunk is END_OF_STREAM:
                    break

                current_buffer.extend(chunk)
                bytes_to_process = len(current_buffer) - (len(current_buffer) % 2)

                if bytes_to_process > 0:
                    audio_data = np.frombuffer(
                        bytes(current_buffer[:bytes_to_process]),
                        dtype=np.int16
                    )
                    stream.write(audio_data)
                    current_buffer = current_buffer[bytes_to_process:]

                play_queue.task_done()

            if current_buffer:
                audio_data = np.frombuffer(bytes(current_buffer), dtype=np.int16)
                stream.write(audio_data)

    except Exception as e:
        logger.error("Player Error: %s", e, exc_info=True)
        raise
    finally:
        logger.info("Player: Audio playback finished.")


# 3. Main:
async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    play_queue = asyncio.Queue(maxsize=10)
    tasks = [
        audio_generator(play_queue, TEXT, VOICE, OUTPUT_FORMAT),
        audio_player(play_queue),
    ]
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error("Error %s", e)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        logger.info("Done")

if __name__ == "__main__":
    asyncio.run(main())
