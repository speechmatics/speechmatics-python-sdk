# Batch SDK Migration Guide

This guide helps users migrate from the legacy Speechmatics Batch Client (`speechmatics-python`) to the new Speechmatics Batch SDK (`speechmatics-batch`). The new SDK provides a modern async API, improved error handling, and enhanced authentication options with minimal dependencies.

## Significant Changes

- **Fully async API**: All operations now use async/await pattern with `AsyncClient`
- **Enhanced authentication**: Support for both API key and JWT authentication methods
- **Better error handling**: More specific exceptions and clearer error messages
- **Lightweight package**: Minimal dependencies for faster installation and reduced conflicts
- **Improved job management**: Better job status tracking and result handling
- **Streamlined configuration**: Unified `JobConfig` for all job types
- **URL and API key configuration**: Allows loading URL and API key from environment variables

### Breaking Changes

- **Import paths**: `speechmatics.batch_client` → `speechmatics.batch`
- **Client class**: `BatchClient` → `AsyncClient`
- **All methods**: Synchronous → Asynchronous (requires `await`)
- **Configuration**: `BatchTranscriptionConfig` → `JobConfig` with `TranscriptionConfig`
- **Job submission**: Direct config parameter → Structured `JobConfig` object
- **Result format**: `transcription_format` parameter → `format_type` parameter
- **Authentication**: API key parameter naming changed to `api_key`
- **CLI not available**: CLI will be released as a separate package

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
