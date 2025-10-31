import os

import pytest

from speechmatics.tts import AsyncClient


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("SPEECHMATICS_API_KEY") is None, reason="Skipping test if API key is not set")   
async def test_async_http():
    async with AsyncClient() as client:
        async with await client.generate(text="Hello world") as response:
            start_length = response.content.total_raw_bytes
            assert response.status == 200
            async for chunk in response.content.iter_chunked(1024):
                assert chunk
            end_length = response.content.total_raw_bytes
            # Assert that bytes are streamed async from the socket rather than awaited
            assert start_length <= end_length
