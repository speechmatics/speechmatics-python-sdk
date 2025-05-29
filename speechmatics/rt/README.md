# Speechmatics Real-Time API Client

A modern, async-first Python client for the Speechmatics Real-Time Speech Recognition API.

## Installation

```bash
pip install speechmatics-rt
```

For development dependencies:
```bash
pip install speechmatics-rt[dev]
```

## Features

- **Async-first design** with synchronous wrappers for compatibility
- **Comprehensive error handling** with detailed error messages
- **Type hints throughout** for excellent IDE support and code safety
- **Environment variable support** for secure credential management
- **Event-driven architecture** for real-time transcript processing
- **Middleware support** for custom message processing and filtering
- **Structured logging** with request tracing for debugging
- **Simple connection management** with clear error reporting

## Quick Start

### Async Usage

```python
import asyncio

from speechmatics.rt import AsyncClient


async def main():
    # Initialize client with API key
    client = AsyncClient(api_key="your-api-key")

    # Register event handlers
    @client.on(ServerMessageType.AddTranscript)
    def handle_final_transcript(msg):
        print(f"Final: {msg['metadata']['transcript']}")

    @client.on(ServerMessageType.AddPartialTranscript)
    def handle_partial_transcript(msg):
        print(f"Partial: {msg['metadata']['transcript']}")

    # Transcribe audio file
    with open("audio.wav", "rb") as audio_file:
        await client.transcribe(audio_file)

    await client.close()

# Run the async function
asyncio.run(main())
```

## Configuration

### Environment Variables

Set these environment variables to avoid passing credentials in code:

```bash
export SPEECHMATICS_API_KEY="your-api-key"
export SPEECHMATICS_RT_URL="wss://eu2.rt.speechmatics.com/v2"  # Default
```
