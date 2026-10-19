"""Drive turn boundaries from the application instead of the service.

This is the mode host frameworks use: Pipecat, LiveKit and others already run a VAD, so the
service's VAD is switched off and each turn is closed by calling `finalize()`, which sends
ForceEndOfUtterance stamped with the audio position at the moment of the call.

The fixed interval below stands in for the host framework's own end-of-speech signal.

Run with: python examples/agent_stt/client_vad/main.py [path/to/8kHz-or-16kHz.wav]
"""

import asyncio
import sys
import wave

from speechmatics.agent_stt import DEFAULT_CHUNK_SIZE
from speechmatics.agent_stt import SUPPORTED_SAMPLE_RATES
from speechmatics.agent_stt import AgentSttAsyncClient
from speechmatics.agent_stt import AudioEncoding
from speechmatics.agent_stt import AudioFormat
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import TurnConfig
from speechmatics.agent_stt import TurnDetectionMode

DEFAULT_AUDIO_FILE = "./tests/voice/assets/audio_01_16kHz.wav"
TURN_SECONDS = 5.0


async def main(path: str) -> None:
    transcription_config = TranscriptionConfig(language="en", enable_partials=True)
    turn_config = TurnConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL)

    with wave.open(path, "rb") as wav:
        sample_rate = wav.getframerate()
        if sample_rate not in SUPPORTED_SAMPLE_RATES:
            print(f"{path} is {sample_rate} Hz; the Agent STT service needs 8 kHz or 16 kHz audio")
            return
        audio_format = AudioFormat(
            encoding=AudioEncoding.PCM_S16LE,
            sample_rate=sample_rate,
            chunk_size=DEFAULT_CHUNK_SIZE,
        )

        # Uses SPEECHMATICS_API_KEY from the environment
        client = AgentSttAsyncClient(
            transcription_config=transcription_config,
            turn_config=turn_config,
            audio_format=audio_format,
        )

        # Registered before the session opens, so no message can arrive unhandled
        @client.on(ServerMessageType.ADD_SEGMENT)
        def handle_segment(message):
            print(f"[final] {message['segment']['transcript']}")

        async with client:
            next_turn_end = TURN_SECONDS
            while True:
                frame = wav.readframes(DEFAULT_CHUNK_SIZE // wav.getsampwidth())
                if not frame:
                    break
                await client.send_audio(frame)

                if client.audio_seconds_sent >= next_turn_end:
                    print(f"[client vad] end of turn at {client.audio_seconds_sent:.2f}s")
                    await client.force_end_of_utterance()
                    next_turn_end += TURN_SECONDS

    print(f"\nTranscript: {client.transcript}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIO_FILE))
