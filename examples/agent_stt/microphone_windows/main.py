"""Live microphone transcription with the Agent STT service, set up for Windows.

The service runs its own VAD, so it decides where each turn ends; this script only captures
the microphone and prints what comes back. Partials are rewritten in place on one line and
each closed segment is printed above them.

Setup in PowerShell:

    py -m pip install speechmatics-agent-stt pyaudio
    $env:SPEECHMATICS_API_KEY = "your-key"
    py examples\\agent_stt\\microphone_windows\\main.py

Add `$env:SPEECHMATICS_RT_URL = "wss://preview.rt.speechmatics.com/v2"` to point at a
service. Use `--list-devices` and `--device N` when Windows picks the wrong input.
"""

import argparse
import asyncio
import signal
import sys

from speechmatics.agent_stt import AsyncClient
from speechmatics.agent_stt import Microphone
from speechmatics.agent_stt import ServerMessageType
from speechmatics.agent_stt import TranscriptionConfig

SAMPLE_RATE = 16000
CHUNK_SIZE = 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list-devices", action="store_true", help="list input devices and exit")
    parser.add_argument("--device", type=int, help="input device index, from --list-devices")
    parser.add_argument("--language", default="en")
    parser.add_argument("--diarization", action="store_true", help="label segments by speaker")
    parser.add_argument("--no-partials", action="store_true")
    return parser.parse_args()


class Console:
    """Keeps the partial on one rewritten line, with finals printed above it."""

    def __init__(self) -> None:
        self._partial_width = 0

    def partial(self, text: str) -> None:
        line = f"[partial] {text}"
        print("\r" + line.ljust(self._partial_width), end="", flush=True)
        self._partial_width = len(line)

    def line(self, text: str) -> None:
        print("\r" + text.ljust(self._partial_width), flush=True)
        self._partial_width = 0


def list_devices() -> None:
    devices = Microphone.list_devices()
    if not devices:
        print("No input devices found. Is pyaudio installed, and does Windows list a microphone?")
        return
    for device in devices:
        print(f"  {device['index']:>2}  {device['name']} ({device['channels']} ch)")


def build_client(args: argparse.Namespace, console: Console) -> AsyncClient:
    config = TranscriptionConfig(
        language=args.language,
        enable_partials=not args.no_partials,
        diarization="speaker" if args.diarization else None,
    )

    # Uses SPEECHMATICS_API_KEY, and SPEECHMATICS_RT_URL to point at a local service
    client = AsyncClient(config=config)

    @client.on(ServerMessageType.ADD_PARTIAL_SEGMENT)
    def handle_partial_segment(message):
        console.partial(message["segment"]["transcript"])

    @client.on(ServerMessageType.ADD_SEGMENT)
    def handle_segment(message):
        segment = message["segment"]
        speaker = f"{segment['speaker']}: " if segment.get("speaker") else ""
        console.line(f"[final]   {speaker}{segment['transcript']}")

    @client.on(ServerMessageType.END_OF_TURN)
    def handle_end_of_turn(message):
        console.line(f"[turn]    end at {message['metadata']['end_time']:.2f}s")

    @client.on(ServerMessageType.ERROR)
    def handle_error(message):
        console.line(f"[error]   {message}")

    return client


async def capture(client: AsyncClient, mic: Microphone, stop: asyncio.Event) -> None:
    """Pump microphone frames until Ctrl+C, which sets `stop`."""
    while not stop.is_set():
        await client.send_audio(await mic.read(CHUNK_SIZE))


async def main() -> None:
    args = parse_args()

    if args.list_devices:
        list_devices()
        return

    mic = Microphone(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE, device_index=args.device)
    if not mic.is_available:
        print("pyaudio is not installed. Install it with: py -m pip install pyaudio")
        return
    if not mic.start():
        print(f"Could not open the microphone at {SAMPLE_RATE} Hz. Available inputs:")
        list_devices()
        print(
            "\nPick one with --device N. If none open, set the device's Default Format to\n"
            "16000 Hz in Sound Control Panel > Recording > Properties > Advanced."
        )
        return

    # Ctrl+C on Windows will not interrupt a pending await, so shut down through an event
    stop = asyncio.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    console = Console()
    client = build_client(args, console)

    try:
        async with client:
            print("\nMicrophone ready - speak now (Ctrl+C to stop)\n")
            await capture(client, mic, stop)
    finally:
        mic.stop()

    console.line("")
    print(f"Transcript: {client.transcript_text(speaker_labels=args.diarization)}")


# Windows spawns child processes by re-importing this file, so keep startup behind the guard
if __name__ == "__main__":
    # The Windows console defaults to a legacy code page that cannot print every transcript
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    asyncio.run(main())
