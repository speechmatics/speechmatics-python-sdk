import asyncio
import datetime
import json
import os
import time
import wave
from typing import Any
from typing import Callable
from typing import Optional

import aiofiles

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig


async def get_client(
    api_key: Optional[str] = None,
    url: Optional[str] = None,
    app: Optional[str] = None,
    config: Optional[VoiceAgentConfig] = None,
    connect: bool = True,
) -> VoiceAgentClient:
    """Get a client."""

    # Create client
    client = VoiceAgentClient(api_key=api_key, url=url, app=app, config=config)

    # Connect
    if connect:
        """Connect to the client and wait for the RECOGNITION_STARTED event."""

        # Create an event to track when the callback is called
        event_received = asyncio.Event()
        received_message = None

        # Callback function for connection
        def on_recognition_started(message):
            nonlocal received_message
            received_message = message
            event_received.set()

        # Add listener for when recognition starts
        client.once(AgentServerMessageType.RECOGNITION_STARTED, on_recognition_started)

        # Connect
        await client.connect()

        # Wait for the callback with a 5-second timeout
        try:
            await asyncio.wait_for(event_received.wait(), timeout=5.0)
            assert received_message is not None
        except asyncio.TimeoutError:
            raise TimeoutError("RECOGNITION_STARTED event was not received within 5 seconds")

    # Return client
    return client


async def send_audio_file(
    client: VoiceAgentClient,
    audio_file: str,
    terminate_event: Optional[asyncio.Event] = None,
    chunk_size: int = 320,
    sample_rate: int = 16000,
    sample_size: int = 2,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """Send audio data to the API server."""

    # Make sure client is connected
    assert client._is_connected

    # Make sure file ends with .wav
    assert audio_file.lower().endswith(".wav")

    # Check file exists
    file = os.path.join(os.path.dirname(__file__), audio_file)
    assert os.path.exists(file)

    # Make sure progress callback is callable
    if progress_callback:
        assert callable(progress_callback)

    # Delay is based off 16kHz int16 and chunk size
    delay = chunk_size / sample_rate / sample_size

    # Catch errors - we can be lazy as this is only for testing
    try:

        # Load the file
        async with aiofiles.open(file, "rb") as wav_file:
            # Trim off the WAV file header
            await wav_file.seek(44)

            # Send audio data
            next_time = time.perf_counter() + delay
            while not terminate_event.is_set() if terminate_event else True:
                """Reads all chunks until the end of the file with precision delay."""

                # Read chunk
                chunk = await wav_file.read(chunk_size)

                # End of file
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

    # Catch errors
    except Exception:
        pass


async def load_audio_file(audio_file: str) -> bytes:
    """Load an audio file."""

    # Make sure file ends with .wav
    assert audio_file.lower().endswith(".wav")

    # Check file exists
    file = os.path.join(os.path.dirname(__file__), audio_file)
    assert os.path.exists(file)

    # Load the file
    with wave.open(file, "rb") as wav_file:
        return wav_file.readframes(wav_file.getnframes())


async def send_silence(
    client: VoiceAgentClient,
    duration: float,
    terminate_event: Optional[asyncio.Event] = None,
    chunk_size: int = 320,
    sample_rate: int = 16000,
    sample_size: int = 2,
    progress_callback: Optional[Callable[[int], None]] = None,
):
    """Send silence to the client (creates a chunk of silence and sends it to the client)"""

    # Make sure client is connected
    assert client._is_connected

    # Make sure duration is positive
    assert duration > 0

    # Make sure chunk size is positive
    assert chunk_size > 0

    # Make sure progress callback is callable
    if progress_callback:
        assert callable(progress_callback)

    # Send silence
    silence = b"\x00" * chunk_size

    # Timing
    delay = chunk_size / sample_rate / sample_size
    next_time = time.perf_counter() + delay

    # Iterations required
    iterations = int(duration / delay)

    # Catch errors - we can be lazy as this is only for testing
    try:

        # Keep sending
        while (not terminate_event.is_set() if terminate_event else True) and iterations > 0:
            # Send audio to client
            await client.send_audio(silence)

            # Do any callbacks
            if progress_callback:
                progress_callback(len(silence))

            # Precision delay
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            next_time += delay

            # Reduce iterations
            iterations -= 1

    # Catch errors - we can be lazy as this is only for testing
    except Exception:
        pass


def log_client_messages(client: VoiceAgentClient, messages: list[AgentServerMessageType] | None = None) -> None:
    """Register and log client messages."""

    # Start time
    start_time = datetime.datetime.now()

    # Callback for each message
    def _log_message(message):
        ts = (datetime.datetime.now() - start_time).total_seconds()
        print(json.dumps({"ts": round(ts, 3), "payload": message}))

    # Set fo all agent messages, apart from AUDIO_ADDED
    if messages is None:
        messages = [message for message in AgentServerMessageType if message != AgentServerMessageType.AUDIO_ADDED]

    # Add listeners
    for message_type in messages:
        client.on(message_type, _log_message)


class ConversationLog:
    """Load a JSONL past conversation."""

    def __init__(self, file: str):
        """Load a JSONL past conversation.

        Args:
            file (str): Path to the JSONL file.
        """
        self.file = file
        self.conversation = self._load_conversation()

    def _load_conversation(self):
        """Load a JSONL past conversation."""
        with open(self.file) as f:
            return [json.loads(line) for line in f]

    def get_conversation(self, filter: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Get the conversation."""
        try:
            if filter:
                return [line for line in self.conversation if line["payload"]["message"] in filter]
            return list(self.conversation)
        except KeyError:
            return []
