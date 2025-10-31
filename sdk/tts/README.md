# Speechmatics TTS API Client

[![PyPI](https://img.shields.io/pypi/v/speechmatics-tts)](https://pypi.org/project/speechmatics-tts/)
![PythonSupport](https://img.shields.io/badge/Python-3.9%2B-green)

Async Python client for Speechmatics TTS API.

## Features

- Async API client with comprehensive error handling
- Type hints throughout for better IDE support
- Environment variable support for credentials

## Installation

```bash
pip install speechmatics-tts
```

## Usage

### Quick Start

```python
import asyncio
from speechmatics.tts import AsyncClient


async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
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

```

### Error Handling

```python
import asyncio
from speechmatics.tts import (
    AsyncClient,
    ttsError,
    AuthenticationError,
    JobError,
    TimeoutError
)

async def main():
    try:
        async with AsyncClient() as client:
            response = await client.generate(text="Hello, this is the Speechmatics TTS API. We are excited to have you here!")

    except AuthenticationError:
        print("Invalid API key")
    except ttsError as e:
        print(f"Job submission failed: {e}")
    except JobError as e:
        print(f"Job processing failed: {e}")
    except TimeoutError as e:
        print(f"Job timed out: {e}")
    except FileNotFoundError:
        print("Audio file not found")

asyncio.run(main())
```

### Connection Configuration

```python
import asyncio
from speechmatics.tts import AsyncClient, ConnectionConfig

async def main():
    # Custom connection settings
    config = ConnectionConfig(
        url="https://preview.tts.speechmatics.com",
        api_key="your-api-key",
        connect_timeout=30.0,
        operation_timeout=600.0
    )

    async with AsyncClient(conn_config=config) as client:
        response = await client.generate(text="Hello World")
   

asyncio.run(main())
```

## Logging

The client supports logging with job id tracing for debugging. To increase logging verbosity, set `DEBUG` level in your example code:

```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
```

## Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key
- `SPEECHMATICS_TTS_URL`: Custom API endpoint URL (optional)
