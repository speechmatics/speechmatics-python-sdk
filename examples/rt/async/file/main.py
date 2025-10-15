
import asyncio
from speechmatics.rt import AsyncClient, ServerMessageType


async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    async with AsyncClient() as client:
        # Register event handlers
        @client.on(ServerMessageType.ADD_TRANSCRIPT)
        def handle_final_transcript(msg):
            print(f"Final: {msg['metadata']['transcript']}")

        # Transcribe audio file
        with open("./examples/example.wav", "rb") as audio_file:
            await client.transcribe(audio_file)

# Run the async function
asyncio.run(main())
