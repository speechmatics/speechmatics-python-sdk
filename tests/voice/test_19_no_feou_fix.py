import json
import os
import shutil
import time

import pytest
from _utils import get_client
from _utils import send_audio_file

from speechmatics.voice import AgentServerMessageType
from speechmatics.voice import EndOfTurnConfig
from speechmatics.voice import EndOfUtteranceMode
from speechmatics.voice import SmartTurnConfig
from speechmatics.voice import VoiceActivityConfig
from speechmatics.voice import VoiceAgentConfig

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping transcription tests in CI")

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")
SHOW_LOG = os.getenv("SPEECHMATICS_SHOW_LOG", "0").lower() in ["1", "true"]


@pytest.mark.asyncio
async def test_no_feou_fix():
    """Test for when FEOU is disabled."""

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Config
    config = VoiceAgentConfig(
        language="en",
        end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
        end_of_utterance_silence_trigger=0.5,
        smart_turn_config=SmartTurnConfig(enabled=True, smart_turn_threshold=0.80),
        vad_config=VoiceActivityConfig(enabled=True),
        end_of_turn_config=EndOfTurnConfig(base_multiplier=1.0),
    )

    # Debug config
    print(
        config.to_json(
            indent=2,
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )
    )

    # Client
    client = await get_client(
        api_key=API_KEY,
        connect=False,
        config=config,
    )

    # Disable FEOU
    client._use_forced_eou = False

    # Add listeners
    messages = [message for message in AgentServerMessageType if message != AgentServerMessageType.AUDIO_ADDED]

    # Colors for messages
    colors = {
        "StartOfTurn": "\033[94m",  # Blue
        "EndOfTurn": "\033[92m",  # Green
        "AddSegment": "\033[93m",  # Yellow
        "AddPartialSegment": "\033[38;5;208m",  # Orange
        "SpeakerStarted": "\033[96m",  # Cyan
        "SpeakerEnded": "\033[95m",  # Magenta
        "VadStatus": "\033[91m",  # Red
    }

    # Callback for each message
    term_width = shutil.get_terminal_size().columns
    log_start_time = time.monotonic()

    def log_message(message):
        """Log a message with color and formatting."""

        # Elapsed time in seconds (right-aligned, capacity for 100s)
        elapsed = time.monotonic() - log_start_time
        timestamp = f"{elapsed:>7.3f}"

        # Extract message type and remaining payload (drop noisy keys)
        msg_type = message.get("message", "")
        rest = {k: v for k, v in message.items() if k not in ("message", "format")}

        # Color based on message type (default: dark gray)
        color = colors.get(msg_type, "\033[90m")
        reset = "\033[0m"

        # Format: timestamp - fixed-width type label + JSON payload
        label = f"{msg_type:<20}"
        payload = json.dumps(rest, default=str)
        visible = f"{timestamp} - {label} - {payload}"

        # Truncate to terminal width to prevent wrapping
        if len(visible) > term_width:
            visible = visible[: term_width - 1] + "…"

        # Print with color
        print(f"{color}{visible}{reset}")

    # Add listeners
    for message_type in messages:
        client.on(message_type, log_message)

    # Load the audio file `./assets/audio_01_16kHz.wav`
    # audio_file = "../../tmp/feou/recording-appointment.wav"
    audio_file = "./assets/audio_10_16kHz.wav"

    # HEADER
    if SHOW_LOG:
        print()
        print()
        print("---")

    # Connect
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Individual payloads
    await send_audio_file(client, audio_file)

    # Close session
    await client.disconnect()
    assert not client._is_connected

    # FOOTER
    if SHOW_LOG:
        print("---")
        print()
        print()
