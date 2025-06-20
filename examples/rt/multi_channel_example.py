import asyncio
import os

from speechmatics.rt import AsyncMultiChannelClient, ServerMessageType, TranscriptionConfig

audio_file = os.getenv(
    "AUDIO_FILE_PATH", os.path.join(os.path.dirname(__file__), "../example.wav")
)

async def main():
    sources = {
        "stream_one": open(audio_file, "rb"),
        "stream_two": open(audio_file, "rb"),
    }

    try:
        async with AsyncMultiChannelClient() as client:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_transcript(msg):
                channel = msg['results'][0]['channel']
                transcript = msg['metadata']['transcript']
                print(f"[{channel}]: {transcript}")

            await client.transcribe(
                sources,
                transcription_config=TranscriptionConfig(
                    language="en",
                    diarization="channel",
                    channel_diarization_labels=list(sources.keys()),
                )
            )
    except Exception as e:
        print(f"Transcription error: {e}")
    finally:
        # Ensure all files are closed
        for source in sources.values():
            source.close()

asyncio.run(main())
