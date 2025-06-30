# Speechmatics Flow API Client

Async Python client for the Speechmatics Flow API - Real-time conversational AI.

## Features

- **Async-first design** with simpler interface
- **Comprehensive error handling** with detailed error messages
- **Event-driven architecture** for real-time conversation processing
- **Binary audio streaming** support for assistant responses
- **Tool function calling** support for LLM function invocation
- **Debug mode** for LLM debugging and troubleshooting
- **Direct LLM input** for sending text input to conversations

## Installation

```bash
pip install speechmatics-flow
```

## JWT Authentication

For enhanced security, use temporary JWT tokens instead of static API keys.
JWTs are short-lived (60 seconds by default).

```python
from speechmatics.flow import AsyncClient, JWTAuth

# Create JWT auth (requires: pip install 'speechmatics-flow[jwt]')
auth = JWTAuth("your-api-key", ttl=60)

async with AsyncClient(auth=auth) as client:
    pass
```

Ideal for browser applications or when minimizing API key exposure.
See the [authentication documentation](https://docs.speechmatics.com/introduction/authentication) for more details.


## Environment Variables

The client supports the following environment variables:

- `SPEECHMATICS_API_KEY`: Your Speechmatics API key
- `SPEECHMATICS_FLOW_URL`: Custom API endpoint URL (optional)

## Logging

The client supports logging with conversation id tracing for debugging.
To increase logging verbosity, set `DEBUG` level in your code:

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
