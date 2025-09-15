import asyncio

from colorama import init as colorama_init
from utils import CustomLevels
from utils import get_logger
from utils import select_audio_device

from speechmatics.rt import Microphone
from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import DiarizationSpeakerConfig
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig

colorama_init(autoreset=True)

logger = get_logger(__name__)


async def main() -> None:
    """
    Live microphone transcription with speaker diarisation.

    This example demonstrates:
    - Real-time microphone input with device selection
    - Speaker diarisation and voice activity detection
    - Performance metrics (TTFB)
    - Works with any PyAudio-compatible input device
    """

    # Audio configuration for real-time processing
    sample_rate = 16000
    chunk_size = 320

    # Setup microphone with user device selection
    mic = _setup_microphone(sample_rate, chunk_size)
    if not mic:
        return

    # Configure Voice Agent with microphone-specific settings
    config = VoiceAgentConfig(
        sample_rate=sample_rate,
        end_of_utterance_silence_trigger=0.5,
        enable_diarization=True,
        end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
        speaker_config=DiarizationSpeakerConfig(focus_speakers=["S1"]),
    )

    # Create Voice Agent client and start transcription
    async with VoiceAgentClient(config=config) as client:
        # Register event handlers for real-time transcription events
        _register_event_handlers(client, logger)

        try:
            print("Microphone ready - speak now... (Press Ctrl+C to stop)\n")
            # Connect to the Voice Agent service
            await client.connect()

            # Start streaming microphone audio
            await _stream_microphone(mic, client, chunk_size)
        except asyncio.CancelledError:
            print("\nTranscription cancelled")
        except Exception as e:
            print(f"Error: {e}")


def _register_event_handlers(client: VoiceAgentClient, logger) -> None:
    """Register event handlers for real-time transcription events."""

    def _format_segment(segment) -> str:
        """Format speaker segment for display."""
        template = "@{speaker_id}: {text}" if segment.is_active else "@{speaker_id} (background): {text}"
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

    @client.on(AgentServerMessageType.TTFB_METRICS)
    def handle_metrics(message):
        """Handle time-to-first-byte metrics."""
        logger.debug(f"📊 Metrics: {message}")


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
    while True:
        frame = await mic.read(chunk_size)
        await client.send_audio(frame)


if __name__ == "__main__":
    asyncio.run(main())
