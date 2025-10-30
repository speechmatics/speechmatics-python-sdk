"""Simple microphone transcription example.

This example demonstrates basic real-time transcription with speaker diarization
using the default microphone. It prints partial segments, final segments, and
end-of-turn events.
"""

import asyncio
import json
import os
from enum import Enum
from pathlib import Path

from speechmatics.rt import Microphone
from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice import VoiceAgentConfigPreset


class Color(Enum):
    PARTIAL = "\033[93m"
    FINAL = "\033[1;92m"
    WAITING = "\033[95m"
    RESET = "\033[0m"


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

    # Load additional vocabulary from vocab.json if it exists
    vocab_file = Path(__file__).parent / "vocab.json"
    additional_vocab = []
    if vocab_file.exists():
        with open(vocab_file) as f:
            vocab_data = json.load(f)
            additional_vocab = [
                AdditionalVocabEntry(content=entry["content"], sounds_like=entry.get("sounds_like", []))
                for entry in vocab_data
            ]

    # Use the SCRIBE preset with additional vocabulary
    config = VoiceAgentConfigPreset.SCRIBE(VoiceAgentConfig(language="en", additional_vocab=additional_vocab))

    # Create client
    client = VoiceAgentClient(api_key=api_key, config=config)

    # Track waiting state
    waiting_displayed = False

    # Show listening message
    def show_listening():
        """Show listening for audio."""
        nonlocal waiting_displayed
        if not waiting_displayed:
            print(f"\r\033[K{Color.WAITING.value} listening ... {Color.RESET.value}", end="", flush=True)
            waiting_displayed = True

    # Format timestamp from start_time (seconds since session start)
    def format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS timestamp."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    # Handle partial segments (interim results)
    def on_partial_segment(message):
        """Print partial segment(s) as yellow."""

        # Clear waiting message
        nonlocal waiting_displayed
        waiting_displayed = False

        # Segments
        segments = message.get("segments", [])
        if not segments:
            return

        # Get metadata start_time
        metadata = message.get("metadata", {})
        start_time = metadata.get("start_time", 0)
        timestamp = format_time(start_time)

        # Move to beginning of line, clear it, and print yellow partial with timestamp
        for segment in segments:
            print(
                f"\r\033[K{Color.PARTIAL.value}{timestamp} - {segment['speaker_id']}: {segment['text']}{Color.RESET.value}",
                end="",
                flush=True,
            )

    # Handle final segments
    def on_segment(message):
        """Print final segment(s) as green."""

        # Segments
        segments = message.get("segments", [])
        if not segments:
            return

        # Get metadata start_time
        metadata = message.get("metadata", {})
        start_time = metadata.get("start_time", 0)
        timestamp = format_time(start_time)

        # Clear line, print green final with timestamp, then newline
        for segment in segments:
            print(
                f"\r\033[K{Color.FINAL.value}{timestamp} - {segment['speaker_id']}: {segment['text']}{Color.RESET.value}",
                flush=True,
            )

        # Show listening message
        show_listening()

    # Register event handlers
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, on_partial_segment)
    client.on(AgentServerMessageType.ADD_SEGMENT, on_segment)

    # Instructions
    print("\nMicrophone ready - speak now... (Press CTRL+C to stop)\n")

    # Connect to the service
    await client.connect()

    # Show initial listening message
    show_listening()

    # Stream audio from microphone
    async def stream_audio():
        while True:
            audio_chunk = await mic.read(160)
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
