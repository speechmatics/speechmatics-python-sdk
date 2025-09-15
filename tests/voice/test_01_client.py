import os

import pytest
from _utils import get_client


@pytest.mark.asyncio
async def test_client():
    """Tests that a client can be created.

    - Checks for a valid session
    - Checks that 'English' is the language pack info
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Create client
    client = await get_client(
        api_key=api_key,
        connect=False,
    )

    # Check we are connected OK
    await client.connect()

    # Check we are connected
    assert client._is_connected

    # Disconnect
    await client.disconnect()

    # Check we are disconnected
    assert not client._is_connected

    # Check session info
    assert client._session_id is not None
    assert client._language_pack_info is not None
    assert client._language_pack_info.language_description == "English"
