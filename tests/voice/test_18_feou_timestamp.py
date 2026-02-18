import os

import pytest
from _utils import get_client
from _utils import send_silence

from speechmatics.voice import VoiceAgentConfig

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping in CI")
pytestmark = pytest.mark.skipif(API_KEY is None, reason="Skipping when no API key is provided")

# Endpoints
ENDPOINTS: list[str] = [
    "wss://eu.rt.speechmatics.com/v2",
]

# How much silence to send (seconds)
SILENCE_DURATION = 3.0

# Tolerance for the timestamp check
TOLERANCE = 0.00


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_feou_timestamp(endpoint: str):
    """Test that audio_seconds_sent correctly computes elapsed audio time.

    Sends 3 seconds of silence (zero bytes) and verifies that the
    audio_seconds_sent property on the client returns a value close to 3.0,
    accounting for the configured sample rate and encoding.
    """

    # Create and connect client
    config = VoiceAgentConfig()
    client = await get_client(
        url=endpoint,
        api_key=API_KEY,
        connect=False,
        config=config,
    )

    try:
        await client.connect()
    except Exception:
        pytest.skip("Failed to connect to server")

    assert client._is_connected

    # Send 3 seconds of silence
    await send_silence(client, duration=SILENCE_DURATION)

    # Check the computed audio seconds
    actual_seconds = client.audio_seconds_sent
    assert (
        abs(actual_seconds - SILENCE_DURATION) <= TOLERANCE
    ), f"Expected ~{SILENCE_DURATION}s but got {actual_seconds:.4f}s"

    # Clean up
    await client.disconnect()
    assert not client._is_connected
