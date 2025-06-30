# Flow SDK Migration Guide

This guide helps users migrate from the legacy Speechmatics Flow Client (`speechmatics-flow`) to the new Speechmatics Flow SDK (`speechmatics-flow`). The new SDK provides a cleaner API, better error handling, and improved performance.

## Significant Changes

- **Restructured Async Client API**: New async context manager pattern with `AsyncClient`
- **Improved event handler interface**: Simplified event registration with `.on()` method
- **Better error handling**: More specific exceptions and clearer error messages
- **Lightweight package**: Minimal dependencies for faster installation and reduced conflicts
- **Enhanced authentication**: Dedicated `JWTAuth` class for JWT token management
- **Streamlined configuration**: Separate `ConnectionConfig` for WebSocket settings
- **URL and API key configuration**: Allows loading URL and API key from environment variables

### Breaking Changes

- **Import paths**: `speechmatics_flow.client` → `speechmatics.flow`
- **Client class**: `WebsocketClient` → `AsyncClient`
- **Method names**: `.run()` → `.start_conversation()` for conversation operations
- **Event registration**: `.add_event_handler()` → `.on()`
- **Connection configuration**: `ConnectionSettings` → `ConnectionConfig` (for WebSocket settings only)
- **Authentication**: API key passed directly to client or through environment variable instead of `ConnectionSettings`
- **Audio input**: Removed `Interaction` object → direct audio stream objects
- **Configuration structure**: Separate `AudioFormat` and `ConversationConfig` classes
- **CLI not available**: CLI will be released as a separate package

## Installation

```bash
pip install speechmatics-flow
```

## Basic Usage

**Before**

```python
from speechmatics_flow.client import WebsocketClient
from speechmatics_flow.models import (
    ConnectionSettings,
    Interaction,
    AudioSettings,
    ConversationConfig,
)

client = WebsocketClient(
    ConnectionSettings(
        url="wss://flow.api.speechmatics.com/v1/flow",
        auth_token="API-KEY",
    )
)

await client.run(
    interactions=[Interaction(audio_stream)],
    audio_settings=AudioSettings(),
    conversation_config=ConversationConfig(),
)
```

**After**

```python
from speechmatics.flow import AsyncClient, AudioFormat, ConversationConfig

async with AsyncClient("API-KEY") as client:
    audio_format = AudioFormat()
    conversation_config = ConversationConfig()

    await client.start_conversation(
        audio_stream,
        audio_format=audio_format,
        conversation_config=conversation_config,
    )
```

## Event Callbacks Usage

**Before**

```python
from speechmatics_flow.client import WebsocketClient
from speechmatics_flow.models import (
    ConnectionSettings,
    ServerMessageType,
    ConversationConfig,
)

client = WebsocketClient(
    ConnectionSettings(
        url="wss://flow.api.speechmatics.com/v1/flow",
        auth_token="API-KEY",
    )
)

def on_transcript(msg: dict):
    transcript = msg.get("metadata", {}).get("transcript", "")
    print(f"Transcript: {transcript}")

def binary_msg_handler(msg: bytes):
    # Handle binary audio data
    audio_buffer.write(msg)

client.add_event_handler(ServerMessageType.AddTranscript, on_transcript)
client.add_event_handler(ServerMessageType.AddAudio, binary_msg_handler)

await client.run(
    interactions=[Interaction(audio_stream)],
    audio_settings=AudioSettings(),
    conversation_config=ConversationConfig(),
)
```

**After**

```python
from speechmatics.flow import (
    AsyncClient,
    AudioFormat,
    ConversationConfig,
    ServerMessageType,
)

def on_transcript(msg: dict):
    transcript = msg.get("metadata", {}).get("transcript", "")
    print(f"Transcript: {transcript}")

def on_audio(audio_data: bytes):
    # Handle binary audio data
    audio_buffer.write(audio_data)

async with AsyncClient("API-KEY") as client:
    client.on(ServerMessageType.ADD_TRANSCRIPT, on_transcript)
    client.on(ServerMessageType.ADD_AUDIO, on_audio)

    await client.start_conversation(
        audio_stream,
        audio_format=AudioFormat(),
        conversation_config=ConversationConfig(),
    )
```

## JWT Authentication

**Before**

```python
from speechmatics_flow.client import WebsocketClient
from speechmatics_flow.models import ConnectionSettings

# JWT generation was handled manually or through external libraries
client = WebsocketClient(
    ConnectionSettings(
        url="wss://flow.api.speechmatics.com/v1/flow",
        auth_token="API-KEY",
        generate_temp_token=True,
    )
)
```

**After**

```python
from speechmatics.flow import AsyncClient, JWTAuth, ConnectionConfig

# Built-in JWT authentication
auth = JWTAuth("API-KEY", ttl=60)
conn_config = ConnectionConfig(ping_timeout=60)

async with AsyncClient(auth=auth, conn_config=conn_config) as client:
    await client.start_conversation(audio_stream)
```

## Environment Variables

The new SDK supports environment variables for configuration:

```python
# Set environment variables
export SPEECHMATICS_API_KEY=your-api-key
export SPEECHMATICS_FLOW_URL=wss://flow.api.speechmatics.com/v1/flow

# Use without explicit configuration
from speechmatics.flow import AsyncClient

async with AsyncClient() as client:
    await client.start_conversation(audio_stream)
```

### Getting Help

If you encounter issues during migration:

1. Check the [Flow SDK documentation](https://docs.speechmatics.com/sdk/flow-python-sdk)
2. Review the [examples directory](https://github.com/speechmatics/speechmatics-python-sdk/tree/main/examples/flow)
3. Contact support at support@speechmatics.com
