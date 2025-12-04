import asyncio
import sounddevice as sd
import numpy as np
from speechmatics.tts import AsyncClient, Voice, OutputFormat

# Configuration
TEXT = "Welcome to the future of audio generation from text! This audio is a demo of the async streaming Speechmatics' text to speech API."
VOICE = Voice.JACK
OUTPUT_FORMAT = OutputFormat.RAW_PCM_16000

# Audio Parameters
SAMPLE_RATE = 16000 #Hz
SAMPLE_WIDTH = 2 # 16-bit audio
CHANNELS = 1 # Mono audio
CHUNK_SIZE = 2048 # Size of audio chunks
BUFFER_SIZE = 4096 # Size of buffer

# Sentinel value to signal end of stream
END_OF_STREAM = None


# Core Async Functions

# 1. Producer: Generates audio and puts chunks into the queue:

async def audio_generator(audio_queue: asyncio.Queue, text: str, voice: str, output_format: str) -> None:
    try:
        async with AsyncClient() as client, await client.generate(
            text=text,
            voice=voice,
            output_format=output_format
        ) as response:
            buffer=bytearray()
            async for chunk in response.content.iter_chunked(BUFFER_SIZE):
                if not chunk:
                    continue
                buffer.extend(chunk)

                # Process complete frames (2 bytes per sample for 16-bit audio)
                # Convert little-endian 16-bit signed int to np.int-16
                while len(buffer) >= 2:
                    sample = int.from_bytes(buffer[:2], byteorder='little', signed=True)
                    await audio_queue.put(sample)
                    buffer = buffer[2:]
            
            await audio_queue.put(END_OF_STREAM)
            print("Audio generated and put into queue.")
                
    except Exception as e:
        print(f"[{'Generator'}] An error occurred in the audio generator: {e}")
        await audio_queue.put(END_OF_STREAM)
        raise

# 2. Consumer: Read audio data from queue and play it in real-time using sounddevice.
async def audio_player(play_queue: asyncio.Queue) -> None:
    try:
        with sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',  # 16-bit PCM
            blocksize=CHUNK_SIZE,
            latency='high',
        ) as stream:
            buffer=[]
            while True:
                try:
                    sample = await asyncio.wait_for(play_queue.get(), timeout=0.1)
                    if sample is END_OF_STREAM:
                        if buffer:
                            audio_data=np.array(buffer, dtype=np.int16)
                            stream.write(audio_data)
                            buffer=[]
                        break
                    
                    buffer.append(sample)
                    if len(buffer) >= CHUNK_SIZE:
                        audio_data=np.array(buffer[:CHUNK_SIZE], dtype=np.int16)
                        stream.write(audio_data)
                        buffer=buffer[CHUNK_SIZE:]
                    
                    play_queue.task_done()
                
                except asyncio.TimeoutError:
                    if buffer:
                        audio_data=np.array(buffer, dtype=np.int16)
                        stream.write(audio_data)
                        buffer=[]
                    continue
                
                except Exception as e:
                    print(f"[{'Player'}] An error occurred playing audio chunk {e}")
                    raise

    except Exception as e:
        print(f"[{'Player'}] An error occurred in the audio player: {e}")
        raise
    finally:
        sd.stop()

# 3. Main Function: Orchestrate audio generation and audio stream
async def main() -> None:
    play_queue = asyncio.Queue()

    # Create tasks
    tasks = [
        asyncio.create_task(audio_generator(play_queue, TEXT, VOICE, OUTPUT_FORMAT)),
        asyncio.create_task(audio_player(play_queue))
    ]
    
    try:
        await asyncio.gather(*tasks)
        
    except Exception as e:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
