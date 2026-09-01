"""Transcribe the microphone with the Agent STT service.

The service's VAD decides where turns begin and end, so this prints segments as they close
plus the speech and turn events around them.

Run with: python examples/agent_stt/microphone/main.py
"""

import asyncio

from speechmatics.agent_stt import AgentSttAsyncClient
from speechmatics.agent_stt import Microphone
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024


async def main() -> None:
    mic = Microphone(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
    if not mic.start():
        print("PyAudio not installed - install with: pip install pyaudio")
        return

    transcription_config = TranscriptionConfig(language="en", enable_partials=True, diarization="speaker")

    # Uses SPEECHMATICS_API_KEY from the environment
    client = AgentSttAsyncClient(transcription_config=transcription_config)

    # Registered before the session opens, so no message can arrive unhandled
    @client.on(ServerMessageType.ADD_PARTIAL_SEGMENT)
    def handle_partial_segment(message):
        print(f"[partial] {message['segment']['transcript']}")

    @client.on(ServerMessageType.ADD_SEGMENT)
    def handle_segment(message):
        speaker = message["segment"].get("speaker", "?")
        print(f"[final]   {speaker}: {message['segment']['transcript']}")

    @client.on(ServerMessageType.END_OF_TURN)
    def handle_end_of_turn(message):
        print(f"[turn]    end at {message['metadata']['end_time']}s")

    async with client:
        print("\nMicrophone ready - speak now (Ctrl+C to stop)\n")

        try:
            while True:
                await client.send_audio(await mic.read(CHUNK_SIZE))
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            mic.stop()

    print(f"\nTranscript: {client.transcript_text(speaker_labels=True)}")


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
