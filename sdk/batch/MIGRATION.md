# Batch SDK Migration Guide

This guide helps users migrate from the legacy Speechmatics Batch Client (`speechmatics-python`) to the new Speechmatics Batch SDK (`speechmatics-batch`). The new SDK provides a modern async API, improved error handling, and enhanced authentication options with minimal dependencies.

## Significant Changes

- **Async and sync APIs**: `AsyncClient` for async/await code, `Client` for blocking code
- **Enhanced authentication**: Support for both API key and JWT authentication methods
- **Better error handling**: More specific exceptions and clearer error messages
- **Lightweight package**: Minimal dependencies for faster installation and reduced conflicts
- **Improved job management**: Better job status tracking and result handling
- **Streamlined configuration**: Unified `JobConfig` for all job types
- **URL and API key configuration**: Allows loading URL and API key from environment variables

### Breaking Changes

- **Import paths**: `speechmatics.batch_client` → `speechmatics.batch`
- **Client class**: `BatchClient` → `AsyncClient`, or `Client` to stay synchronous
- **All methods**: Asynchronous on `AsyncClient` (requires `await`); `Client` keeps them blocking
- **Configuration**: `BatchTranscriptionConfig` → `JobConfig` with `TranscriptionConfig`
- **Job submission**: Direct config parameter → Structured `JobConfig` object
- **Result format**: `transcription_format` parameter → `format_type` parameter
- **Authentication**: API key parameter naming changed to `api_key`
- **CLI not available**: CLI will be released as a separate package

### Changes within `speechmatics-batch`

- **Type hints now reach type checkers.** `speechmatics` is a PEP 420 namespace package, so the
  `py.typed` marker is found where mypy and pyright look for it. Previously an installed
  `speechmatics-batch` was reported as untyped (`missing library stubs or py.typed marker`) and
  every call inferred as `Any`. Type checking your code against this SDK may now surface real
  errors that were silently ignored before.

- **Invalid credentials now raise `AuthenticationError`**: HTTP 401/403 responses were
  previously re-wrapped as `TransportError` before reaching callers, despite the documented
  behaviour. Code that catches `TransportError` for authentication failures must catch
  `AuthenticationError` instead.
- **Unavailable transcripts now raise `TranscriptNotReadyError`**: `get_transcript()` answers
  an HTTP 404 with this exception, which subclasses `JobError`, so existing `except JobError`
  handlers keep working.
- **`AuthBase` methods are no longer abstract**: a custom auth class implements
  `get_auth_headers` (async), `get_auth_headers_sync` (blocking), or both. Previously a
  blocking-only implementation could not be instantiated because the async method was
  abstract. Calling a method a subclass does not implement raises `NotImplementedError`
  naming the missing one.
- **`delete_job()` accepts `force`**: the API refuses to delete a running job with HTTP 423, so
  deleting one previously was not possible. Pass `force=True` to delete it anyway; without it,
  the resulting `JobError` now says so explicitly.
- **New dependency: `httpx`**, alongside the existing `aiohttp`/`aiofiles`. It powers the new
  blocking `Client`; `AsyncClient` does not use it.

## Installation

``` bash
pip install speechmatics-batch
```

## Usage

Before

```python
from speechmatics.models import ConnectionSettings, BatchTranscriptionConfig
from speechmatics.batch_client import BatchClient

with BatchClient("API-KEY") as client:
    job_id = client.submit_job(PATH_TO_FILE, BatchTranscriptionConfig(LANGUAGE))

    transcript = client.wait_for_completion(job_id, transcription_format='txt')

    print(transcript)
```

After

```python
from speechmatics.batch import AsyncClient, FormatType, JobConfig, JobType, TranscriptionConfig

async with AsyncClient(os.environ.get("SPEECHMATICS_API_KEY")) as client:
    config = JobConfig(
        type=JobType.TRANSCRIPTION,
        transcription_config=TranscriptionConfig(language="en"),
    )

    job = await client.submit_job("audio.wav", config=config)

    result = await client.wait_for_completion(job.id, format_type=FormatType.TXT)

    print(f"Transcript: {result.transcript_text}")
```
