# Voice Agent Python client for Speechmatics Real-Time API

[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/speechmatics/speechmatics-python-voice/blob/master/LICENSE)

An SDK for working with the Speechmatics Real-Time API optimised for use in voice agents or transcription services.

This uses the Python Real-Time API to process the transcription results from the STT engine and combine them into manageable segments of text. Taking advantage of speaker diarization, the transcription is grouped into individual speakers, with advanced options to focus on and/or ignore specific speakers.

See [OVERVIEW.md](OVERVIEW.md) for more information.

## Installation

```bash
pip install speechmatics-voice
```

## Requirements

You must have a valid Speechmatics API key to use this SDK. You can get one from the [Speechmatics Console](https://console.speechmatics.com).

Store this as `SPEECHMATICS_API_KEY` environment variable in your `.env` file or use `export SPEECHMATICS_API_KEY="your_api_key_here"` in your terminal.

## Quick Start

Below is a basic example of how to use the SDK to transcribe audio from a microphone.

```python
import asyncio
from speechmatics.rt import Microphone
from speechmatics.voice import (
    VoiceAgentClient,
    VoiceAgentConfig,
    EndOfUtteranceMode,
    AgentServerMessageType,
    SpeakerSegment,
)

async def main():
    # Configure the voice agent
    config = VoiceAgentConfig(
        enable_diarization=True,
        end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
    )

    # Initialize microphone
    mic = Microphone(
        sample_rate=16000,
        chunk_size=160,
    )

    if not mic.start():
        print("Microphone not available")
        return

    # Create client and register event handlers
    async with VoiceAgentClient(config=config) as client:

        # Handle interim transcription segments
        @client.on(AgentServerMessageType.ADD_INTERIM_SEGMENTS)
        def handle_interim_segments(message):
            segments: list[SpeakerSegment] = message["segments"]
            for segment in segments:
                print(f"Speaker {segment.speaker_id}: {segment.text}")

        # Handle finalized transcription segments
        @client.on(AgentServerMessageType.ADD_SEGMENTS)
        def handle_final_segments(message):
            segments: list[SpeakerSegment] = message["segments"]
            for segment in segments:
                print(f"Speaker {segment.speaker_id}: {segment.text}")

        # Handle user started speaking event
        @client.on(AgentServerMessageType.SPEAKING_STARTED)
        def handle_speech_started(message):
            print("User started speaking")

        # Handle user stopped speaking event
        @client.on(AgentServerMessageType.SPEAKING_ENDED)
        def handle_speech_ended(message):
            print("User stopped speaking")

        # End of turn / utterance(s)
        @client.on(AgentServerMessageType.END_OF_TURN)
        def handle_end_of_turn(message):
            print("End of turn")

        # Connect and start processing audio
        await client.connect()

        while True:
            frame = await mic.read(160)
            await client.send_audio(frame)

if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

The `examples/` directory contains practical demonstrations of the Voice Agent SDK. See the README in the `examples/voice` directory for more information.

## Documentation

- **SDK Overview**: See [OVERVIEW.md](OVERVIEW.md) for comprehensive API documentation
- **Speechmatics API**: https://docs.speechmatics.com

## License

[MIT](LICENSE)
