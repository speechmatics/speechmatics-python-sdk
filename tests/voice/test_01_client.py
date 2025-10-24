import os

import pytest
from _utils import get_client

from speechmatics.voice import VoiceAgentClient
from speechmatics.voice import VoiceAgentConfig


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
    assert client._client_session.session_id != "NOT_SET"
    assert client._client_session.language_pack_info is not None
    assert client._client_session.language_pack_info.language_description == "English"


@pytest.mark.asyncio
async def test_client_context_manager():
    """Tests that a client can be used as an async context manager.

    - Checks that connection is established automatically on enter
    - Checks that disconnection happens automatically on exit
    - Verifies session info is set correctly
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Create config
    config = VoiceAgentConfig(language="en")

    # Use client as context manager
    async with VoiceAgentClient(api_key=api_key, config=config) as client:
        # Check we are connected automatically
        assert client._is_connected

        # Check session info is set
        assert client._client_session.session_id != "NOT_SET"
        assert client._client_session.language_pack_info is not None
        assert client._client_session.language_pack_info.language_description == "English"

    # After exiting context, client should be disconnected
    assert not client._is_connected


@pytest.mark.asyncio
async def test_client_context_manager_with_exception():
    """Tests that context manager properly cleans up even when an exception occurs.

    - Checks that disconnection happens even if an exception is raised
    - Verifies exception is propagated correctly
    """

    # API key
    api_key = os.getenv("SPEECHMATICS_API_KEY")
    if not api_key:
        pytest.skip("Valid API key required for test")

    # Create config
    config = VoiceAgentConfig(language="en")

    # Use client as context manager and raise an exception
    with pytest.raises(ValueError, match="Test exception"):
        async with VoiceAgentClient(api_key=api_key, config=config) as client:
            # Check we are connected
            assert client._is_connected

            # Raise an exception
            raise ValueError("Test exception")

    # After exiting context (even with exception), client should be disconnected
    assert not client._is_connected
