import argparse
import asyncio
import datetime
import json
import os
import sys
import time
from typing import Callable
from typing import Optional

import aiofiles

from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationFocusMode
from speechmatics.voice import DiarizationSpeakerConfig
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._helpers import to_serializable


async def main() -> None:
    """Transcribe a file to a JSONL file."""

    # Parse command line arguments
    args = parse_args()

    # Check file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)

    # Create speaker configuration if speaker options are provided
    speaker_config = None
    if args.focus_speakers or args.ignore_speakers:
        focus_mode = DiarizationFocusMode.IGNORE if args.ignore_mode else DiarizationFocusMode.RETAIN
        speaker_config = DiarizationSpeakerConfig(
            focus_speakers=args.focus_speakers,
            ignore_speakers=args.ignore_speakers,
            focus_mode=focus_mode,
        )

    # Client
    client = VoiceAgentClient(
        api_key=args.api_key,
        url=args.url,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=args.end_of_utterance_silence_trigger,
            max_delay=args.max_delay,
            end_of_utterance_mode=args.end_of_utterance_mode,
            enable_diarization=True,
            speaker_config=speaker_config,
            additional_vocab=[
                AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matters", "speech magic"])
            ],
        ),
    )

    # Create an event to track when the callback is called
    messages: list[str] = []
    bytes_sent: int = 0

    # Start time
    start_time = datetime.datetime.now()

    # Bytes logger
    def log_bytes_sent(bytes):
        nonlocal bytes_sent
        bytes_sent += bytes

    # Callback for each message
    def log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        audio_ts = bytes_sent / 16000 / 2
        log = json.dumps({"ts": ts, "audio_ts": audio_ts, "payload": to_serializable(message)})
        messages.append(log)

        # Output to file or stdout
        if args.output:
            with open(args.output, "a") as f:
                f.write(log + "\n")
        else:
            print(log)

    # Log script info
    log_message({"message": "AudioFile", "path": args.input_file})
    log_message({"message": "VoiceAgentConfig", **to_serializable(client._config)})
    log_message({"message": "TranscriptionConfig", **to_serializable(client._transcription_config)})
    log_message({"message": "AudioFormat", **to_serializable(client._audio_format)})

    # Add listeners
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
    client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
    client.on(AgentServerMessageType.END_OF_TURN, log_message)

    # Clear output file if it exists
    if args.output and os.path.exists(args.output):
        open(args.output, "w").close()

    # Connect
    await client.connect()

    # Use the input file from command line arguments
    await send_audio_file(client, args.input_file, progress_callback=log_bytes_sent)

    # Close session
    await client.disconnect()
    assert not client._is_connected


async def send_audio_file(
    client: VoiceAgentClient,
    file: str,
    event_received: Optional[asyncio.Event] = None,
    chunk_size: int = 320,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """Send audio data to the API server."""

    # Delay is based off 16kHz int16 and chunk size
    delay = chunk_size / 16000 / 2

    # Load the file
    async with aiofiles.open(file, "rb") as wav_file:
        # Trim off the WAV file header
        await wav_file.seek(44)

        # Send audio data
        next_time = time.perf_counter() + delay
        while not event_received.is_set() if event_received else True:
            """Reads all chunks until the end of the file with precision delay."""

            # Read chunk
            chunk = await wav_file.read(chunk_size)
            if not chunk:
                break

            # Send audio to client
            await client.send_audio(chunk)

            # Do any callbacks
            if progress_callback:
                progress_callback(len(chunk))

            # Precision delay
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            next_time += delay


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file to JSONL format using Speechmatics Voice API",
        epilog="Example: python file_to_jsonl.py audio.wav --output transcription.jsonl --focus-speakers S1 S2",
    )
    parser.add_argument("input_file", help="Path to the input audio file (WAV format)")
    parser.add_argument(
        "--api-key",
        default=os.getenv("SPEECHMATICS_API_KEY"),
        help="Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)",
    )
    parser.add_argument("--url", help="Speechmatics server URL (optional)")
    parser.add_argument("--output", "-o", help="Output JSONL file (defaults to stdout)")

    # Speaker configuration arguments
    parser.add_argument(
        "--focus-speakers",
        nargs="*",
        help="Speakers to focus on (e.g., S1 S2). Use with --ignore-mode to ignore these speakers instead",
    )
    parser.add_argument(
        "--ignore-speakers",
        nargs="*",
        help="Specific speakers to ignore (e.g., S1 S2)",
    )
    parser.add_argument(
        "--ignore-mode",
        action="store_true",
        help="Use ignore mode instead of focus mode for --focus-speakers",
    )

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
        default="FIXED",
        help="End of utterance detection mode (default: FIXED)",
    )

    args = parser.parse_args()

    # Convert string to EndOfUtteranceMode enum
    if args.end_of_utterance_mode == "FIXED":
        args.end_of_utterance_mode = EndOfUtteranceMode.FIXED
    else:
        args.end_of_utterance_mode = EndOfUtteranceMode.ADAPTIVE

    return args


if __name__ == "__main__":
    asyncio.run(main())
