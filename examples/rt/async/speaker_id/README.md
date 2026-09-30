# Live Real-Time Speaker ID Example

This example demonstrates how to use the Speechmatics Python SDK to perform speaker ID in real-time.

The SDK requires an API key to be set as an environment variable before it can be used. You can obtain an API key by signing up for a Speechmatics account at https://portal.speechmatics.com/dashboard

## Prerequisites

- Install Speechmatics RT SDK: `pip install speechmatics-rt`
- Export Speechmatics API key: `export SPEECHMATICS_API_KEY=YOUR-API-KEY`

## Usage

- Generate speaker IDs: `python generate.py` - this will generate a `speakers.json` file
- Transcribe audio: `python transcribe.py` - this will use the `speakers.json` file to perform speaker ID on a conversation
