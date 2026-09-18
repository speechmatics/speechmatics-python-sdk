# Speechmatics Batch API Client

[![PyPI](https://img.shields.io/pypi/v/speechmatics-batch)](https://pypi.org/project/speechmatics-batch/)
![PythonSupport](https://img.shields.io/badge/Python-3.9%2B-green)

Python client for Speechmatics Batch API, with both async and blocking interfaces.

## Features

- Async (`AsyncClient`) and blocking (`Client`) API clients with comprehensive error handling
- Synchronous transcription support: get a transcript in a single request, without polling
- Type hints throughout for better IDE support
- Environment variable support for credentials
- Easy-to-use interface for submitting, monitoring, and retrieving transcription jobs
- Full job configuration support with all Speechmatics features
- Intelligent transcript formatting with speaker diarization
- Support for multiple output formats (JSON, TXT, SRT)

## Installation

```bash
pip install speechmatics-batch
```

## Usage

### Quick Start

```python
import asyncio
from speechmatics.batch import AsyncClient

async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    async with AsyncClient() as client:
        # Simple transcription
        result = await client.transcribe("audio.wav")
        print(result.transcript_text)

asyncio.run(main())
```

### Without asyncio

`Client` is the blocking equivalent of `AsyncClient`. It exposes the same
methods and returns the same models, so it suits scripts, notebooks, serverless
handlers and synchronous web frameworks. It is genuinely synchronous under the
hood — no event loop is ever created — even though both clients ship together:

```python
from speechmatics.batch import Client

with Client() as client:
    result = client.transcribe("audio.wav")
    print(result.transcript_text)
```

### Synchronous Transcription

By default a transcription job is submitted, polled until it finishes, and then
its transcript is fetched. For short audio you can instead ask the server to
hold the request open until the transcript is ready, so one call replaces the
whole cycle. Pass `wait` (in seconds) to do this:

```python
from speechmatics.batch import Client, FormatType

with Client() as client:
    # One request: submit, transcribe and return the transcript
    text = client.transcribe("audio.wav", wait=60, format_type=FormatType.TXT)
    print(text)
```

If the job is still running when the wait elapses, `transcribe()` falls back to
polling automatically, so longer audio keeps working unchanged.

`wait` is also available on the individual operations, for full control:

```python
from speechmatics.batch import Client, JobStatus, TranscriptNotReadyError

with Client() as client:
    job = client.submit_job("audio.wav", wait=60)

    if job.status == JobStatus.DONE:
        print(job.transcript.transcript_text)  # already available, no extra call
    else:
        # status is JobStatus.CREATED: the wait elapsed, the job is still running
        print(client.wait_for_completion(job.id).transcript_text)
```

Requesting a transcript before it exists raises `TranscriptNotReadyError` (a
subclass of `JobError`), which is the signal to retry:

```python
try:
    transcript = client.get_transcript(job.id, wait=30)
except TranscriptNotReadyError:
    transcript = client.wait_for_completion(job.id)
```

Notes:

- Synchronous transcription is available on Speechmatics SaaS only; on-premises
  deployments do not support it.
- The server caps how long it will wait, and intermediate proxies may close
  long-held connections, so treat the fallback path as the normal case for
  longer audio.
- The API applies a small default wait (currently 2 seconds) to the `GET`
  endpoints when `wait` is omitted. Pass `wait=0` to return immediately.
- `wait` is clamped to any `timeout` you pass, so the timeout is always honoured.
- Job submission is not idempotent. If a submission fails after the server
  accepted it, resubmitting creates a second billable job — use `list_jobs()`
  to recover the original job instead of retrying blindly.

Everything above works identically on `AsyncClient` with `await`:

```python
async with AsyncClient() as client:
    text = await client.transcribe("audio.wav", wait=60, format_type=FormatType.TXT)
```

## JWT Authentication

For enhanced security, use temporary JWT tokens instead of static API keys.
JWTs are short-lived (60 seconds default) and automatically refreshed:

```python
from speechmatics.batch import AsyncClient, JWTAuth

auth = JWTAuth("your-api-key", ttl=60)

async with AsyncClient(auth=auth) as client:
    # Tokens are cached and auto-refreshed automatically
    result = await client.transcribe("audio.wav")
    print(result.transcript_text)
```

Ideal for long-running applications or when minimizing API key exposure.
See the [authentication documentation](https://docs.speechmatics.com/introduction/authentication) for more details.

### Basic Job Workflow

```python
import asyncio
from speechmatics.batch import AsyncClient, JobConfig, JobType, TranscriptionConfig

async def main():
    # Create client with explicit API key
    async with AsyncClient(api_key="your-api-key") as client:

        # Configure transcription
        config = JobConfig(
            type=JobType.TRANSCRIPTION,
            transcription_config=TranscriptionConfig(
                language="en",
                enable_entities=True,
                diarization="speaker"
            )
        )

        # Submit job
        job = await client.submit_job("audio.wav", config=config)
        print(f"Job submitted: {job.id}")

        # Wait for completion
        result = await client.wait_for_completion(
            job.id,
            polling_interval=2.0,
            timeout=300.0
        )

        # Access results
        print(f"Transcript: {result.transcript_text}")
        print(f"Confidence: {result.confidence}")

asyncio.run(main())
```

### Advanced Configuration

```python
import asyncio
from speechmatics.batch import (
    AsyncClient,
    JobConfig,
    JobType,
    Model,
    TranscriptionConfig,
    TranslationConfig,
    SummarizationConfig
)

async def main():
    async with AsyncClient(api_key="your-api-key") as client:

        # Advanced job configuration
        config = JobConfig(
            type=JobType.TRANSCRIPTION,
            transcription_config=TranscriptionConfig(
                language="en",
                model=Model.ENHANCED,
                enable_entities=True,
                diarization="speaker",
            ),
            translation_config=TranslationConfig(target_languages=["es", "fr"]),
            summarization_config=SummarizationConfig(
                content_type="conversational", summary_length="brief"
            ),
        )

        result = await client.transcribe("audio.wav", config=config)

        # Access advanced features
        if result.summary:
            print(f"Summary: {result.summary}")
        if result.translations:
            print(f"Translations: {result.translations}")

asyncio.run(main())
```

### Manual Job Management

```python
import asyncio
from speechmatics.batch import AsyncClient, JobStatus

async def main():
    async with AsyncClient() as client:

        # Submit job
        job = await client.submit_job("audio.wav")

        # Check job status
        job_details = await client.get_job_info(job.id)
        print(f"Status: {job_details.status}")

        # Wait for completion manually
        while job_details.status == JobStatus.RUNNING:
            await asyncio.sleep(5)
            job_details = await client.get_job_info(job.id)

        if job_details.status == JobStatus.DONE:
            # Get transcript
            transcript = await client.get_transcript(job.id)
            print(transcript.transcript_text)
        else:
            print(f"Job failed with status: {job_details.status}")

asyncio.run(main())
```

### Different Output Formats

```python
import asyncio
from speechmatics.batch import AsyncClient, FormatType

async def main():
    async with AsyncClient() as client:
        job = await client.submit_job("audio.wav")

        # Get JSON format (default)
        json_result = await client.get_transcript(job.id, format_type=FormatType.JSON)
        print(json_result.transcript_text)

        # Get plain text
        txt_result = await client.get_transcript(job.id, format_type=FormatType.TXT)
        print(txt_result)

        # Get SRT subtitles
        srt_result = await client.get_transcript(job.id, format_type=FormatType.SRT)
        print(srt_result)

asyncio.run(main())
```

### Error Handling

```python
import asyncio
from speechmatics.batch import (
    AsyncClient,
    BatchError,
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
    except BatchError as e:
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
from speechmatics.batch import AsyncClient, ConnectionConfig

async def main():
    # Custom connection settings
    config = ConnectionConfig(
        url="https://asr.api.speechmatics.com/v2",
        api_key="your-api-key",
        connect_timeout=30.0,
        operation_timeout=600.0
    )

    async with AsyncClient(conn_config=config) as client:
        result = await client.transcribe("audio.wav")
        print(result.transcript_text)

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
- `SPEECHMATICS_BATCH_URL`: Custom API endpoint URL (optional)
