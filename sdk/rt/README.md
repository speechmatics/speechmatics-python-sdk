# Speechmatics Real-Time API Client

Async Python client for the Speechmatics Real-Time API.

## Features

- **Async-first design** with simpler interface
- **Multi-channel transcription** - Simultaneous processing of multiple audio sources
- **Single-stream transcription** - Optimized client for single audio source
- **Comprehensive error handling** with detailed error messages
- **Type hints throughout** for excellent IDE support and code safety
- **Environment variable support** for secure credential management
- **Event-driven architecture** for real-time transcript processing
- **Simple connection management** with clear error reporting

## Installation

```bash
pip install speechmatics-rt

```
## Quick Start

```python
import asyncio
from speechmatics.rt import AsyncClient, ServerMessageType


async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    async with AsyncClient() as client:
        # Register event handlers
        @client.on(ServerMessageType.ADD_TRANSCRIPT)
        def handle_final_transcript(msg):
            print(f"Final: {msg['metadata']['transcript']}")

        # Transcribe audio file
        with open("audio.wav", "rb") as audio_file:
            await client.transcribe(audio_file)

# Run the async function
asyncio.run(main())
```

### Multi-Channel Transcription

```python
import asyncio
from speechmatics.rt import AsyncMultiChannelClient, ServerMessageType, TranscriptionConfig

async def main():
    # Prepare multiple audio sources
    sources = {
        "left": open("left.wav", "rb"),
        "right": open("right.wav", "rb"),
    }

    try:
        async with AsyncMultiChannelClient() as client:
            # Handle transcripts with channel identification
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_transcript(msg):
                channel = msg["results"][0]["channel"]
                transcript = msg["metadata"]["transcript"]
                print(f"[{channel}]: {transcript}")

            # Start multi-channel transcription
            await client.transcribe(
                sources,
                transcription_config=TranscriptionConfig(
                    language="en",
                    diarization="channel",
                    channel_diarization_labels=list(sources.keys()),
                )
            )
    finally:
        # Ensure all files are closed
        for source in sources.values():
            source.close()

asyncio.run(main())
```

## JWT Authentication

For enhanced security, use temporary JWT tokens instead of static API keys.
JWTs are short-lived (60 seconds by default).

```python
from speechmatics.rt import AsyncClient, JWTAuth

# Create JWT auth (requires: pip install 'speechmatics-rt[jwt]')
auth = JWTAuth("your-api-key", ttl=60)

async with AsyncClient(auth=auth) as client:
    pass
```

Ideal for browser applications or when minimizing API key exposure.
See the [authentication documentation](https://docs.speechmatics.com/introduction/authentication) for more details.

## Logging

The client supports logging with job id tracing for debugging.
To increase logging verbosity, set `DEBUG` level in your example code:

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

### Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key
- `SPEECHMATICS_RT_URL`: Custom API endpoint URL (optional)
