# Speechmatics Real-Time API Client

Async Python client for the Speechmatics Real-Time API.

## Features

- **Async-first design** with synchronous wrappers for compatibility
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

### Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key
- `SPEECHMATICS_RT_URL`: Custom API endpoint URL (optional)
