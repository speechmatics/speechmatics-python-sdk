import asyncio
import sys
import wave
from pathlib import Path

from colorama import init as colorama_init
from utils import AudioPlayer
from utils import CustomLevels
from utils import get_logger
from utils import select_audio_output_device

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationSpeakerConfig
from speechmatics.voice import DiarizationFocusMode
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import SpeakerSegment
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig

colorama_init(autoreset=True)
logger = get_logger(__name__)


async def main() -> None:
    """
    Transcribe audio files with real-time playback and speaker diarisation.

    This example demonstrates:
    - Loading and validating WAV audio files
    - Real-time audio playback during transcription
    - Speaker diarisation with voice activity detection
    - Comprehensive event handling and logging
    """
    # Parse command line arguments for audio file path
    # Default to example.wav if no file specified
    audio_file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "../example2.wav"

    # Validate that the audio file exists
    if not audio_file_path.exists():
        print(f"Error: Audio file not found: {audio_file_path}")
        print("Usage: python file_transcription.py [audio_file.wav]")
        return

    # Load and validate the audio file format
    # Only mono 16-bit WAV files are supported
    try:
        sample_rate, channels, sample_width, duration = _load_audio_file(audio_file_path)
        print(f"Loading: {audio_file_path.name} ({duration:.1f}s, {sample_rate}Hz)")
    except (wave.Error, ValueError) as e:
        print(f"Error: {e}")
        return

    # Setup audio playback device for real-time playback
    # User can select from available output devices
    audio_player = _setup_audio_player(sample_rate, channels, sample_width)

    # Configure Voice Agent with transcription settings
    config = VoiceAgentConfig(
        sample_rate=sample_rate,
        end_of_utterance_silence_trigger=0.5,
        enable_diarization=True,
        end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
        speaker_config=DiarizationSpeakerConfig(focus_speakers=["S2"], focus_mode=DiarizationFocusMode.IGNORE),
    )

    # Create Voice Agent client and start transcription
    async with VoiceAgentClient(config=config) as client:
        # Register event handlers for transcription events
        _register_event_handlers(client, logger)

        try:
            print("Starting transcription... (Press Ctrl+C to stop)\n")
            # Connect to the Voice Agent service
            await client.connect()

            # Stream the audio file with real-time playback
            await _stream_audio_file(audio_file_path, client, audio_player, sample_rate, sample_width)
        except asyncio.CancelledError:
            print("\nTranscription cancelled")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Clean up audio playback resources
            if audio_player:
                audio_player.stop()


def _load_audio_file(file_path: Path) -> tuple[int, int, int, float]:
    """Load and validate audio file.

    Returns:
        Tuple of (sample_rate, channels, sample_width, duration)
    """
    with wave.open(str(file_path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.getnframes()
        duration = frames / sample_rate

        if channels != 1:
            raise ValueError("Only mono audio files are supported")
        if sample_width != 2:
            raise ValueError("Only 16-bit audio files are supported")

        return sample_rate, channels, sample_width, duration


def _setup_audio_player(sample_rate: int, channels: int, sample_width: int) -> AudioPlayer | None:
    """Setup audio player with device selection."""
    print("\nSelect audio output device for playback:")
    output_device = select_audio_output_device()

    audio_player = AudioPlayer(sample_rate, channels, sample_width, output_device)
    if not audio_player.start():
        print("Warning: Audio playback unavailable - continuing with transcription only")
        return None
    return audio_player


def _register_event_handlers(client: VoiceAgentClient, logger) -> None:
    """Register event handlers for transcription events with detailed logging."""

    def _format_segment(segment: SpeakerSegment) -> str:
        """Format speaker segment for display."""
        template = "@{speaker_id} -> {text}" if segment.is_active else "@{speaker_id} (background) -> {text}"
        return segment.format_text(template)

    @client.on(AgentServerMessageType.ADD_SEGMENTS)
    def handle_final_segments(message):
        """Handle final transcription segments."""
        segments = [_format_segment(s) for s in message["segments"]]
        logger.log(CustomLevels.FINAL, f"🚀 {segments}")

    @client.on(AgentServerMessageType.ADD_INTERIM_SEGMENTS)
    def handle_partial_segments(message):
        """Handle partial transcription segments."""
        segments = [_format_segment(s) for s in message["segments"]]
        delay = message.get("delay_to_finalize")
        if delay is not None:
            logger.log(CustomLevels.PARTIAL, f"⚡ {segments} ({delay}s to finals)")
        else:
            logger.log(CustomLevels.PARTIAL, f"⚡ {segments}")

    @client.on(AgentServerMessageType.USER_SPEECH_STARTED)
    def handle_speech_started(message):
        """Handle speech start events."""
        logger.log(CustomLevels.SPEAKER, f"✅ Speech started: {message}")

    @client.on(AgentServerMessageType.USER_SPEECH_ENDED)
    def handle_speech_ended(message):
        """Handle speech end events."""
        logger.log(CustomLevels.SPEAKER, f"🛑 Speech ended: {message}")

    @client.on(AgentServerMessageType.TTFB_METRICS)
    def handle_metrics(message):
        """Handle time-to-first-byte metrics."""
        logger.debug(f"📊 Metrics: {message}")


async def _stream_audio_file(
    file_path: Path,
    client: VoiceAgentClient,
    audio_player: AudioPlayer | None,
    sample_rate: int,
    sample_width: int,
) -> None:
    """Stream audio file in real-time to client and player."""
    CHUNK_SIZE = 320
    chunk_duration = CHUNK_SIZE / sample_rate / sample_width

    with wave.open(str(file_path), "rb") as wav_file:
        while True:
            audio_data = wav_file.readframes(CHUNK_SIZE)
            if not audio_data:
                print("\nEnd of file reached")
                break

            # Send to transcription and play audio simultaneously
            asyncio.create_task(client.send_audio(audio_data))
            if audio_player:
                audio_player.play(audio_data)

            await asyncio.sleep(chunk_duration)


if __name__ == "__main__":
    asyncio.run(main())
