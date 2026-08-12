"""Transcribe a 16 kHz WAV file with the Agent STT service.

The service runs its own VAD here, so it reports speech and turn events and closes each
segment itself. The whole transcript is on the client when the session ends.

Run with: python examples/agent_stt/file/main.py [path/to/16kHz.wav]
"""

import asyncio
import sys
import wave

from speechmatics.agent_stt import AsyncClient
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig

DEFAULT_AUDIO_FILE = "./tests/voice/assets/audio_01_16kHz.wav"


class WavSource:
    """Reads raw PCM frames out of a WAV file, leaving the header behind."""

    def __init__(self, wav: wave.Wave_read) -> None:
        self._wav = wav

    def read(self, size: int) -> bytes:
        return self._wav.readframes(size // self._wav.getsampwidth())


async def main(path: str) -> None:
    # Uses SPEECHMATICS_API_KEY from the environment
    client = AsyncClient(config=TranscriptionConfig(language="en", enable_partials=True))

    @client.on(ServerMessageType.ADD_PARTIAL_SEGMENT)
    def handle_partial_segment(message):
        print(f"[partial] {message['segment']['transcript']}")

    @client.on(ServerMessageType.ADD_SEGMENT)
    def handle_segment(message):
        print(f"[final]   {message['segment']['transcript']}")

    @client.on(ServerMessageType.START_OF_TURN)
    def handle_start_of_turn(message):
        print(f"[turn]    start at {message['metadata']['start_time']}s")

    @client.on(ServerMessageType.END_OF_TURN)
    def handle_end_of_turn(message):
        print(f"[turn]    end at {message['metadata']['end_time']}s")

    with wave.open(path, "rb") as wav:
        if wav.getframerate() != 16000:
            print(f"{path} is {wav.getframerate()} Hz; the Agent STT service needs 16 kHz audio")
            return
        await client.transcribe(WavSource(wav))

    print(f"\nTranscript: {client.transcript}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_AUDIO_FILE))
