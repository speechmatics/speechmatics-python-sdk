"""Stream a 16 kHz WAV file to the Agent STT service at wall-clock speed.

A file read at full speed reaches the service far ahead of real time, so VAD windows, turn
boundaries and latency all read wrong. This paces the send loop so each frame leaves at the
moment its audio would have been captured live, and prints how far behind the audio position
every message arrives - the number worth watching when testing locally.

Run with: python examples/agent_stt/realtime_file/main.py [path/to/16kHz.wav]
"""

import argparse
import asyncio
import time
import wave
from typing import Optional

from speechmatics.agent_stt import AgentSttAsyncClient
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import TurnConfig
from speechmatics.agent_stt import TurnDetectionMode

DEFAULT_AUDIO_FILE = "./tests/voice/assets/audio_01_16kHz.wav"
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("audio", nargs="?", default=DEFAULT_AUDIO_FILE, help="16 kHz mono WAV file")
    parser.add_argument("--language", default="en")
    parser.add_argument("--chunk-ms", type=float, default=20.0, help="audio frame size in milliseconds")
    parser.add_argument(
        "--turn-detection",
        choices=[TurnDetectionMode.VAD.value, TurnDetectionMode.EXTERNAL.value],
        default=TurnDetectionMode.VAD.value,
        help="which mechanism closes turns: the service's VAD, or this script calling finalize()",
    )
    parser.add_argument(
        "--turn-seconds", type=float, default=5.0, help="fake turn length, --turn-detection external only"
    )
    parser.add_argument("--no-partials", action="store_true")
    return parser.parse_args()


class Clock:
    """Wall clock for the streaming run, and the lag of each message behind the audio."""

    def __init__(self) -> None:
        self._started_at = time.monotonic()
        self.segment_lags = []

    def start(self) -> None:
        """Reset to zero, so the connection handshake does not count as streaming time."""
        self._started_at = time.monotonic()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started_at

    def log(self, tag: str, text: str, *, audio_time: Optional[float] = None, record: bool = False) -> None:
        lag = ""
        if audio_time is not None:
            behind = self.elapsed - audio_time
            if record:
                self.segment_lags.append(behind)
            lag = f"+{behind * 1000:>5.0f}ms"
        print(f"[{self.elapsed:6.2f}s] {tag:<17}{lag:<10} {text}")


def build_client(args: argparse.Namespace, clock: Clock) -> AgentSttAsyncClient:
    config = TranscriptionConfig(
        language=args.language,
        enable_partials=not args.no_partials,
    )
    turn_config = TurnConfig(turn_detection_mode=TurnDetectionMode(args.turn_detection))

    # Uses SPEECHMATICS_API_KEY, and SPEECHMATICS_RT_URL to point at a local service
    client = AgentSttAsyncClient(config=config, turn_config=turn_config)

    @client.on(ServerMessageType.ADD_PARTIAL_SEGMENT)
    def handle_partial_segment(message):
        clock.log("[partial]", message["segment"]["transcript"], audio_time=message["metadata"]["end_time"])

    @client.on(ServerMessageType.ADD_SEGMENT)
    def handle_segment(message):
        clock.log(
            "[final]",
            message["segment"]["transcript"],
            audio_time=message["metadata"]["end_time"],
            record=True,
        )

    @client.on(ServerMessageType.SPEECH_STARTED)
    def handle_speech_started(message):
        clock.log("[speech started]", f"{message['metadata']['start_time']:.2f}s")

    @client.on(ServerMessageType.SPEECH_ENDED)
    def handle_speech_ended(message):
        clock.log("[speech ended]", f"{message['metadata']['end_time']:.2f}s")

    @client.on(ServerMessageType.START_OF_TURN)
    def handle_start_of_turn(message):
        clock.log("[turn started]", f"{message['metadata']['start_time']:.2f}s")

    @client.on(ServerMessageType.END_OF_TURN)
    def handle_end_of_turn(message):
        end_time = message["metadata"]["end_time"]
        clock.log("[turn ended]", f"{end_time:.2f}s", audio_time=end_time)

    @client.on(ServerMessageType.ERROR)
    def handle_error(message):
        clock.log("[error]", str(message))

    return client


async def stream(client: AgentSttAsyncClient, wav: wave.Wave_read, args: argparse.Namespace, clock: Clock) -> None:
    """Send the file frame by frame, releasing each frame no earlier than its capture time."""
    frames_per_chunk = int(SAMPLE_RATE * args.chunk_ms / 1000)
    next_turn_end = args.turn_seconds
    clock.start()

    while frame := wav.readframes(frames_per_chunk):
        # Hold each frame until the wall clock reaches the end of the audio it carries, so a
        # frame leaves exactly when a live capture would have finished recording it. Paced off
        # the session clock rather than per-frame sleeps, so the send does not drift.
        frame_end = client.audio_seconds_sent + len(frame) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
        early = frame_end - clock.elapsed
        if early > 0:
            await asyncio.sleep(early)

        await client.send_audio(frame)

        if args.turn_detection == TurnDetectionMode.EXTERNAL.value and client.audio_seconds_sent >= next_turn_end:
            clock.log("[external]", f"end of turn at {client.audio_seconds_sent:.2f}s")
            await client.force_end_of_utterance()
            next_turn_end += args.turn_seconds


async def main() -> None:
    args = parse_args()
    clock = Clock()
    client = build_client(args, clock)

    with wave.open(args.audio, "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (SAMPLE_RATE, 1, BYTES_PER_SAMPLE):
            print(f"{args.audio} must be 16 kHz mono 16-bit PCM for the Agent STT service")
            return
        duration = wav.getnframes() / SAMPLE_RATE

        async with client:
            await stream(client, wav, args, clock)

    print(f"\nTranscript: {client.transcript}")
    print(f"Streamed {duration:.2f}s of audio in {clock.elapsed:.2f}s")
    if clock.segment_lags:
        mean = sum(clock.segment_lags) / len(clock.segment_lags)
        print(f"Final segment lag behind audio: mean {mean * 1000:.0f}ms, max {max(clock.segment_lags) * 1000:.0f}ms")


asyncio.run(main())
