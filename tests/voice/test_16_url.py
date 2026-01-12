from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs
from urllib.parse import urlparse

import pytest
from _utils import get_client

from speechmatics.voice import __version__


@dataclass
class URLExample:
    input_url: str
    input_app: Optional[str] = None


URLS: list[URLExample] = [
    URLExample(
        input_url="wss://dummy/ep",
        input_app="dummy-0.1.2",
    ),
    URLExample(
        input_url="wss://dummy:1234/ep?client=amz",
        input_app="dummy-0.1.2",
    ),
    URLExample(
        input_url="wss://dummy/ep?sm-app=dummy",
    ),
    URLExample(
        input_url="ws://localhost:8080/ep?sm-app=dummy",
        input_app="dummy-0.1.2",
    ),
    URLExample(
        input_url="http://dummy/ep/v1/",
        input_app="dummy-0.1.2",
    ),
    URLExample(
        input_url="wss://dummy/ep",
    ),
    URLExample(
        input_url="wss://dummy/ep",
        input_app="client/a#b:c^d",
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

    # Parse the input parameters
    input_parsed = urlparse(test.input_url)
    input_params = parse_qs(input_parsed.query, keep_blank_values=True)

    # URL test
    generated_url = client._get_endpoint_url(test.input_url, test.input_app)

    # Parse the URL
    parsed_url = urlparse(generated_url)
    parsed_params = parse_qs(parsed_url.query, keep_blank_values=True)

    # Check the url scheme, netloc and path are preserved
    assert parsed_url.scheme == input_parsed.scheme
    assert parsed_url.netloc == input_parsed.netloc
    assert parsed_url.path == input_parsed.path

    # Validate `sm-app`
    if test.input_app:
        assert parsed_params["sm-app"] == [test.input_app]
    elif "sm-app" in input_params:
        assert parsed_params["sm-app"] == [input_params["sm-app"][0]]
    else:
        assert parsed_params["sm-app"] == [f"voice-sdk/{__version__}"]

    # Validate `sm-voice-sdk`
    assert parsed_params["sm-voice-sdk"] == [__version__]

    # Check other original params are preserved
    for key, value in input_params.items():
        if key not in ["sm-app", "sm-voice-sdk"]:
            assert parsed_params[key] == value
