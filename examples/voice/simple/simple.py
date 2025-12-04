"""Simple microphone transcription example.

This example demonstrates basic real-time transcription with speaker diarization
using the default microphone. It prints partial segments, final segments, and
end-of-turn events.
"""

import asyncio
import os

from speechmatics.rt import Microphone
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import SpeechSegmentConfig
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice import VoiceAgentConfigPreset


async def main() -> None:
    """Run simple microphone transcription."""

    # Get API key from environment
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        print("Error: SPEECHMATICS_API_KEY environment variable not set")
        return

    # Setup microphone with default device
    mic = Microphone(sample_rate=16000, chunk_size=320)
    if not mic.start():
        print("Error: PyAudio not available - install with: pip install pyaudio")
        return

    # Config
    config = VoiceAgentConfigPreset.FAST(
        VoiceAgentConfig(speech_segment_config=SpeechSegmentConfig(emit_sentences=False))
    )

    # Create client
    client = VoiceAgentClient(api_key=api_key, config=config)

    # Handle partial segments (interim results)
    # @client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT)
    # def on_partial_segment(message):
    #     segments = message.get("segments", [])
    #     for segment in segments:
    #         print(f"[PARTIAL] {segment['speaker_id']}: {segment['text']}")

    # Handle final segments
    @client.on(AgentServerMessageType.ADD_SEGMENT)
    def on_segment(message):
        segments = message.get("segments", [])
        for segment in segments:
            print(f"[FINAL] {segment['speaker_id']}: {segment['text']}")

    # Handle end of turn
    @client.on(AgentServerMessageType.END_OF_TURN)
    def on_end_of_turn(message):
        print("[END OF TURN]")

    # Instructions
    print("\nMicrophone ready - speak now... (Press CTRL+C to stop)\n")

    # Connect to the service
    await client.connect()

    # Stream audio from microphone
    async def stream_audio():
        while True:
            audio_chunk = await mic.read(320)
            await client.send_audio(audio_chunk)

    # Run until interrupted
    try:
        await stream_audio()
    except KeyboardInterrupt:
        print("\n\nStopping...")
    except asyncio.CancelledError:
        pass

    # Disconnect
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
