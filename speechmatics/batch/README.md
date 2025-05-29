# Speechmatics Batch API Client

A Python client for Speechmatics Batch Automatic Speech Recognition (ASR) API.

## Installation

```bash
pip install speechmatics-batch
```

## Features

- Async and sync API clients
- Comprehensive error handling and input validation
- Type hints throughout for better IDE support
- Environment variable support for credentials
- Easy-to-use interface for submitting, monitoring, and retrieving transcription jobs

## Usage

```python
from batch.client import BatchClient

# Create a client
client = BatchClient(api_key="your-api-key")

# Submit a transcription job
job_id = client.submit_job(
    audio_file="path/to/audio.wav",
    language="en",
)

# Wait for job to complete
client.wait_for_completion(job_id)

# Get the results
results = client.get_results(job_id)
print(results.transcript)
```

For more detailed examples, see the examples directory in the repository.

## License

MIT
