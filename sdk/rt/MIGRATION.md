# Real-Time SDK Migration Guide

This guide helps users migrate from the legacy Speechmatics Real-Time Client (`speechmatics-python`) to the new Speechmatics Real-Time SDK (`speechmatics-rt`). The new SDK provides a cleaner API, better error handling, and improved performance with minimal dependencies.

## Significant Changes

- **Restructured Async Client API**: New async context manager pattern with `AsyncClient`
- **Improved event handler interface**: Simplified event registration with `.on()` method
- **Better error handling**: More specific exceptions and clearer error messages
- **Lightweight package**: Minimal dependencies for faster installation and reduced conflicts
- **Enhanced authentication**: Dedicated `JWTAuth` class for JWT token management
- **Streamlined configuration**: Separate `ConnectionConfig` for WebSocket settings
- **URL and API key configuration**: Allows loading URL and API key from environment variables

### Breaking Changes

- **Import paths**: `speechmatics.client` → `speechmatics.rt`
- **Client class**: `WebsocketClient` → `AsyncClient`
- **Method names**: `.run()` → `.transcribe()` for transcription operations
- **Event registration**: `.add_event_callback()` → `.on()`
- **Event types**: `ServerMessageType.AddTranscript` → `ServerMessageType.ADD_TRANSCRIPT`
- **Authentication**: API key passed directly to client or through environment variable instead of `ConnectionConfig`
- **JWT setup**: Separate `JWTAuth` class instead of `ConnectionConfig.generate_temp_token` parameter
- **Configuration**: `ConnectionConfig` now only handles WebSocket connection settings
- **CLI not available**: CLI will be released as a separate package

## Installation

``` bash
pip install speechmatics-rt
```

## Basic Usage

Before

```python
from speechmatics.client import WebsocketClient
from speechmatics.models import TranscriptionConfig

client = WebsocketClient("API-KEY")

conf = TranscriptionConfig(language="en")

await client.run(audio_stream, conf)
```

After

```python
from speechmatics.rt import AsyncClient, TranscriptionConfig

async with AsyncClient("API-KEY") as client:

    conf = TranscriptionConfig(language="en")

    await client.transcribe(audio_stream, transcription_config=conf)
```

## Event Callbacks Usage

Before

```python
from speechmatics.client import WebsocketClient
from speechmatics.models import ServerMessageType, TranscriptionConfig

client = WebsocketClient("API-KEY")

def on_transcript(msg: dict):
    print(msg)

client.add_event_callback(ServerMessageType.AddTranscript, on_transcript)

conf = TranscriptionConfig(language="en")

await client.run(audio_stream, conf)
```

After

```python
from speechmatics.rt import AsyncClient, TranscriptionConfig, ServerMessageType

def on_transcript(msg: dict):
    print(msg)

async with AsyncClient("API-KEY") as client:
    client.on(ServerMessageType.ADD_TRANSCRIPT, on_transcript)

    conf = TranscriptionConfig(language="en")

    await client.transcribe(audio_stream, transcription_config=conf)
```

## JWT Usage

Before

```python
from speechmatics.client import WebsocketClient
from speechmatics.models import TranscriptionConfig, ConnectionConfig

conn_config = ConnectionConfig(auth_token="API-KEY", generate_temp_token=True)

client = WebsocketClient(conn_config)

conf = TranscriptionConfig(language="en")

await client.run(audio_stream, conf)
```

After

### ConnectionConfig is now exclusively used for websocket connection configuration.

```python
from speechmatics.rt import AsyncClient, ConnectionConfig, TranscriptionConfig, JWTAuth

conn_config = ConnectionConfig(ping_timeout=60)

auth = JWTAuth("API-KEY")

async with AsyncClient(auth=auth, conn_config=conn_config) as client:

    conf = TranscriptionConfig(language="en")

    await client.transcribe(audio_stream, transcription_config=conf)
```
