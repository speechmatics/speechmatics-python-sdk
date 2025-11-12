import asyncio

import wave 
from pathlib import Path

from speechmatics.tts import AsyncClient, Voice, OutputFormat

async def save_audio(audio_data: bytes, filename: str) -> None:
    with wave.open(filename, "wb") as wav:
        wav.setnchannels(1)           # Mono
        wav.setsampwidth(2)           # 16-bit
        wav.setframerate(16000)       # 16kHz
        wav.writeframes(audio_data)

# Generate speech data from text and save to WAV file
async def main():
    async with AsyncClient() as client:
        async with await client.generate(
            text="Welcome to the future of audio generation from text!",
            voice=Voice.SARAH,
            output_format=OutputFormat.RAW_PCM_16000
        ) as response:
            audio = b''.join([chunk async for chunk in response.content.iter_chunked(1024)])
            await save_audio(audio, "output.wav")


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
