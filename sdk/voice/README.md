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
    AgentServerMessageType
)

async def main():
    # Configure the voice agent
    config = VoiceAgentConfig(
        enable_diarization=True,
        end_of_utterance_mode=EndOfUtteranceMode.FIXED,
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
        @client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT)
        def handle_interim_segments(message):
            segments = message["segments"]
            for segment in segments:
                print(f"[PARTIAL] Speaker {segment['speaker_id']}: {segment['text']}")

        # Handle finalized transcription segments
        @client.on(AgentServerMessageType.ADD_SEGMENT)
        def handle_final_segments(message):
            segments = message["segments"]
            for segment in segments:
                print(f"[FINAL] Speaker {segment['speaker_id']}: {segment['text']}")

        # Handle user started speaking event
        @client.on(AgentServerMessageType.SPEAKER_STARTED)
        def handle_speech_started(message):
            status = message["status"]
            print(f"User started speaking: {status}")

        # Handle user stopped speaking event
        @client.on(AgentServerMessageType.SPEAKER_ENDED)
        def handle_speech_ended(message):
            status = message["status"]
            print(f"User stopped speaking: {status}")

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

## Client Configuration

The `VoiceAgentClient` can be configured with a number of options to control the behavior of the client.

## Messages

The async client will return messages of type `AgentServerMessageType`. To register for a message, use the `on` method. Optionally, you can use the `once` method to register a callback that will be called once and then removed. Use the `off` method to remove a callback.

### `RECOGNITION_STARTED`

Emitted when the recognition has started and contains the session ID and base time for when transcription started. It also contains the language pack information for the model being used.

```json
{
  "message": "RecognitionStarted",
  "orchestrator_version": "2025.08.29127+289170c022.HEAD",
  "id": "a8779b0b-a238-43de-8211-c70f5fcbe191",
  "language_pack_info": {
    "adapted": false,
    "itn": true,
    "language_description": "English",
    "word_delimiter": " ",
    "writing_direction": "left-to-right"
  }
}
```

### `SPEAKER_STARTED`

Emitted when a speaker starts speaking. Contains the speaker ID and the VAD status. If there are multiple speakers, this will be emitted each time a speaker starts speaking. There will only be one active speaker at any given time.

```json
{
  "message": "SpeakerStarted",
  "status": {
    "is_active": true,
    "speaker_id": "S1"
  }
}
```

### `SPEAKER_ENDED`

Emitted when a speaker stops speaking. Contains the speaker ID (if diarization is enabled) and the VAD status. If there are multiple speakers, this will be emitted each time a speaker stops speaking.

```json
{
  "message": "SpeakerEnded",
  "status": {
    "is_active": false,
    "speaker_id": "S1"
  }
}
```

### `ADD_PARTIAL_SEGMENT`

Emitted when a partial segment has been detected. Contains the speaker ID, if diarization is enabled. If there are multiple speakers, this will be emitted each time a speaker starts speaking. Words from different speakers will be grouped into segments.

If diarization is enabled and the client has been configured to focus on a specific speaker, the `is_active` will indicate whether the contents are from focused speakers. Ignored speakers will not have their words emitted.

The `metadata` contains the start and end time for the segment. Each time the segment is updated as new partials are received, whole segment will be emitted again with updated `metadata`. The `annotation` field contains additional information about the contents of the segment.

```json
{
  "message": "AddPartialSegment",
  "segments": [
    {
      "speaker_id": "S1",
      "is_active": true,
      "timestamp": "2025-09-15T19:47:29.096+00:00",
      "language": "en",
      "text": "Welcome",
      "annotation": ["has_partial"]
    }
  ],
  "metadata": { "start_time": 0.36, "end_time": 0.92 }
}
```

### `ADD_SEGMENT`

Emitted when a final segment has been detected. Contains the speaker ID, if diarization is enabled. If there are multiple speakers, this will be emitted each time a speaker stops speaking.

The `metadata` contains the start and end time for the segment. The `annotation` field contains additional information about the contents of the segment.

```json
{
  "message": "AddSegment",
  "segments": [
    {
      "speaker_id": "S1",
      "is_active": true,
      "timestamp": "2025-09-15T19:47:29.096+00:00",
      "language": "en",
      "text": "Welcome to Speechmatics.",
      "annotation": [
        "has_final",
        "starts_with_final",
        "ends_with_final",
        "ends_with_eos",
        "ends_with_punctuation"
      ]
    }
  ],
  "metadata": { "start_time": 0.36, "end_time": 1.32 }
}
```

### `END_OF_TURN`

Emitted when a turn has ended. This is a signal that the user has finished speaking and the system has finished processing the turn.

The message is emitted differently for the different `EndOfUtterance` modes:

- `FIXED` -> emitted when the fixed delay has elapsed with the STT engine
- `ADAPTIVE` -> emitted when the adaptive delay has elapsed with the client
- `EXTERNAL` -> emitted when an external trigger forces the end of turn

The `ADAPTIVE` mode takes into consideration a number of factors to determine whether the most recent speaker as completed their turn. These include:

- The speed of speech
- Whether they have been using disfluencies (e.g. "um", "er", "ah")
- If the words spoken are considered to be a complete sentence

The `end_of_utterance_silence_trigger` is used to calculate the baseline `FIXED` and `ADAPTIVE` delays. As a fallback, the `end_of_utterance_max_delay` is used to trigger the end of turn after a fixed amount of time, regardless of the content of what the most recent speaker has said.

When using `EXTERNAL` mode, call `client.finalize()` to force the end of turn.

## Documentation

- **SDK Overview**: See [OVERVIEW.md](OVERVIEW.md) for comprehensive API documentation
- **Speechmatics API**: https://docs.speechmatics.com

## License

[MIT](LICENSE)
