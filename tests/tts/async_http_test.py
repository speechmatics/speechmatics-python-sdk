import os

import pytest

from speechmatics.tts import AsyncClient


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("SPEECHMATICS_API_KEY") is None, reason="Skipping test if API key is not set")   
async def test_async_http():
    async with AsyncClient() as client:
        response = await client.generate(text="Hello world")
    assert response.status == 200
