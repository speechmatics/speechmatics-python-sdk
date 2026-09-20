# Batch SDK Migration Guide

This guide helps you migrate from the legacy Speechmatics Batch Client
(`speechmatics-python`, class `BatchClient`) to the new Speechmatics Batch SDK
(`speechmatics-batch`).

**Coming from blocking code?** Use `Client` — it is a drop-in-shaped
replacement for `BatchClient`: no `asyncio` required, same synchronous
mental model. `AsyncClient` exposes identical methods with `async`/`await`,
for code that already runs an event loop, but adopting it is optional.

## Quick reference

| Legacy (`BatchClient`) | New (`Client` / `AsyncClient`) | Notes |
| --- | --- | --- |
| `BatchClient(auth_token)` | `Client(api_key=...)` / `AsyncClient(api_key=...)` | Also reads `SPEECHMATICS_API_KEY` — see [Credentials](#credentials) |
| `client.connect()` / `with BatchClient(...)` | `Client(...)` used directly, or `with Client(...)` | `connect()` no longer exists or is needed |
| `client.submit_job(audio, transcription_config)` → `str` (job ID) | `client.submit_job(audio, config=...)` → `JobDetails` | Return type changed — use `job.id` |
| `client.submit_jobs(paths, config, concurrency=5)` | No direct equivalent | See [Bulk submission](#bulk-submission) |
| `client.check_job_status(job_id)` → raw `dict` | `client.get_job_info(job_id)` → `JobDetails` | |
| `client.get_job_result(job_id, transcription_format="json-v2")` | `client.get_transcript(job_id, format_type=FormatType.JSON)` → raises `TranscriptNotReadyError` if the job isn't done yet | Catch `TranscriptNotReadyError` to retry — see [Exceptions](#exceptions) |
| `client.wait_for_completion(job_id, transcription_format="txt")` | `client.wait_for_completion(job_id, format_type=FormatType.TXT)` | **Default format changed** — see [Breaking Changes](#breaking-changes) |
| `client.delete_job(job_id, force=False)` → `str` | `client.delete_job(job_id, force=False)` → `None`, raises on failure | |
| `client.list_jobs()` → `List[dict]` | `client.list_jobs()` → `List[JobDetails]` | |

## Installation

``` bash
pip install speechmatics-batch
```

## Credentials

Legacy `BatchClient` took an explicit `auth_token`, or fell back to
`~/.speechmatics/config` (a file written by the legacy CLI's
`speechmatics config set`). The new SDK does not read that file — pass
`api_key` explicitly, or set an environment variable. If you configured the
legacy CLI, your token is already on disk:

```bash
cat ~/.speechmatics/config   # find the auth_token you already have

export SPEECHMATICS_API_KEY="<paste the auth_token value here>"
```

```python
from speechmatics.batch import Client

with Client() as client:  # reads SPEECHMATICS_API_KEY
    ...
```

A custom `ConnectionSettings.url` is replaced by the `SPEECHMATICS_BATCH_URL`
environment variable, or `Client(url=...)` / `ConnectionConfig(url=...)`.

## Usage

### Submit and wait (blocking — the direct replacement)

Before:

```python
from speechmatics.models import ConnectionSettings, BatchTranscriptionConfig
from speechmatics.batch_client import BatchClient

with BatchClient("API-KEY") as client:
    job_id = client.submit_job(PATH_TO_FILE, BatchTranscriptionConfig(LANGUAGE))

    transcript = client.wait_for_completion(job_id, transcription_format='txt')

    print(transcript)
```

After:

```python
from speechmatics.batch import Client, FormatType, JobConfig, JobType, TranscriptionConfig

with Client(api_key="API-KEY") as client:
    config = JobConfig(
        type=JobType.TRANSCRIPTION,
        transcription_config=TranscriptionConfig(language=LANGUAGE),
    )

    job = client.submit_job(PATH_TO_FILE, config=config)

    transcript = client.wait_for_completion(job.id, format_type=FormatType.TXT)

    print(transcript)
```

### Submit and wait (async, if you're adopting `asyncio`)

```python
from speechmatics.batch import AsyncClient, FormatType, JobConfig, JobType, TranscriptionConfig

async with AsyncClient(api_key="API-KEY") as client:
    config = JobConfig(
        type=JobType.TRANSCRIPTION,
        transcription_config=TranscriptionConfig(language=LANGUAGE),
    )

    job = await client.submit_job(PATH_TO_FILE, config=config)

    transcript = await client.wait_for_completion(job.id, format_type=FormatType.TXT)

    print(transcript)
```

### Bulk submission

`submit_jobs()` has no direct equivalent. Reproduce a concurrency-limited
batch with `asyncio.gather` and a semaphore — see the
[README's Bulk and Concurrent Transcription section](README.md#bulk-and-concurrent-transcription)
for a full example (both async and blocking) that submits each file, waits
for it, and returns its transcript. It defaults to a concurrency of 5,
matching `submit_jobs()`'s old default.

### Manual job management

Before:

```python
status = client.check_job_status(job_id)["job"]["status"]
if status == "done":
    result = client.get_job_result(job_id, transcription_format="json-v2")
```

After:

```python
from speechmatics.batch import JobStatus

job_info = client.get_job_info(job_id)
if job_info.status == JobStatus.DONE:
    result = client.get_transcript(job_id)
```

## Breaking Changes

- **Import paths**: `speechmatics.batch_client` → `speechmatics.batch`
- **Client class**: `BatchClient` → `AsyncClient`, or `Client` to stay synchronous
- **All methods async on `AsyncClient`** (requires `await`); `Client` keeps them blocking
- **Configuration**: `BatchTranscriptionConfig` → `JobConfig` with `TranscriptionConfig`
- **`submit_job()` return type changed**: it returned a job ID `str`; it now
  returns a `JobDetails` object — use `job.id` instead of the return value
  directly.
- **`wait_for_completion()` default format changed**: the legacy default was
  `transcription_format="txt"`; the new default is `format_type=FormatType.JSON`.
  **If your code relied on the default rather than passing the format
  explicitly, you will silently start getting JSON instead of plain text.**
- **Result format**: `transcription_format` string parameter → `format_type`,
  a `FormatType` enum
- **Authentication**: API key parameter renamed to `api_key`; credentials are
  no longer read from `~/.speechmatics/config` — see [Credentials](#credentials)
- **`get_transcript()` raises `TranscriptNotReadyError` when a job isn't
  finished yet** — catch this specifically to retry, rather than treating it
  the same as a missing job (`JobError`).
- **`submit_jobs()` (bulk submission) removed**: no direct equivalent — see
  [Bulk submission](#bulk-submission).
- **No CLI**: there is no command-line tool for `speechmatics-batch`, and
  none is planned. Use the SDK directly from a script for one-off jobs.

## Exceptions

| Legacy exception (`speechmatics.exceptions`) | Raised by | New exception (`speechmatics.batch`) |
| --- | --- | --- |
| `JobNotFoundException` | `check_job_status()`, `delete_job()` (job not found) | `JobError` |
| `JobNotFoundException` | `get_job_result()` (job not ready, or not found) | `TranscriptNotReadyError` (from `get_transcript()`) |
| `TranscriptionError` (invalid format string) | `get_job_result()` | N/A — `format_type` takes a `FormatType` enum member, not a string |
| `TranscriptionError` (job in an unexpected state) | `wait_for_completion()` | `JobError` |
| `httpx.HTTPStatusError` (401/403) | any request | `AuthenticationError` |
| *(no equivalent — surfaces as a generic `httpx.HTTPStatusError`)* | job data expired (HTTP 410) | `JobExpiredError` |

## Changes within `speechmatics-batch`

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
- **Expired jobs now raise `JobExpiredError`**: Speechmatics retains job data for a limited
  time; once it expires, both `get_job_info()` and `get_transcript()` answer with HTTP 410,
  which now raises this exception (a subclass of `JobError`) instead of a generic `JobError`
  with the raw response embedded in the message.
- **`JobStatus.EXPIRED` removed**: the API signals expiry via HTTP 410 on the endpoints above,
  never as a `status` field value, so this member never matched anything a real API response
  could produce and has been removed.
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

## Polling behaviour

Legacy `wait_for_completion()` slept for 10% of the audio's duration before
polling at all, then polled at a fixed 15-second interval regardless of file
length. The new SDK polls at a fixed interval too — `polling_interval`
(default 5 seconds), with up to 20% jitter applied so concurrent clients
don't synchronise — but does not scale it to the audio's duration. Pass
`polling_interval` to `wait_for_completion()`/`transcribe()` if 5 seconds
doesn't fit your workload.
