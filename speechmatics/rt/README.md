# Speechmatics Real-Time API Client

Async Python client for the Speechmatics Real-Time API.

## Installation

```bash
pip install speechmatics-rt
```

## Features

- **Async-first design** with synchronous wrappers for compatibility
- **Comprehensive error handling** with detailed error messages
- **Type hints throughout** for excellent IDE support and code safety
- **Environment variable support** for secure credential management
- **Event-driven architecture** for real-time transcript processing
- **Structured logging** with request tracing for debugging
- **Simple connection management** with clear error reporting

## Quick Start

```python
import asyncio
from speechmatics.rt import AsyncClient, ServerMessageType


async def main():
    # Create a client using environment variable SPEECHMATICS_API_KEY
    async with AsyncClient() as client:
        # Register event handlers
        @client.on(ServerMessageType.AddTranscript)
        def handle_final_transcript(msg):
            print(f"Final: {msg['metadata']['transcript']}")

        # Transcribe audio file
        with open("audio.wav", "rb") as audio_file:
            await client.transcribe(audio_file)

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
