import os

import pytest
from _utils import get_client


@pytest.mark.asyncio
async def test_client():
    """Tests that a client can be created."""

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Create client
    client = await get_client(api_key=api_key, connect=False)

    # Check we are connected OK
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Disconnect
    await client.disconnect()

    # Check we are disconnected
    assert not client._is_connected
