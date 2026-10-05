import os

import pytest
from _utils import get_client
from _utils import send_silence

from speechmatics.rt import AudioEncoding
from speechmatics.voice import VoiceAgentConfig

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping in CI")
pytestmark = pytest.mark.skipif(API_KEY is None, reason="Skipping when no API key is provided")

# How much silence to send (seconds)
SILENCE_DURATION = 3.0

# Tolerance for the timestamp check
TOLERANCE = 0.00

# Audio format configurations to test: (encoding, chunk_size, bytes_per_sample)
AUDIO_FORMATS = [
    pytest.param(AudioEncoding.PCM_S16LE, 160, 2, id="s16-chunk160"),
    pytest.param(AudioEncoding.PCM_S16LE, 320, 2, id="s16-chunk320"),
    pytest.param(AudioEncoding.PCM_F32LE, 160, 4, id="f32-chunk160"),
    pytest.param(AudioEncoding.PCM_F32LE, 320, 4, id="f32-chunk320"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding,chunk_size,sample_size", AUDIO_FORMATS)
async def test_feou_timestamp(encoding: AudioEncoding, chunk_size: int, sample_size: int):
    """Test that audio_seconds_sent correctly computes elapsed audio time.

    Sends 3 seconds of silence (zero bytes) with different audio encodings
    and chunk sizes, then verifies that audio_seconds_sent returns the
    correct duration.
    """

    # Create and connect client
    config = VoiceAgentConfig(audio_encoding=encoding, chunk_size=chunk_size)
    client = await get_client(
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
    await send_silence(
        client,
        duration=SILENCE_DURATION,
        chunk_size=chunk_size,
        sample_size=sample_size,
    )

    # Check the computed audio seconds
    actual_seconds = client.audio_seconds_sent
    assert (
        abs(actual_seconds - SILENCE_DURATION) <= TOLERANCE
    ), f"Expected ~{SILENCE_DURATION}s but got {actual_seconds:.4f}s"

    # Clean up
    await client.disconnect()
    assert not client._is_connected
