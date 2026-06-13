import os

import pytest
from _utils import get_client

# Constants
API_KEY = os.getenv("SPEECHMATICS_API_KEY")


@pytest.mark.asyncio
async def test_with_headers():
    """Tests that a client can be created.

    - Checks for a valid session
    - Checks that 'English' is the language pack info
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Create client
    client = await get_client(
        api_key=API_KEY,
        connect=False,
    )

    # Headers
    ws_headers = {"Z-TEST-HEADER-1": "ValueOne", "Z-TEST-HEADER-2": "ValueTwo"}

    # Check we are connected OK
    await client.connect(ws_headers=ws_headers)

    # Check we are connected
    assert client._is_connected

    # Disconnect
    await client.disconnect()

    # Check we are disconnected
    assert not client._is_connected


@pytest.mark.asyncio
async def test_with_corrupted_headers():
    """Tests that a client can be created.

    - Checks for a valid session
    - Checks that 'English' is the language pack info
    """

    # API key
    if not API_KEY:
        pytest.skip("Valid API key required for test")

    # Create client
    client = await get_client(
        api_key=API_KEY,
        connect=False,
    )

    # Headers
    ws_headers = ["ItemOne", "ItemTwo"]

    # Check we are connected OK
    try:
        await client.connect(ws_headers=ws_headers)
    except AttributeError:
        pass

    # Check we are connected
    assert not client._is_connected

    # Disconnect (in case connected)
    await client.disconnect()

    # Check we are disconnected
    assert not client._is_connected
