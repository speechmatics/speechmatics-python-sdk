from dataclasses import dataclass
from typing import Optional

import pytest
from _utils import get_client

from speechmatics.voice import __version__


@dataclass
class URLExample:
    input_url: str
    input_app: Optional[str] = None
    expected_url: str = ""


URLS: list[URLExample] = [
    URLExample(
        input_url="wss://dummy/ep",
        input_app="dummy-0.1.2",
        expected_url="wss://dummy/ep?sm-app=dummy-0.1.2&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="wss://dummy:1234/ep?client=amz",
        input_app="dummy-0.1.2",
        expected_url="wss://dummy:1234/ep?client=amz&sm-app=dummy-0.1.2&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="wss://dummy/ep?sm-app=dummy",
        expected_url="wss://dummy/ep?sm-app=dummy&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="ws://localhost:8080/ep?sm-app=dummy",
        input_app="dummy-0.1.2",
        expected_url="ws://localhost:8080/ep?sm-app=dummy-0.1.2&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="http://dummy/ep/v1/",
        input_app="dummy-0.1.2",
        expected_url="http://dummy/ep/v1/?sm-app=dummy-0.1.2&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="wss://dummy/ep",
        expected_url="wss://dummy/ep?sm-app=voice-sdk%2F0.0.0&sm-voice-sdk={v}",
    ),
    URLExample(
        input_url="wss://dummy/ep",
        input_app="client/a#b:c^d",
        expected_url="wss://dummy/ep?sm-app=client%2Fa%23b%3Ac%5Ed&sm-voice-sdk={v}",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("test", URLS, ids=lambda s: s.input_url)
async def test_url_endpoints(test: URLExample):
    """Test URL endpoint construction."""

    # Client
    client = await get_client(
        api_key="DUMMY",
        connect=False,
    )

    # URL test
    url = client._get_endpoint_url(test.input_url, test.input_app)
    assert url == test.expected_url.format(v=__version__)
