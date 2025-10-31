import os
import asyncio

import wave 
from pathlib import Path

from speechmatics.tts import AsyncClient, Voice, OutputFormat

    
#Set configuration 
TEXT = "Welcome to the future of audio generation from text!"
VOICE = Voice.SARAH
OUTPUT_FORMAT = OutputFormat.RAW_PCM_16000
OUTPUT_FILE = "output.wav"

#Set Format Parameters for WAV output file
SAMPLE_RATE = 16000 #Hz
SAMPLE_WIDTH = 2 # 16-bit audio
CHANNELS = 1 # Mono audio

# Save audio to WAV file
async def save_audio_to_wav(audio_data: bytes,
                            output_file_name: str) -> None:
    with wave.open(output_file_name, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data)

#Generate speech from text and save to WAV file
async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    if not os.getenv("SPEECHMATICS_API_KEY"):
        raise ValueError("SPEECHMATICS_API_KEY environment variable is not set")

    print(f"Generating speech from text: {TEXT}")
    
    try:
        async with AsyncClient() as client:
            async with await client.generate(
                text=TEXT,
                voice=VOICE,
                output_format=OUTPUT_FORMAT
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error}")
                
                # Process the response in chunks and save to WAV
                audio_chunks = []
                async for chunk in response.content.iter_chunked(1024):
                    if not chunk:
                        break
                    audio_chunks.append(chunk)
                
                # Combine chunks and save to WAV
                audio_data = b''.join(audio_chunks)
                await save_audio_to_wav(audio_data, OUTPUT_FILE)
                print(f"Speech saved to {Path(OUTPUT_FILE).resolve()}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())