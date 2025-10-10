import argparse
import asyncio
import json
import os
import sys
import termios
import tty
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from colorama import init as colorama_init
from utils import CustomLevels
from utils import get_logger
from utils import select_audio_device

from speechmatics.rt import Microphone
from speechmatics.voice import AgentClientMessageType
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationKnownSpeaker
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig

colorama_init(autoreset=True)

logger = get_logger(__name__)


async def main() -> None:
    """
    Live microphone transcription with speaker diarization and speaker ID extraction.

    This example demonstrates:
    - Real-time microphone input with device selection
    - Speaker diarization and voice activity detection
    - Works with any PyAudio-compatible input device
    - At the end of the session the speaker ID is shown in the console
    """
    # Parse command line arguments
    args = parse_args()

    # Audio configuration for real-time processing
    sample_rate = args.sample_rate
    chunk_size = args.chunk_size

    # Setup microphone with user device selection
    mic = _setup_microphone(sample_rate, chunk_size)
    if not mic:
        return

    # Known speakers
    known_speakers: list[DiarizationKnownSpeaker] = (
        [DiarizationKnownSpeaker(**s) for s in args.speakers] if args.speakers else []
    )

    # Configure Voice Agent with microphone-specific settings
    config = VoiceAgentConfig(
        sample_rate=sample_rate,
        end_of_utterance_silence_trigger=args.end_of_utterance_silence_trigger,
        max_delay=args.max_delay,
        enable_diarization=True,
        end_of_utterance_mode=args.end_of_utterance_mode,
        known_speakers=known_speakers,
    )

    # Create Voice Agent client and start transcription
    async with VoiceAgentClient(api_key=args.api_key, url=args.url, config=config) as client:
        # Register event handlers for real-time transcription events
        _register_event_handlers(client, logger)

        try:
            # User instructions
            print("Microphone ready - speak now... (Press any key to stop)\n")

            # Connect to the Voice Agent service
            await client.connect()

            # Request speaker IDs at the end of the session
            if args.enrol:
                await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS, "final": True})

            # Start streaming microphone audio in a task
            streaming_task = asyncio.create_task(_stream_microphone(mic, client, chunk_size))
            keypress_task = asyncio.create_task(_wait_for_keypress())

            # Wait for either task to complete (keypress or error in streaming)
            done, pending = await asyncio.wait([streaming_task, keypress_task], return_when=asyncio.FIRST_COMPLETED)

            # End the session
            await client.disconnect()

            # Cancel any remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except asyncio.CancelledError:
            print("\nTranscription cancelled")
        except Exception as e:
            print(f"Error: {e}")


def _register_event_handlers(client: VoiceAgentClient, logger) -> None:
    """Register event handlers for real-time transcription events."""

    def _format_segment(segment) -> str:
        """Format speaker segment for display."""
        template = "@{speaker_id}: {text}" if segment["is_active"] else "@{speaker_id} (background): {text}"
        return template.format(**segment)

    @client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT)
    def handle_partial_segments(message):
        """Handle partial transcription segments."""
        segments = [_format_segment(s) for s in message["segments"]]
        delay = message.get("delay_to_finalize")
        if delay is not None:
            logger.log(CustomLevels.PARTIAL, f"💬 Partial: {segments} ({delay}s to finals)")
        else:
            logger.log(CustomLevels.PARTIAL, f"💬 Partial: {segments}")

    @client.on(AgentServerMessageType.ADD_SEGMENT)
    def handle_final_segments(message):
        """Handle final transcription segments."""
        segments = [_format_segment(s) for s in message["segments"]]
        logger.log(CustomLevels.FINAL, f"🚀 Final: {segments}")

    @client.on(AgentServerMessageType.SPEAKER_STARTED)
    def handle_speech_started(message):
        """Handle speech start events."""
        logger.log(CustomLevels.SPEAKER, f"✅ Speech started: {message}")

    @client.on(AgentServerMessageType.SPEAKER_ENDED)
    def handle_speech_ended(message):
        """Handle speech end events."""
        logger.log(CustomLevels.SPEAKER, f"🛑 Speech ended: {message}")

    @client.on(AgentServerMessageType.SPEAKERS_RESULT)
    def handle_metrics(message):
        """Show the speakers result."""
        if message["speakers"]:
            logger.info(f"😀 Speakers: {json.dumps(message['speakers'])}")


def _setup_microphone(sample_rate: int, chunk_size: int) -> Microphone | None:
    """Setup microphone with device selection."""
    selected_device = select_audio_device()

    mic = Microphone(
        sample_rate=sample_rate,
        chunk_size=chunk_size,
        device_index=selected_device,
    )

    if not mic.start():
        print("Error: PyAudio not available - install with: pip install pyaudio")
        return None
    return mic


async def _stream_microphone(mic: Microphone, client: VoiceAgentClient, chunk_size: int) -> None:
    """Stream microphone audio to client."""
    try:
        while True:
            frame = await mic.read(chunk_size)
            await client.send_audio(frame)
    except asyncio.CancelledError:
        logger.debug("Microphone streaming task cancelled")
        raise


async def _wait_for_keypress() -> None:
    """Wait for any key press in a non-blocking way."""
    loop = asyncio.get_event_loop()

    def _read_key():
        """Read a single key press (Unix/Mac only)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Run the blocking key read in a thread pool
    await loop.run_in_executor(None, _read_key)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Live microphone transcription with speaker diarization using Speechmatics Voice API",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SPEECHMATICS_API_KEY"),
        help="Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)",
    )
    parser.add_argument("--url", help="Speechmatics server URL (optional)")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Audio sample rate in Hz (default: 16000)")
    parser.add_argument("--chunk-size", type=int, default=320, help="Audio chunk size in bytes (default: 320)")

    # Voice Agent configuration arguments
    parser.add_argument(
        "--max-delay",
        type=float,
        default=0.7,
        help="Maximum delay for transcription results in seconds (default: 0.7)",
    )
    parser.add_argument(
        "--end-of-utterance-silence-trigger",
        type=float,
        default=0.5,
        help="Silence duration to trigger end of utterance in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--end-of-utterance-mode",
        choices=["FIXED", "ADAPTIVE"],
        default="ADAPTIVE",
        help="End of utterance detection mode (default: ADAPTIVE)",
    )

    # Enrolment
    parser.add_argument(
        "--enrol",
        action="store_true",
        help="Enroll a speaker (default: False)",
    )
    parser.add_argument(
        "--speakers",
        type=json.loads,
        help="Known speakers (default: None)",
    )

    # Process the arguments
    args = parser.parse_args()

    # Convert string to EndOfUtteranceMode enum
    if args.end_of_utterance_mode == "FIXED":
        args.end_of_utterance_mode = EndOfUtteranceMode.FIXED
    else:
        args.end_of_utterance_mode = EndOfUtteranceMode.ADAPTIVE

    return args


if __name__ == "__main__":
    asyncio.run(main())
