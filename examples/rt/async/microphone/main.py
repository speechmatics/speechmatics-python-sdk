import asyncio
import logging

from speechmatics.rt import (
    AsyncClient,
    AudioEncoding,
    AudioFormat,
    Microphone,
    OperatingPoint,
    ServerMessageType,
    TranscriptResult,
    TranscriptionConfig,
)


logging.basicConfig(level=logging.INFO)


def select_audio_device() -> int | None:
    """Allow user to select an audio device."""
    devices = Microphone.list_devices()

    if not devices:
        return None

    if devices:
        print("Available microphones:")
        for device in devices:
            print(f"  [{device['index']}] {device['name']} ({device['channels']} channels)")
        print()

    while True:
        try:
            choice = input("Enter device index (or press Enter for default): ").strip()
            if not choice:
                return None  # Use default

            device_index = int(choice)
            if any(d["index"] == device_index for d in devices):
                return device_index
            else:
                print(f"Invalid device index. Choose from: {[d['index'] for d in devices]}")
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            return None


async def main() -> None:
    """Run async transcription example."""
    transcript_parts = []

    # Configure audio format and transcription
    audio_format = AudioFormat(
        encoding=AudioEncoding.PCM_S16LE,
        chunk_size=4096,
        sample_rate=16000,
    )

    transcription_config = TranscriptionConfig(
        max_delay=0.8,
        enable_partials=True,
        operating_point=OperatingPoint.ENHANCED,
    )

    # Allow user to select input device
    selected_device = select_audio_device()

    mic = Microphone(
        sample_rate=audio_format.sample_rate,
        chunk_size=audio_format.chunk_size,
        device_index=selected_device,
    )

    if not mic.start():
        print("PyAudio not installed - microphone not available")
        print("Install with: pip install pyaudio")
        return

    # Initialize client with API key from environment
    async with AsyncClient() as client:
        # Register callbacks for transcript events
        @client.on(ServerMessageType.ADD_TRANSCRIPT)
        def handle_final_transcript(message):
            result = TranscriptResult.from_message(message)
            if result.transcript:
                print(f"[final]: {result.transcript}")
                transcript_parts.append(result.transcript)

        @client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
        def handle_partial_transcript(message):
            result = TranscriptResult.from_message(message)
            if result.transcript:
                print(f"[partial]: {result.transcript}")

        try:
            print("Microphone started - speak now...")
            print("Press Ctrl+C to stop transcription\n")

            await client.transcribe(
                source=mic,
                transcription_config=transcription_config,
                audio_format=audio_format,
            )

            if transcript_parts:
                print(f"\nFull transcript: {''.join(transcript_parts)}")

        except Exception as e:
            print(f"Transcription error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
