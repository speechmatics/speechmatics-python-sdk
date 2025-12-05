# Speechmatics Voice SDK

[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/speechmatics/speechmatics-python-sdk/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/speechmatics-voice)](https://pypi.org/project/speechmatics-voice/)
[![PythonSupport](https://img.shields.io/badge/Python-3.9%2B-green)](https://www.python.org/)

Python SDK for building voice-enabled applications using Speechmatics Real-Time API. Optimized for specific use cases: conversational AI, voice agents, transcription services, and real-time captioning.

## Table of Contents
- [What is the Voice SDK?](#what-is-the-voice-sdk)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Event Messages](#event-messages)
- [Common Usage Patterns](#common-usage-patterns)
- [Environment Variables](#environment-variables)
- [Examples](#examples)
- [SDK Class Reference](#sdk-class-reference)
- [Requirements](#requirements)
- [Documentation](#documentation)
- [License](#license)


## What is the Voice SDK?

The Voice SDK is a higher-level abstraction built on top of the Speechmatics Real-Time API (`speechmatics-rt`). While the Real-Time API provides raw transcription events (words and utterances), the Voice SDK adds:

- **Intelligent Segmentation** - Groups words into meaningful speech segments per speaker
- **Turn Detection** - Automatically detects when speakers finish their turns using adaptive or ML-based methods
- **Speaker Management** - Focus on or ignore specific speakers in multi-speaker scenarios
- **Preset Configurations** - Ready-to-use configs for common use cases (conversation, note-taking, captions)
- **Simplified Event Handling** - Receive clean, structured segments instead of raw word-level events

### When to Use Voice SDK vs Real-Time API

**Use Voice SDK when:**

- You are building conversational AI or voice agents
- You need automatic turn detection
- You want speaker-focused transcription
- You need ready-to-use presets for common scenarios

**Use Real-Time API when:**

- You only need raw, word-level events
- You are building custom segmentation / aggregation logic
- You want fine-grained control over every event

## Installation

```bash
# Standard installation
pip install speechmatics-voice

# With VAD and SMART_TURN (ML-based turn detection)
pip install speechmatics-voice[smart]
```

> **Note:** Some features require additional ML dependencies (ONNX runtime, transformers). If not installed, these features will be unavailable and a warning will be shown.

<details>

<summary><strong>👉 Using Docker? Click to see how to install the required models.</strong></summary>

### Use within Docker

If you are using a Docker container with the Voice SDK installed and you require the smart features (`SMART_TURN`), then you can use the following in your `Dockerfile` to make sure the ML models are included and not downloaded at runtime.

```python
"""
Download the Voice SDK required models during the build process.
"""

from speechmatics.voice import SileroVAD, SmartTurnDetector


def load_models():
    SileroVAD.download_model()
    SmartTurnDetector.download_model()


if __name__ == "__main__":
    load_models()
```

Then, in your `Dockerfile`, include the following:

```
COPY ./models.py models.py
RUN uv run models.py
```
This copies the script and runs it as part of the build.

</details>

## Quick Start

### Basic Example

A simple example that shows complete sentences as they have been finalized, with different speakers shown with different IDs.

```python
import asyncio
import os
from speechmatics.rt import Microphone
from speechmatics.voice import VoiceAgentClient, AgentServerMessageType

async def main():
    """Stream microphone audio to Speechmatics Voice Agent using 'scribe' preset"""

    # Audio configuration
    SAMPLE_RATE = 16000         # Hz
    CHUNK_SIZE = 160            # Samples per read
    PRESET = "scribe"           # Configuration preset

    # Create client with preset
    client = VoiceAgentClient(
        api_key=os.getenv("SPEECHMATICS_API_KEY"),
        preset=PRESET
    )

    # Print finalised segments of speech with speaker ID
    @client.on(AgentServerMessageType.ADD_SEGMENT)
    def on_segment(message):
        for segment in message["segments"]:
            speaker = segment["speaker_id"]
            text = segment["text"]
            print(f"{speaker}: {text}")

    # Setup microphone
    mic = Microphone(SAMPLE_RATE, CHUNK_SIZE)
    if not mic.start():
        print("Error: Microphone not available")
        return

    # Connect to the Voice Agent
    await client.connect()

    # Stream microphone audio (interruptable using keyboard)
    try:
        while True:
            audio_chunk = await mic.read(CHUNK_SIZE)
            if not audio_chunk:
                break # Microphone stopped producing data
            await client.send_audio(audio_chunk)
    except KeyboardInterrupt:
        pass
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Configuring a Voice Agent Client
When creating a VoiceAgentClient, there are several ways to configure it:

1. **Presets** - optimised configurations for common use cases. These require no further configuration to be set.
```python
# Low latency preset - for fast responses (may split speech in to smaller segments)
client = VoiceAgentClient(api_key=api_key, preset="fast")

# Conversation preset - for natural dialogue
client = VoiceAgentClient(api_key=api_key, preset="adaptive")

# Advanced conversation with ML turn detection
client = VoiceAgentClient(api_key=api_key, preset="smart_turn")

# External end of turn preset - endpointing handled by the client
client = VoiceAgentClient(api_key=api_key, preset="external")

# Scribe preset - for note-taking
client = VoiceAgentClient(api_key=api_key, preset="scribe")

# Captions preset - for live captioning
client = VoiceAgentClient(api_key=api_key, preset="captions")

# To view all available presets, use:
presets = VoiceAgentConfigPreset.list_presets()
```


2. **Custom Configuration** - for more control, you can also specify custom configuration in a `VoiceAgentConfig` object.

```python
from speechmatics.voice import VoiceAgentClient, VoiceAgentConfig, EndOfUtteranceMode

# Define your custom configuration
config = VoiceAgentConfig(
    language="en",
    enable_diarization=True,
    max_delay=0.7,
    end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
)

client = VoiceAgentClient(api_key=api_key, config=config)
```

3. **Custom Configuration with Overlays** - you can use presets as a starting point, and then customize with overlays.

```python
from speechmatics.voice import VoiceAgentConfigPreset, VoiceAgentConfig

# Use preset with custom overrides
config = VoiceAgentConfigPreset.SCRIBE(
    VoiceAgentConfig(
        language="es",
        max_delay=0.8
    )
)
```

> **Note:** If no config or preset is provided, the client will default to the `external` preset.

### Configuration Serialization
It can also be useful to export and import configuration as JSON:

```python
from speechmatics.voice import VoiceAgentConfigPreset, VoiceAgentConfig

# Export preset to JSON
config_json = VoiceAgentConfigPreset.SCRIBE().to_json()

# Load from JSON
config = VoiceAgentConfig.from_json(config_json)

# Or create from JSON string
config = VoiceAgentConfig.from_json('{"language": "en", "enable_diarization": true}')
```

## Configuration

### Basic Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | str | `"en"` | Language code for transcription (e.g., `"en"`, `"es"`, `"fr"`). <br>See [supported languages](https://docs.speechmatics.com/speech-to-text/languages). |
| `operating_point` | OperatingPoint | `ENHANCED` | Balance accuracy vs latency. Options: `STANDARD` or `ENHANCED`. |
| `domain` | str | `None` | Domain-specific model (e.g., `"finance"`, `"medical"`). <br> See [supported languages and domains](https://docs.speechmatics.com/speech-to-text/languages). |
| `output_locale` | str | `None` | Output locale for formatting (e.g., `"en-GB"`, `"en-US"`). <br> See [supported languages and locales](https://docs.speechmatics.com/speech-to-text/languages). |
| `max_delay` | float | `0.7` | Maximum transcription delay for word emission. |

### Turn Detection Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `end_of_utterance_mode` | EndOfUtteranceMode | `FIXED` | Controls how turn endings are detected. Options: <br>- `FIXED` - Uses fixed silence threshold. Fast but may split slow speech.<br>- `ADAPTIVE` - Adjusts delay based on speech rate, pauses, and disfluencies. Best for natural conversation.<br>- `EXTERNAL` - Manual control via `client.finalize()`. For custom turn logic. |
| `end_of_utterance_silence_trigger` | float | `0.2` | Silence duration in seconds to trigger turn end (also used for the basis of adaptive delay). |

### Speaker Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_diarization` | bool | `False` | Enable speaker diarization to identify and label different speakers. |
| `speaker_sensitivity` | float | `0.5` | Diarization sensitivity between 0.0 and 1.0. Higher values detect more speakers. |
| `max_speakers` | int | `None` | Limit maximum number of speakers to detect. |
| `prefer_current_speaker` | bool | `False` | Give extra weight to current speaker for word grouping. |
| `speaker_config` | SpeakerFocusConfig | `SpeakerFocusConfig()` | Configure speaker focus/ignore rules. |
| `known_speakers` | list[SpeakerIdentifier] | `[]` | Pre-enrolled speaker identifiers for speaker identification. |

#### Usage Examples
Using `speaker_config`, you can focus on only specific speakers but keep words from others, or ignore specific speakers.

```python
from speechmatics.voice import SpeakerFocusConfig, SpeakerFocusMode

# Focus only on specific speakers, but keep words from other speakers
config = VoiceAgentConfig(
    enable_diarization=True,
    speaker_config=SpeakerFocusConfig(
        focus_speakers=["S1", "S2"],
        focus_mode=SpeakerFocusMode.RETAIN
    )
)

# Ignore specific speakers
config = VoiceAgentConfig(
    enable_diarization=True,
    speaker_config=SpeakerFocusConfig(
        ignore_speakers=["S3"]
    )
)
```

Using `known_speakers`, you can use pre-enrolled speaker identifiers to identify specific speakers.

```python
from speechmatics.voice import SpeakerIdentifier

# Use known speakers from previous session
config = VoiceAgentConfig(
    enable_diarization=True,
    known_speakers=[
        SpeakerIdentifier(label="Alice", speaker_identifiers=["XX...XX"]),
        SpeakerIdentifier(label="Bob", speaker_identifiers=["YY...YY"])
    ]
)
```

### Language & Vocabulary

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `additional_vocab` | list[AdditionalVocabEntry] | `[]` | Custom vocabulary for domain-specific terms. |
| `punctuation_overrides` | dict | `None` | Custom punctuation rules. |

#### Usage Examples

Using `additional_vocab`, you can specify a dictionary of domain-specific terms.

```python
from speechmatics.voice import AdditionalVocabEntry

config = VoiceAgentConfig(
    language="en",
    additional_vocab=[
        AdditionalVocabEntry(
            content="Speechmatics",
            sounds_like=["speech matters", "speech matics"]
        ),
        AdditionalVocabEntry(content="API"),
    ]
)
```

### Audio Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_rate` | int | `16000` | Audio sample rate in Hz. |
| `audio_encoding` | AudioEncoding | `PCM_S16LE` | Audio encoding format. |

### Advanced Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `transcription_update_preset` | TranscriptionUpdatePreset | `COMPLETE` | Controls when to emit updates: `COMPLETE`, `COMPLETE_PLUS_TIMING`, `WORDS`, `WORDS_PLUS_TIMING`, or `TIMING`. |
| `speech_segment_config` | SpeechSegmentConfig | `SpeechSegmentConfig()` | Fine-tune segment generation and post-processing. |
| `smart_turn_config` | SmartTurnConfig | `None` | Configure SMART_TURN behavior (buffer length, threshold). |
| `include_results` | bool | `False` | Include word-level timing data in segments. |
| `include_partials` | bool | `True` | Include interim (lower confidence) words in emitted segments. Set to `False` for final-only output. |

## Event Messages

The Voice SDK emits real-time, structured events as a session progresses via `AgentServerMessageType`.

These events fall into three main categories:
1. **Core Events** - high-level session and transcription updates.
2. **Speaker Events** - detected speech activity.
3. **Additional** - detailed, low-level events.

To handle events, register a callback using `@client.on()` decorator or `client.on()` method.

> **Note:** The payloads shown below are the actual message payloads from the Voice SDK. When using the CLI example with `--output-file`, messages also include a `ts` timestamp field (e.g., `"ts": "2025-11-11 23:18:35.909"`), which is added by the CLI for logging purposes and is not part of the SDK payload.

### High Level Overview

#### Core Events

| Event                   | Description                               | Notes / Purpose                                              |
| ----------------------- | ----------------------------------------- | ------------------------------------------------------------ |
| `RECOGNITION_STARTED`   | Fired when a transcription session starts | Contains session ID, language pack info                      |
| `ADD_PARTIAL_SEGMENT` | Emitted continuously during speech        | Provides interim, real-time transcription text               |
| `ADD_SEGMENT`         | Fired when a segment is finalized         | Provides stable, final transcription text                    |
| `END_OF_TURN`         | Fired when a speaker’s turn ends          | Depends on `end_of_utterance_mode`; useful for turn tracking |

#### Speaker Events
| Event           | When it fires        | Purpose                         |
| --------------- | -------------------- | ------------------------------- |
| `SPEAKER_STARTED` | Voice detected       | Marks start of speech           |
| `SPEAKER_ENDED`   | Silence detected     | Marks end of speech             |
| `SPEAKERS_RESULT` | Enrollment completes | Provides speaker IDs and labels |

#### Additional Events
| Event                  | When it fires                 | Purpose                                     |
| ---------------------- | ----------------------------- | ------------------------------------------- |
| `START_OF_TURN`          | New turn begins               | Optional, low-level event for turn tracking |
| `END_OF_TURN_PREDICTION` | Predicts turn completion      | Fires before END_OF_TURN in adaptive mode   |
| `END_OF_UTTERANCE`       | Silence threshold reached     | Low-level STT engine trigger                |
| `ADD_PARTIAL_TRANSCRIPT` | Word-level partial transcript | Legacy; use ADD_PARTIAL_SEGMENT instead     |
| `ADD_TRANSCRIPT`         | Word-level final transcript   | Legacy; use ADD_SEGMENT instead             |


### Core Events - Examples and Payloads

#### RECOGNITION_STARTED

```python
@client.on(AgentServerMessageType.RECOGNITION_STARTED)
def on_started(message):
    session_id = message["id"]
    language = message["language_pack_info"]["language_description"]
    print(f"Session {session_id} started - Language: {language}")
```

**Payload:**

```json
{
  "message": "RecognitionStarted",
  "id": "a8779b0b-a238-43de-8211-c70f5fcbe191",
  "orchestrator_version": "2025.08.29127+289170c022.HEAD",
  "language_pack_info": {
    "language_description": "English",
    "word_delimiter": " ",
    "writing_direction": "left-to-right",
    "itn": true,
    "adapted": false
  }
}
```

#### ADD_PARTIAL_SEGMENT

```python
@client.on(AgentServerMessageType.ADD_PARTIAL_SEGMENT)
def on_partial(message):
    for segment in message["segments"]:
        print(f"[INTERIM] {segment['speaker_id']}: {segment['text']}")
```

**Payload:**

```json
{
  "message": "AddPartialSegment",
  "segments": [
    {
      "speaker_id": "S1",
      "is_active": true,
      "timestamp": "2025-11-11T23:18:37.189+00:00",
      "language": "en",
      "text": "Welcome to",
      "metadata": {
        "start_time": 1.28,
        "end_time": 1.6
      }
    }
  ],
  "metadata": {
    "start_time": 1.28,
    "end_time": 1.6,
    "processing_time": 0.307
  }
}
```

**Fields:**

- `speaker_id` - Speaker label (e.g., `"S1"`, `"S2"`)
- `is_active` - `true` if speaker is in focus (based on `speaker_config`)
- `text` - Current partial transcription text
- `metadata.start_time` - Segment start time (seconds since session start)
- `metadata.end_time` - Segment end time (seconds since session start)

Top-level `metadata` contains the same timing plus `processing_time`.

#### ADD_SEGMENT

```python
@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    for segment in message["segments"]:
        speaker = segment["speaker_id"]
        text = segment["text"]
        start = message["metadata"]["start_time"]
        print(f"[{start:.2f}s] {speaker}: {text}")
```

**Payload:**

```json
{
  "message": "AddSegment",
  "segments": [
    {
      "speaker_id": "S1",
      "is_active": true,
      "timestamp": "2025-11-11T23:18:37.189+00:00",
      "language": "en",
      "text": "Welcome to Speechmatics.",
      "metadata": {
        "start_time": 1.28,
        "end_time": 8.04
      }
    }
  ],
  "metadata": {
    "start_time": 1.28,
    "end_time": 8.04,
    "processing_time": 0.187
  }
}
```

#### END_OF_TURN

```python
@client.on(AgentServerMessageType.END_OF_TURN)
def on_turn_end(message):
    duration = message["metadata"]["end_time"] - message["metadata"]["start_time"]
    print(f"Turn ended (duration: {duration:.2f}s)")
```

**Payload:**

```json
{
  "message": "EndOfTurn",
  "turn_id": 0,
  "metadata": {
    "start_time": 1.28,
    "end_time": 8.04
  }
}
```

### Speaker Events - Examples and Payloads

#### SPEAKER_STARTED

```python
@client.on(AgentServerMessageType.SPEAKER_STARTED)
def on_speaker_start(message):
    speaker = message["speaker_id"]
    time = message["time"]
    print(f"{speaker} started speaking at {time}s")
```

**Payload:**

```json
{
  "message": "SpeakerStarted",
  "is_active": true,
  "speaker_id": "S1",
  "time": 1.28
}
```

#### SPEAKER_ENDED

```python
@client.on(AgentServerMessageType.SPEAKER_ENDED)
def on_speaker_end(message):
    speaker = message["speaker_id"]
    time = message["time"]
    print(f"{speaker} stopped speaking at {time}s")
```

**Payload:**

```json
{
  "message": "SpeakerEnded",
  "is_active": false,
  "speaker_id": "S1",
  "time": 2.64
}
```

#### SPEAKERS_RESULT

```python
# Listen for the result
@client.on(AgentServerMessageType.SPEAKERS_RESULT)
def on_speakers(message):
    for speaker in message["speakers"]:
        print(f"Speaker {speaker['label']}: {speaker['speaker_identifiers']}")

# Request speaker IDs at end of session
await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS, "final": True})

# Request speaker IDs now
await client.send_message({"message": AgentClientMessageType.GET_SPEAKERS})
```

## Common Usage Patterns

### Simple Transcription

```python
client = VoiceAgentClient(api_key=api_key, preset="scribe")

@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    for segment in message["segments"]:
        print(f"{segment['speaker_id']}: {segment['text']}")
```

### Conversational AI with Turn Detection

```python
config = VoiceAgentConfig(
    language="en",
    enable_diarization=True,
    end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
)

client = VoiceAgentClient(api_key=api_key, config=config)

@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    user_text = message["segments"][0]["text"]
    # Process user input

@client.on(AgentServerMessageType.END_OF_TURN)
def on_turn_end(message):
    # User finished speaking - generate AI response
    pass
```

### Live Captions with Timestamps

```python
client = VoiceAgentClient(api_key=api_key, preset="captions")

@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    start_time = message["metadata"]["start_time"]
    for segment in message["segments"]:
        print(f"[{start_time:.1f}s] {segment['text']}")
```

### Speaker Identification

```python
from speechmatics.voice import SpeakerIdentifier

# Use known speakers from previous session
known_speakers = [
    SpeakerIdentifier(label="Alice", speaker_identifiers=["XX...XX"]),
    SpeakerIdentifier(label="Bob", speaker_identifiers=["YY...YY"])
]

config = VoiceAgentConfig(
    enable_diarization=True,
    known_speakers=known_speakers
)

client = VoiceAgentClient(api_key=api_key, config=config)

@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    for segment in message["segments"]:
        # Will show "Alice" or "Bob" instead of "S1", "S2"
        print(f"{segment['speaker_id']}: {segment['text']}")
```

### Manual Turn Control

```python
config = VoiceAgentConfig(
    end_of_utterance_mode=EndOfUtteranceMode.EXTERNAL
)

client = VoiceAgentClient(api_key=api_key, config=config)

# Manually trigger turn end
await client.finalize(end_of_turn=True)
```

### Focus on Specific Speaker

```python
from speechmatics.voice import SpeakerFocusConfig, SpeakerFocusMode

config = VoiceAgentConfig(
    enable_diarization=True,
    speaker_config=SpeakerFocusConfig(
        focus_speakers=["S1"],  # Only emit S1's speech
        focus_mode=SpeakerFocusMode.RETAIN
    )
)

client = VoiceAgentClient(api_key=api_key, config=config)

@client.on(AgentServerMessageType.ADD_SEGMENT)
def on_segment(message):
    # Only S1's segments will appear here
    for segment in message["segments"]:
        if segment["is_active"]:
            print(f"{segment['text']}")

# Dynamically change focused speaker during session
await client.update_diarization_config(
    SpeakerFocusConfig(
        focus_speakers=["S2"],  # Switch focus to S2
        focus_mode=SpeakerFocusMode.RETAIN
    )
)
```

## Environment Variables

- `SPEECHMATICS_API_KEY` - Your Speechmatics API key (required)
- `SPEECHMATICS_RT_URL` - Custom WebSocket endpoint (optional)
- `SMART_TURN_MODEL_PATH` - Path for SMART_TURN ONNX model cache (optional)
- `SMART_TURN_HF_URL` - Override SMART_TURN model download URL (optional)

## Examples

See the `examples/voice/` directory for complete working examples:

- **`simple/`** - Basic microphone transcription
- **`scribe/`** - Note-taking with custom vocabulary
- **`cli/`** - Full-featured CLI with all options

## SDK Class Reference

### VoiceAgentClient

```python
class VoiceAgentClient:
    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        app: Optional[str] = None,
        config: Optional[VoiceAgentConfig] = None,
        preset: Optional[str] = None
    ):
        """Create Voice Agent client.

        Args:
            auth: Authentication instance (optional)
            api_key: Speechmatics API key (defaults to SPEECHMATICS_API_KEY env var)
            url: Custom WebSocket URL (defaults to SPEECHMATICS_RT_URL env var)
            app: Optional application name for endpoint URL
            config: Voice Agent configuration (optional)
            preset: Preset name ("scribe", "fast", etc.) (optional)
        """

    async def connect(self) -> None:
        """Connect to Speechmatics service.

        Establishes WebSocket connection and starts transcription session.
        Must be called before sending audio.
        """

    async def disconnect(self) -> None:
        """Disconnect from service.

        Closes WebSocket connection and cleans up resources.
        """

    async def send_audio(self, payload: bytes) -> None:
        """Send audio data for transcription.

        Args:
            payload: Audio data as bytes
        """

    def update_diarization_config(self, config: SpeakerFocusConfig) -> None:
        """Update diarization configuration during session.

        Args:
            config: New speaker focus configuration
        """

    def finalize(self, end_of_turn: bool = False) -> None:
        """Finalize segments and optionally trigger end of turn.

        Args:
            end_of_turn: Whether to emit end of turn message (default: False)
        """

    async def send_message(self, message: dict) -> None:
        """Send control message to service.

        Args:
            message: Control message dictionary
        """

    def on(self, event: AgentServerMessageType, callback: Callable) -> None:
        """Register event handler.

        Args:
            event: Event type to listen for
            callback: Function to call when event occurs
        """

    def once(self, event: AgentServerMessageType, callback: Callable) -> None:
        """Register one-time event handler.

        Args:
            event: Event type to listen for
            callback: Function to call once when event occurs
        """

    def off(self, event: AgentServerMessageType, callback: Callable) -> None:
        """Unregister event handler.

        Args:
            event: Event type
            callback: Function to remove
        """
```

## Requirements

- Python 3.9+
- Speechmatics API key (Get one through: [Speechmatics Portal](https://portal.speechmatics.com/))

## Documentation

- [Speechmatics Documentation Homepage](https://docs.speechmatics.com/)
- [Real-Time Quickstart](https://docs.speechmatics.com/speech-to-text/realtime/quickstart)
- [Getting Started with Authentication](https://docs.speechmatics.com/get-started/authentication)

## License

[MIT](LICENSE)
