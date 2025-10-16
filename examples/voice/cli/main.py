"""Transcription CLI with Speaker Diarization.

Command-line tool for real-time transcription using the Speechmatics Voice SDK.
Supports both microphone input and audio file streaming with speaker diarization.
"""

import argparse
import asyncio
import datetime
import json
import os
import wave
from pathlib import Path

from utils import AudioPlayer
from utils import select_audio_device
from utils import select_audio_output_device

from speechmatics.rt import Microphone
from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentClientMessageType
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import SpeakerFocusConfig
from speechmatics.voice import SpeakerFocusMode
from speechmatics.voice import SpeakerIdentifier
from speechmatics.voice import SpeechSegmentConfig
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig

# ==============================================================================
# CONSTANTS
# ==============================================================================

COLORS = {
    # Segments
    "AddPartialSegment": "\033[93m",
    "AddSegment": "\033[1;92m",
    # Speaker events
    "SpeakerStarted": "\033[94m",
    "SpeakerEnded": "\033[94m",
    "SpeakersResult": "\033[95m",
    "SpeakerMetrics": "\033[96m",
    # End of turn
    "StartOfTurn": "\033[91m",
    "EndOfTurnPrediction": "\033[95m",
    "EndOfTurn": "\033[1;91m",
    # Transcript events
    "AddPartialTranscript": "\033[90m",
    "AddTranscript": "\033[90m",
    "EndOfUtterance": "\033[90m",
}


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


async def main() -> None:
    """Run the transcription CLI."""
    args = parse_args()

    # Setup audio source (microphone or file)
    audio_source = setup_audio_source(args)
    if not audio_source:
        return

    # Setup audio output (for file playback)
    audio_player = setup_audio_output(audio_source, args)

    # Remove JSONL output file if it already exists
    if args.output_file and os.path.exists(args.output_file):
        os.remove(args.output_file)

    # Create speaker configuration
    speaker_config = create_speaker_config(args)

    # Known speakers
    known_speakers: list[SpeakerIdentifier] = [SpeakerIdentifier(**s) for s in args.speakers] if args.speakers else []

    # Create Voice Agent configuration
    config = VoiceAgentConfig(
        sample_rate=audio_source["sample_rate"],
        end_of_utterance_silence_trigger=args.end_of_utterance_silence_trigger,
        max_delay=args.max_delay,
        enable_diarization=True,
        end_of_utterance_mode=args.end_of_utterance_mode.lower(),
        speaker_config=speaker_config,
        enable_preview_features=args.preview,
        additional_vocab=[
            AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"]),
        ],
        known_speakers=known_speakers,
        speech_segment_config=SpeechSegmentConfig(split_on_eos=not args.no_split),
    )

    # Create Voice Agent client
    client = VoiceAgentClient(api_key=args.api_key, url=args.url, config=config)

    # Setup event handlers
    start_time = datetime.datetime.now()
    register_event_handlers(client, args, start_time)

    # Display instructions
    if audio_source["type"] == "file":
        print("\nStreaming audio file... (Press CTRL+C to stop)\n")
    else:
        print("\nMicrophone ready - speak now... (Press CTRL+C to stop)\n")

    # Connect to the Voice Agent service
    try:
        await client.connect()
    except Exception as e:
        print(f"Error connecting to Voice Agent service: {e}")
        return

    # Request speaker IDs at the end of the session (if enrolling)
    if args.enrol:
        await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS, "final": True})

    # Stream audio
    try:
        await stream_audio(audio_source, audio_player, client, args.chunk_size)
    except asyncio.CancelledError:
        pass
    finally:
        if audio_player:
            audio_player.stop()
        await client.disconnect()


# ==============================================================================
# AUDIO SOURCE SETUP
# ==============================================================================


def setup_audio_source(args) -> dict | None:
    """Setup audio source (microphone or file).

    Returns:
        Dictionary with audio source information or None on error.
    """
    if args.input_file:
        return setup_file_source(args)
    else:
        return setup_microphone_source(args)


def setup_file_source(args) -> dict | None:
    """Setup audio file source.

    Returns:
        Dictionary with file information or None on error.
    """
    audio_file_path = Path(args.input_file)
    if not audio_file_path.exists():
        print(f"Error: Audio file not found: {audio_file_path}")
        return None

    # Load and validate the audio file
    try:
        with wave.open(str(audio_file_path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.getnframes()
            duration = frames / sample_rate

            if channels != 1:
                print("Error: Only mono audio files are supported")
                return None
            if sample_width != 2:
                print("Error: Only 16-bit audio files are supported")
                return None

        print(f"Loading: {audio_file_path.name} ({duration:.1f}s, {sample_rate}Hz)")

        return {
            "type": "file",
            "path": audio_file_path,
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_width": sample_width,
        }

    except (wave.Error, ValueError) as e:
        print(f"Error loading audio file: {e}")
        return None


def setup_microphone_source(args) -> dict | None:
    """Setup microphone source.

    Returns:
        Dictionary with microphone information or None on error.
    """
    print("\nSelect microphone input device:")
    selected_device = select_audio_device()

    mic = Microphone(
        sample_rate=args.sample_rate,
        chunk_size=args.chunk_size,
        device_index=selected_device,
    )

    if not mic.start():
        print("Error: PyAudio not available - install with: pip install pyaudio")
        return None

    return {
        "type": "microphone",
        "mic": mic,
        "sample_rate": args.sample_rate,
    }


# ==============================================================================
# AUDIO OUTPUT SETUP
# ==============================================================================


def setup_audio_output(audio_source: dict, args) -> AudioPlayer | None:
    """Setup audio output for file playback.

    Args:
        audio_source: Audio source information
        args: Command-line arguments

    Returns:
        AudioPlayer instance or None if not needed/available.
    """
    # Only setup audio output for file sources
    if audio_source["type"] != "file":
        return None

    # Skip audio output if muted
    if args.mute:
        print("\nAudio playback muted - transcription only")
        return None

    print("\nSelect audio output device for playback:")
    output_device = select_audio_output_device()

    audio_player = AudioPlayer(
        sample_rate=audio_source["sample_rate"],
        channels=audio_source["channels"],
        sample_width=audio_source["sample_width"],
        device_index=output_device,
    )

    if not audio_player.start():
        print("Warning: Audio playback unavailable - continuing with transcription only")
        return None

    return audio_player


# ==============================================================================
# SPEAKER CONFIGURATION
# ==============================================================================


def create_speaker_config(args) -> SpeakerFocusConfig:
    """Create speaker diarization configuration from arguments.

    Args:
        args: Command-line arguments

    Returns:
        SpeakerFocusConfig instance.
    """
    if args.focus_speakers or args.ignore_speakers:
        focus_mode = SpeakerFocusMode.IGNORE if args.ignore_mode else SpeakerFocusMode.RETAIN
        return SpeakerFocusConfig(
            focus_speakers=args.focus_speakers or [],
            ignore_speakers=args.ignore_speakers or [],
            focus_mode=focus_mode,
        )
    else:
        return SpeakerFocusConfig()


# ==============================================================================
# EVENT HANDLERS
# ==============================================================================


def register_event_handlers(client: VoiceAgentClient, args, start_time: datetime.datetime) -> None:
    """Register event handlers for transcription events.

    Args:
        client: Voice Agent client
        args: Command-line arguments
        start_time: Start time for timestamp calculation
    """

    def console_print(message) -> None:
        """Print message to console with optional formatting."""
        if not args.pretty:
            print(json.dumps(message))
            return

        # Extract common data
        ts = message["ts"]
        msg_type = message["message"]
        color = COLORS.get(msg_type, "")
        payload = {k: v for k, v in message.items() if k not in ("ts", "message")}

        # Handle segment messages
        if msg_type in ("AddPartialSegment", "AddSegment"):
            _segs = []
            for segment in payload["segments"]:
                prefix = "" if segment["is_active"] else " (background)"
                _segs.append(f"@{segment['speaker_id']}{prefix}: `{segment['text']}` {segment['annotation']}")
            payload = {"segments": _segs}

        # Print to console
        print(f"{color}{ts:7.3f} {msg_type:<24} {json.dumps(payload)}\033[0m")

    def log_message(message) -> None:
        """Log message to console and optional JSONL file."""
        ts = (datetime.datetime.now() - start_time).total_seconds()
        message = {"ts": round(ts, 3), **message}
        console_print(message)

        if args.output_file:
            with open(args.output_file, "a") as f:
                f.write(json.dumps(message) + "\n")

    # Register standard handlers
    client.on(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.on(AgentServerMessageType.END_OF_TRANSCRIPT, log_message)

    # Voice SDK messages
    if not args.legacy:
        # Segment messages
        client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT, log_message)
        client.on(AgentServerMessageType.ADD_SEGMENT, log_message)
        client.on(AgentServerMessageType.START_OF_TURN, log_message)
        client.on(AgentServerMessageType.END_OF_TURN, log_message)
        client.on(AgentServerMessageType.SPEAKERS_RESULT, log_message)

        # Verbose VAD events
        if args.verbose >= 1:
            client.on(AgentServerMessageType.SPEAKER_STARTED, log_message)
            client.on(AgentServerMessageType.SPEAKER_ENDED, log_message)
            client.on(AgentServerMessageType.SPEAKER_METRICS, log_message)

        # Verbose turn prediction
        if args.verbose >= 2:
            client.on(AgentServerMessageType.END_OF_TURN_PREDICTION, log_message)

        # Verbose STT events
        if args.verbose >= 3:
            client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
            client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
            client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)

    # Legacy messages
    else:
        client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
        client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
        client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)


# ==============================================================================
# AUDIO STREAMING
# ==============================================================================


async def stream_audio(
    audio_source: dict,
    audio_player: AudioPlayer | None,
    client: VoiceAgentClient,
    chunk_size: int,
) -> None:
    """Stream audio from source to client.

    Args:
        audio_source: Audio source information
        audio_player: Audio player for file playback (optional)
        client: Voice Agent client
        chunk_size: Audio chunk size in bytes
    """
    if audio_source["type"] == "file":
        await stream_file(audio_source, audio_player, client, chunk_size)
    else:
        await stream_microphone(audio_source, client, chunk_size)


async def stream_file(
    audio_source: dict,
    audio_player: AudioPlayer | None,
    client: VoiceAgentClient,
    chunk_size: int,
) -> None:
    """Stream audio file with real-time pacing.

    Uses absolute timing to prevent audio crackling when processing takes longer
    than expected. This ensures consistent playback timing regardless of
    transcription processing delays.

    Args:
        audio_source: Audio source information
        audio_player: Audio player for playback (optional)
        client: Voice Agent client
        chunk_size: Audio chunk size in bytes
    """
    file_path = audio_source["path"]
    sample_rate = audio_source["sample_rate"]
    chunk_duration = chunk_size / sample_rate

    # Use absolute timing to prevent drift
    start_time = asyncio.get_event_loop().time()
    chunk_count = 0

    with wave.open(str(file_path), "rb") as wav_file:
        while True:
            audio_data = wav_file.readframes(chunk_size)
            if not audio_data:
                break

            # Send to transcription (non-blocking)
            asyncio.create_task(client.send_audio(audio_data))

            # Play audio (blocking to maintain timing)
            if audio_player:
                audio_player.play(audio_data)

            # Calculate next chunk time based on absolute timing
            chunk_count += 1
            next_chunk_time = start_time + (chunk_count * chunk_duration)
            current_time = asyncio.get_event_loop().time()
            sleep_duration = next_chunk_time - current_time

            # Only sleep if we're ahead of schedule
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)


async def stream_microphone(
    audio_source: dict,
    client: VoiceAgentClient,
    chunk_size: int,
) -> None:
    """Stream microphone audio to client.

    Args:
        audio_source: Audio source information
        client: Voice Agent client
        chunk_size: Audio chunk size in bytes
    """
    mic = audio_source["mic"]
    while True:
        frame = await mic.read(chunk_size)
        await client.send_audio(frame)


# ==============================================================================
# COMMAND-LINE ARGUMENT PARSING
# ==============================================================================


def load_speakers(value: str):
    """Load speakers from JSON string or file path.

    Args:
        value: Either a JSON string or path to a JSON file

    Returns:
        Parsed speakers list

    Raises:
        argparse.ArgumentTypeError: If the value cannot be parsed
    """
    # First, try to parse as JSON string
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    # If that fails, try to load as a file path
    try:
        file_path = Path(value)
        if file_path.exists() and file_path.is_file():
            with open(file_path) as f:
                return json.load(f)
        else:
            raise argparse.ArgumentTypeError(f"File not found: {value}")
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Could not parse as JSON or load from file: {value}. Error: {e}")


def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Transcription CLI with speaker diarization - supports microphone or audio file input",
        epilog="Example: python main.py -k YOUR_KEY -i audio.wav -p",
    )

    # ==============================================================================
    # Core parameters
    # ==============================================================================

    parser.add_argument(
        "-k",
        "--api-key",
        default=os.getenv("SPEECHMATICS_API_KEY"),
        help="Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)",
    )
    parser.add_argument(
        "-u",
        "--url",
        default=os.getenv("SPEECHMATICS_SERVER_URL"),
        help="Speechmatics server URL (optional)",
    )

    # ==============================================================================
    # Audio source
    # ==============================================================================

    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        help="Path to input audio file (WAV format, mono 16-bit). If not provided, uses microphone",
    )

    # ==============================================================================
    # Audio configuration
    # ==============================================================================

    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Audio sample rate in Hz (default: 16000)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=320,
        help="Audio chunk size in bytes (default: 320)",
    )
    parser.add_argument(
        "-M",
        "--mute",
        action="store_true",
        help="Mute audio playback for file input (default: False)",
    )

    # ==============================================================================
    # Output configuration
    # ==============================================================================

    parser.add_argument(
        "-o",
        "--output-file",
        type=str,
        help="Output to a JSONL file",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print console output (default: False)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v: add speaker VAD events, -vv: add END_OF_TURN_PREDICTION, -vvv: add additional payloads)",
    )
    parser.add_argument(
        "-l",
        "--legacy",
        action="store_true",
        help="Only show payloads from AsyncClient (AddPartialTranscript | AddTranscript) (default: False)",
    )

    # ==============================================================================
    # Voice Agent configuration
    # ==============================================================================

    parser.add_argument(
        "-d",
        "--max-delay",
        type=float,
        default=0.7,
        help="Maximum delay for transcription results in seconds (default: 0.7)",
    )
    parser.add_argument(
        "-t",
        "--end-of-utterance-silence-trigger",
        type=float,
        default=0.5,
        help="Silence duration to trigger end of utterance in seconds (default: 0.5)",
    )
    parser.add_argument(
        "-m",
        "--end-of-utterance-mode",
        type=lambda s: s.upper(),
        choices=["FIXED", "ADAPTIVE", "EXTERNAL", "SMART_TURN"],
        default="ADAPTIVE",
        help="End of utterance detection mode (default: ADAPTIVE)",
    )
    parser.add_argument(
        "-S",
        "--no-split",
        action="store_true",
        help="Do not emit finalized sentences, only complete segments. (default: False)",
    )

    # ==============================================================================
    # Speaker configuration
    # ==============================================================================

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

    # ==============================================================================
    # Speaker identification
    # ==============================================================================

    parser.add_argument(
        "-e",
        "--enrol",
        action="store_true",
        help="Enrol a speaker (default: False)",
    )
    parser.add_argument(
        "-s",
        "--speakers",
        type=load_speakers,
        help="Known speakers as JSON string or path to JSON file (default: None)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Use preview features (default: False)",
    )

    return parser.parse_args()


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    asyncio.run(main())
