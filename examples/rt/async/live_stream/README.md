# Push-style Audio Streaming for Speechmatics Python RT SDK

## Why this feature is useful

Many real-time pipelines (WebRTC, LiveKit, PipeCat, ...) **produce audio in small frames, not as a file**.
Until now the SDK only supported a File-Like object model:

```python
await client.transcribe(file_like_object)
```

`AsyncClient.start_stream()` solves that problem by adding a *push interface*:

- Open the WebSocket once, get a `_LiveAudioStream` handle, then call `await stream.write(bytes_chunk)` whenever you receive audio.
- Built-in back-pressure: `write()` awaits once an internal queue (default 16 chunks) is full, so memory can’t grow unbounded.
- Reuses all existing internals – authentication, event dispatch, error-handling and logging remain exactly the same.

## Quick Start

```python
from speechmatics import AsyncClient

async with AsyncClient() as client:
    stream = await client.start_stream()

    # Write audio chunks to the stream
    audio_chunk = b""
    await stream.write(audio_chunk)

    # Close the stream when done
    await stream.end()
```
