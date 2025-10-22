import os

import pytest

from speechmatics.tts import AsyncClient


@pytest.mark.asyncio
async def test_async_http():
    if os.environ.get("SPEECHMATICS_API_KEY") is None:
        pytest.skip("SPEECHMATICS_API_KEY not set")
    async with AsyncClient() as client:
        response = await client.generate(text="Hello world")
        assert response.status == 200
