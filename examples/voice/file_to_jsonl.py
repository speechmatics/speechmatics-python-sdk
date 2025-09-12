import argparse
import asyncio
import datetime
import json
import os
import sys
import time
from dataclasses import asdict
from dataclasses import is_dataclass
from typing import Callable
from typing import Optional

import aiofiles

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig, AdditionalVocabEntry


async def main() -> None:
    """Transcribe a file to a JSONL file."""

    # Parse command line arguments
    args = parse_args()

    # Check file exists
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found", file=sys.stderr)
        sys.exit(1)

    # Client
    client = VoiceAgentClient(
        api_key=args.api_key,
        url=args.url,
        config=VoiceAgentConfig(
            end_of_utterance_silence_trigger=0.5,
            max_delay=0.7,
            end_of_utterance_mode=EndOfUtteranceMode.FIXED,
            enable_diarization=True,
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
    client.once(AgentServerMessageType.INFO, log_message)
    client.on(AgentServerMessageType.WARNING, log_message)
    client.on(AgentServerMessageType.ERROR, log_message)
    client.once(AgentServerMessageType.END_OF_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)
    client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
    client.on(AgentServerMessageType.ADD_INTERIM_SEGMENTS, log_message)
    client.on(AgentServerMessageType.ADD_SEGMENTS, log_message)
    client.on(AgentServerMessageType.SPEAKING_STARTED, log_message)
    client.on(AgentServerMessageType.SPEAKING_ENDED, log_message)
    client.on(AgentServerMessageType.TURN_STARTED, log_message)
    client.on(AgentServerMessageType.TURN_ENDED, log_message)

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


def to_serializable(obj) -> str:
    """Convert an object into a JSON-serializable form."""
    if is_dataclass(obj):
        return {k: to_serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


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
        description="Transcribe an audio file to JSONL format using Speechmatics Voice API"
    )
    parser.add_argument("input_file", help="Path to the input audio file (WAV format)")
    parser.add_argument(
        "--api-key",
        help="Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)",
    )
    parser.add_argument("--url", help="Speechmatics server URL (optional)")
    parser.add_argument("--output", "-o", help="Output JSONL file (defaults to stdout)")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
