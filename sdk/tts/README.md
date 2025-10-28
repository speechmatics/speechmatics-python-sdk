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
import pydub

async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    async with AsyncClient() as client:
        # Simple transcription
        response = await client.generate(text="Hello, this is the Speechmatics TTS API. We are excited to have you here!")
        assert response.status == "success"
        assert response.audio is not None
        pydub.AudioSegment.from_file(response.audio).export("output.wav", format="wav")
asyncio.run(main())


```


### Basic Job Workflow

```python
import asyncio
from speechmatics.tts import AsyncClient, JobConfig, JobType, TranscriptionConfig

async def main():
    # Create client with explicit API key
    async with AsyncClient(api_key="your-api-key") as client:

        # Submit job
        response = await client.generate(text="Hello, this is the Speechmatics TTS API. We are excited to have you here!")
        assert response.status == "success"
        assert response.audio is not None

        # Wait for completion
        response = await client.wait_for_completion(
            response.job_id,
            polling_interval=2.0,
            timeout=300.0
        )

        # Access results
        pydub.AudioSegment.from_file(response.audio).export("output.wav", format="wav")

asyncio.run(main())
```

### Manual Job Management

```python
import asyncio
from speechmatics.tts import AsyncClient, JobStatus

async def main():
    async with AsyncClient() as client:

        # Submit job
        response = await client.generate(text="Hello, this is the Speechmatics TTS API. We are excited to have you here!")

        # Check job status
        job_details = await client.get_job_info(response.job_id)
        print(f"Status: {job_details.status}")

        # Wait for completion manually
        while job_details.status == JobStatus.RUNNING:
            await asyncio.sleep(5)
            job_details = await client.get_job_info(response.job_id)

        if job_details.status == JobStatus.DONE:
            # Get audio
            pydub.AudioSegment.from_file(response.audio).export("output.wav", format="wav")
        else:
            print(f"Job failed with status: {job_details.status}")

asyncio.run(main())
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
            result = await client.transcribe("audio.wav", timeout=120.0)
            print(result.transcript_text)

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
        url="https://asr.api.speechmatics.com/v2",
        api_key="your-api-key",
        connect_timeout=30.0,
        operation_timeout=600.0
    )

    async with AsyncClient(conn_config=config) as client:
        response = await client.generate("audio.wav")
    assert response.status == "success"
    assert response.audio is not None
    pydub.AudioSegment.from_file(response.audio).export("output.wav", format="wav")

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
