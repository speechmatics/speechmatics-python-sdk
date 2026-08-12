"""Drive turn boundaries from the client instead of the service.

This is the mode host frameworks use: Pipecat, LiveKit and others already run a VAD, so the
service's VAD is switched off and each turn is closed by calling `finalize()`, which sends
ForceEndOfUtterance stamped with the audio position at the moment of the call.

The fixed interval below stands in for the host framework's own end-of-speech signal.

Run with: python examples/agent_stt/client_vad/main.py [path/to/16kHz.wav]
"""

import asyncio
import sys
import wave

from speechmatics.agent_stt import AsyncClient
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import VADMode

DEFAULT_AUDIO_FILE = "./tests/voice/assets/audio_01_16kHz.wav"
CHUNK_SIZE = 1024
TURN_SECONDS = 5.0


async def main(path: str) -> None:
    config = TranscriptionConfig(language="en", enable_partials=True, vad_mode=VADMode.CLIENT)

    # Uses SPEECHMATICS_API_KEY from the environment
    async with AsyncClient(config=config) as client:

        @client.on(ServerMessageType.ADD_SEGMENT)
        def handle_segment(message):
            print(f"[final] {message['segment']['transcript']}")

        with wave.open(path, "rb") as wav:
            if wav.getframerate() != 16000:
                print(f"{path} is {wav.getframerate()} Hz; the Agent STT service needs 16 kHz audio")
                return

            next_turn_end = TURN_SECONDS
            while True:
                frame = wav.readframes(CHUNK_SIZE // wav.getsampwidth())
                if not frame:
                    break
                await client.send_audio(frame)

                if client.audio_seconds_sent >= next_turn_end:
                    print(f"[client vad] end of turn at {client.audio_seconds_sent:.2f}s")
                    await client.force_end_of_utterance()
                    next_turn_end += TURN_SECONDS

    print(f"\nTranscript: {client.transcript}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIO_FILE))
