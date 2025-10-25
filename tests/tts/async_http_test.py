import pytest
from speechmatics.tts import AsyncClient

@pytest.mark.asyncio
async def test_async_http():
    async with AsyncClient() as client:
        response = await client.generate(text="Hello world")
        assert response.status == 200
        