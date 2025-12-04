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
from typing import Any

from utils import AudioFileWriter
from utils import AudioPlayer
from utils import load_json
from utils import select_audio_device
from utils import select_audio_output_device

from speechmatics.rt import ClientMessageType
from speechmatics.rt import Microphone
from speechmatics.voice import AdditionalVocabEntry
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import SpeakerIdentifier
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice import VoiceAgentConfigPreset

# ==============================================================================
# CONSTANTS
# ==============================================================================


# Default output directory
DEFAULT_OUTPUT_DIR = "./output"

# Output filenames
LOG_FILENAME = "log.jsonl"
RECORDING_FILENAME = "recording.wav"

# Console colors for message types
COLORS = {
    # Segments
    "Diagnostics": "\033[90m",
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
    # VAD status
    "VadStatus": "\033[41;97m",
    # Transcript events
    "AddPartialTranscript": "\033[90m",
    "AddTranscript": "\033[90m",
    "EndOfUtterance": "\033[90m",
}


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


async def main() -> None:
    """Run the transcription CLI.

    Main entry point for the CLI application. Handles:
    - Command-line argument parsing
    - Audio source setup (microphone or file)
    - Output directory management
    - Configuration setup (preset, custom, or default)
    - Event handler registration
    - Audio streaming and transcription
    """

    # Parse the command line arguments
    args = parse_args()

    # Handle preset listing
    if args.list_presets:
        print("Available presets:")
        for preset in VoiceAgentConfigPreset.list_presets():
            print(f"  - {preset}")
        return

    # Setup audio source (microphone or file) - skip if just showing config
    if not args.show_compact and not args.show_complete:
        audio_source = setup_audio_source(args)
        if not audio_source:
            return

        # Warn if trying to record from file input
        if args.record and audio_source["type"] == "file":
            print("Warning: --record is only supported for microphone input, not file playback. Recording disabled.")
            args.record = None

        # Setup audio output (for file playback)
        audio_player = setup_audio_output(audio_source, args)
    else:
        # Dummy audio source for config display
        audio_source = {"sample_rate": 16000}
        audio_player = None

    # Setup output directory with session subdirectory
    base_output_dir = Path(args.output_dir)

    # Create session reference (YYYYMMDD_HHMMSS format for better sorting)
    session_ref = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_output_dir / session_ref

    # Create session directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Session output directory: {output_dir}")

    # Setup file paths
    log_file = output_dir / LOG_FILENAME
    record_file = output_dir / RECORDING_FILENAME if args.record else None

    # Store in args for easy access
    args.log_file = str(log_file)
    args.record_file = str(record_file) if record_file else None

    # Known speakers
    known_speakers: list[SpeakerIdentifier] = [SpeakerIdentifier(**s) for s in args.speakers] if args.speakers else []

    # Use JSON config
    if args.config is not None:
        try:
            config = VoiceAgentConfig.from_dict(args.config)
        except Exception as e:
            print(f"Error validating config: {e}")
            return

    # Use a preset
    elif args.preset:
        try:
            config = VoiceAgentConfigPreset.load(args.preset)
        except ValueError as e:
            print(f"Error loading preset {args.preset}: {e}")
            return

    # Default config
    else:
        config = VoiceAgentConfig(
            additional_vocab=[
                AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"]),
            ]
        )

    # Copy speaker settings (only known_speakers can be overridden)
    config.known_speakers = known_speakers
    config.include_results = args.results

    # Set chunk size
    config.chunk_size = args.chunk_size

    # Set common items
    config.enable_diarization = True

    # Handle config display
    if args.show_compact:
        print(config.to_json(indent=2, exclude_unset=True, exclude_none=True))
        return
    if args.show_complete:
        print(config.to_json(indent=2, exclude_unset=False, exclude_none=False))
        return

    # Set the audio sample rate
    config.sample_rate = audio_source["sample_rate"]

    # Display instructions
    if audio_source["type"] == "file":
        print("\nStreaming audio file... (Press CTRL+C to stop)")
    else:
        print("\nMicrophone ready - speak now... (Press CTRL+C to stop)")

    # Show press 't' to trigger end of turn
    if config.end_of_utterance_mode == EndOfUtteranceMode.EXTERNAL:
        print("EXTERNAL end of utterance mode enabled (Press 't' to trigger end of turn)\n")
    else:
        print(f"{config.end_of_utterance_mode.value.upper()} end of utterance mode enabled\n")

    # Create Voice Agent client
    client = VoiceAgentClient(api_key=args.api_key, url=args.url, config=config)

    # Setup event handlers
    start_time = datetime.datetime.now()
    register_event_handlers(client, args, start_time)

    # Connect to the Voice Agent service
    try:
        await client.connect()
    except Exception:
        print("Error connecting to Voice Agent service")
        return

    # Request speaker IDs at the end of the session (if enrolling)
    if args.enrol:
        await client.send_message({"message": ClientMessageType.GET_SPEAKERS, "final": True})

    # Stream audio
    try:
        await stream_audio(audio_source, audio_player, client, args.chunk_size, config, args.record_file)
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

    if not args.default_device:
        print("\nSelect microphone input device:")
        selected_device = select_audio_device()
    else:
        selected_device = None

    mic = Microphone(
        sample_rate=args.sample_rate or None,
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

    if not args.default_device:
        print("\nSelect audio output device for playback:")
        output_device = select_audio_output_device()
    else:
        output_device = None

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
# EVENT HANDLERS
# ==============================================================================


def register_event_handlers(client: VoiceAgentClient, args, start_time: datetime.datetime) -> None:
    """Register event handlers for transcription events.

    Args:
        client: Voice Agent client
        args: Command-line arguments
        start_time: Start time for timestamp calculation
    """

    def console_print(ts: datetime.datetime, message: dict) -> None:
        """Print message to console with optional formatting."""
        if not args.pretty:
            print(json.dumps(message))
            return

        # Extract common data
        ts_str = ts.strftime("%H:%M:%S") + f".{ts.microsecond // 1000:03d}"
        msg_type = message["message"]
        color = COLORS.get(msg_type, "")
        payload = message

        # Handle segment messages
        if msg_type in ("AddPartialSegment", "AddSegment"):
            _segs = []
            for segment in message["segments"]:
                suffix = "" if segment["is_active"] else " (background)"
                _segs.append(f"@{segment['speaker_id']}{suffix}: `{segment['text']}` {segment.get('annotation', '')}")
            payload = {"segments": _segs}

        # Print to console
        print(f"{color}{ts_str} {client._total_time:>7.3f} {msg_type:<24} {json.dumps(payload)}\033[0m")

    def log_message(message: dict[str, Any]) -> None:
        """Log message to console and optional JSONL file."""
        now = datetime.datetime.now()
        console_print(now, message)
        if args.log_file:
            ts_str = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
            with open(args.log_file, "a") as f:
                f.write(json.dumps({"ts": ts_str, **message}) + "\n")

    # Register standard handlers
    client.on(AgentServerMessageType.INFO, log_message)
    client.once(AgentServerMessageType.RECOGNITION_STARTED, log_message)
    client.once(AgentServerMessageType.END_OF_TRANSCRIPT, log_message)

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
            client.on(AgentServerMessageType.VAD_STATUS, log_message)
            client.on(AgentServerMessageType.DIAGNOSTICS, log_message)

        # Verbose turn prediction
        if args.verbose >= 2:
            client.on(AgentServerMessageType.END_OF_TURN_PREDICTION, log_message)
            client.on(AgentServerMessageType.SMART_TURN_RESULT, log_message)

        # Metrics
        if args.verbose >= 3:
            client.on(AgentServerMessageType.SESSION_METRICS, log_message)
            client.on(AgentServerMessageType.SPEAKER_METRICS, log_message)

        # Verbose STT events
        if args.verbose >= 4:
            client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
            client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
            client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)

    # Legacy messages
    else:
        client.on(AgentServerMessageType.END_OF_UTTERANCE, log_message)
        client.on(AgentServerMessageType.ADD_PARTIAL_TRANSCRIPT, log_message)
        client.on(AgentServerMessageType.ADD_TRANSCRIPT, log_message)

    # Log the config
    if args.verbose >= 1:
        log_message(
            {
                "message": "VoiceAgentClientConfig",
                "config": client._config.to_dict(exclude_none=True, exclude_unset=True),
            }
        )


# ==============================================================================
# AUDIO STREAMING
# ==============================================================================


async def stream_audio(
    audio_source: dict,
    audio_player: AudioPlayer | None,
    client: VoiceAgentClient,
    chunk_size: int,
    config: VoiceAgentConfig,
    record_path: str | None = None,
) -> None:
    """Stream audio from source to client.

    Args:
        audio_source: Audio source information
        audio_player: Audio player for file playback (optional)
        client: Voice Agent client
        chunk_size: Audio chunk size in bytes
        config: Voice agent configuration (for EXTERNAL mode detection)
        record_path: Path to save recorded audio (microphone only)
    """
    if audio_source["type"] == "file":
        await stream_file(audio_source, audio_player, client, chunk_size)
    else:
        await stream_microphone(audio_source, client, chunk_size, config, record_path)


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
    config: VoiceAgentConfig,
    record_path: str | None = None,
) -> None:
    """Stream microphone audio to client.

    Args:
        audio_source: Audio source information
        client: Voice Agent client
        chunk_size: Audio chunk size in bytes
        config: Voice agent configuration (for EXTERNAL mode detection)
        record_path: Path to save recorded audio (optional)
    """
    import select
    import sys
    import termios
    import tty

    mic = audio_source["mic"]
    sample_rate = audio_source["sample_rate"]

    # Check if EXTERNAL mode for keyboard input
    is_external_mode = config.end_of_utterance_mode == "external"

    # Setup keyboard input for EXTERNAL mode
    old_settings = None
    if is_external_mode:
        # print("EXTERNAL mode: Press 't' or 'T' to send end of turn")
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    # Setup WAV file recording if requested
    if record_path:
        async with AudioFileWriter(record_path, sample_rate) as writer:
            try:
                while True:
                    # Read audio frame
                    frame = await mic.read(chunk_size)
                    await client.send_audio(frame)

                    # Write to WAV file
                    await writer.write(frame)

                    # Check for keyboard input in EXTERNAL mode
                    if is_external_mode and select.select([sys.stdin], [], [], 0.0)[0]:
                        char = sys.stdin.read(1)
                        if char.lower() == "t":
                            client.finalize(end_of_turn=True)

            finally:
                # Restore terminal settings
                if old_settings:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    else:
        # No recording - simpler logic
        try:
            while True:
                # Read audio frame
                frame = await mic.read(chunk_size)
                await client.send_audio(frame)

                # Check for keyboard input in EXTERNAL mode
                if is_external_mode and select.select([sys.stdin], [], [], 0.0)[0]:
                    char = sys.stdin.read(1)
                    if char.lower() == "t":
                        client.finalize(end_of_turn=True)

        finally:
            # Restore terminal settings
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


# ==============================================================================
# COMMAND-LINE ARGUMENT PARSING
# ==============================================================================


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
    # Core parameters (authentication)
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
        default=os.getenv("SPEECHMATICS_RT_URL"),
        help="Speechmatics server URL (optional)",
    )

    # ==============================================================================
    # Configuration (preset or custom)
    # ==============================================================================

    parser.add_argument(
        "-P",
        "--preset",
        type=str,
        help="Preset configuration name (e.g., scribe, fast, adaptive)",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available preset configurations and exit",
    )
    parser.add_argument(
        "-w",
        "--show-compact",
        action="store_true",
        help="Display the compact configuration as JSON and exit (excludes unset and None values)",
    )
    parser.add_argument(
        "-W",
        "--show-complete",
        action="store_true",
        help="Display the complete configuration as JSON and exit (includes all defaults)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=load_json,
        help="Config JSON string or path to JSON file (default: None)",
    )

    # ==============================================================================
    # Input/Output
    # ==============================================================================

    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        help="Path to input audio file (WAV format, mono 16-bit). If not provided, uses microphone",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for {LOG_FILENAME}, {RECORDING_FILENAME}, and audio slices (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-r",
        "--record",
        action="store_true",
        help=f"Record microphone audio to {RECORDING_FILENAME} in output directory (microphone input only)",
    )

    # ==============================================================================
    # Audio settings
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
        default=160,
        help="Audio chunk size in bytes (default: 160)",
    )
    parser.add_argument(
        "-M",
        "--mute",
        action="store_true",
        help="Mute audio playback for file input (default: False)",
    )

    # ==============================================================================
    # Output options
    # ==============================================================================

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
        "-L",
        "--legacy",
        action="store_true",
        help="Only show payloads from AsyncClient (AddPartialTranscript | AddTranscript) (default: False)",
    )
    parser.add_argument(
        "-D",
        "--default-device",
        action="store_true",
        help="Use default device (default: False)",
    )
    parser.add_argument(
        "--results",
        action="store_true",
        help="Include word-level transcription results in output (default: False)",
    )

    # ==============================================================================
    # Speaker identification
    # ==============================================================================

    parser.add_argument(
        "-E",
        "--enrol",
        action="store_true",
        help="Enrol a speaker (default: False)",
    )
    parser.add_argument(
        "-s",
        "--speakers",
        type=load_json,
        help="Known speakers as JSON string or path to JSON file (default: None)",
    )

    # ==============================================================================
    # Check for mutually exclusive options
    # ==============================================================================

    args = parser.parse_args()

    # Either preset or config must be provided
    if (
        args.config is None
        and args.preset is None
        and not args.list_presets
        and not args.show_compact
        and not args.show_complete
    ):
        print("**ERROR** -> You must provide either --preset or --config")
        exit(1)

    # Preset and config are mutually exclusive
    if args.config is not None and args.preset is not None:
        print("**ERROR** -> You cannot use both --preset and --config")
        exit(1)

    # Return the parsed arguments
    return args


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCLI utility stopped by user")
