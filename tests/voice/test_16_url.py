import pytest
from _utils import get_client


@pytest.mark.asyncio
async def test_url_endpoints():
    """Test URL endpoint construction."""

    # Client
    client = await get_client(
        api_key="DUMMY",
        connect=False,
    )

    # URL test #1 - no extra params
    url = client._get_endpoint_url("wss://dummy/ep", "dummy-0.1.2")
    assert url == "wss://dummy/ep?sm-app=dummy-0.1.2&sm-voice-sdk=0.0.0"

    # URL test #2 - with extra params
    url = client._get_endpoint_url("wss://dummy:1234/ep?client=amz", "dummy-0.1.2")
    assert url == "wss://dummy:1234/ep?client=amz&sm-app=dummy-0.1.2&sm-voice-sdk=0.0.0"

    # URL test #3 - with sm-app param
    url = client._get_endpoint_url("wss://dummy/ep?sm-app=dummy")
    assert url == "wss://dummy/ep?sm-app=dummy&sm-voice-sdk=0.0.0"

    # URL test #4 - with sm-app param and different app
    url = client._get_endpoint_url("ws://localhost:8080/ep?sm-app=dummy", "dummy-0.1.2")
    assert url == "ws://localhost:8080/ep?sm-app=dummy-0.1.2&sm-voice-sdk=0.0.0"

    # URL test #5 - http endpoint (not actually possible, but a good test)
    url = client._get_endpoint_url("http://dummy/ep/v1/", "dummy-0.1.2")
    assert url == "http://dummy/ep/v1/?sm-app=dummy-0.1.2&sm-voice-sdk=0.0.0"
