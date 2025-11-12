# Speechmatics Voice SDK

[![PyPI](https://img.shields.io/pypi/v/speechmatics-voice)](https://pypi.org/project/speechmatics-voice/)
![PythonSupport](https://img.shields.io/badge/Python-3.9%2B-green)

Python SDK for building voice-enabled applications with the Speechmatics Real-Time API. Optimized for conversational AI, voice agents, transcription services, and real-time captioning.

## What is the Voice SDK?

The Voice SDK is a higher-level abstraction built on top of the Speechmatics Real-Time API (`speechmatics-rt`). While the Real-Time SDK provides raw transcription events (words and utterances), the Voice SDK adds:

- **Intelligent Segmentation** - Groups words into meaningful speech segments per speaker
- **Turn Detection** - Automatically detects when speakers finish their turns using adaptive or ML-based methods
- **Speaker Management** - Focus on or ignore specific speakers in multi-speaker scenarios
- **Preset Configurations** - Ready-to-use configs for common use cases (conversation, note-taking, captions)
- **Simplified Event Handling** - Receive clean, structured segments instead of raw word-level events

### When to Use Voice SDK vs Real-Time SDK

**Use Voice SDK when:**

- Building conversational AI or voice agents
- You need automatic turn detection
- You want speaker-focused transcription
- You need ready-to-use presets for common scenarios

**Use Real-Time SDK when:**

- You need raw word-level events
- Building custom segmentation logic
- You want fine-grained control over every event
- Processing batch files or custom workflows

## Installation

```bash
# Standard installation
pip install speechmatics-voice

# With SMART_TURN (ML-based turn detection)
pip install speechmatics-voice[smart]
```

> **Note:** `SMART_TURN` requires additional ML dependencies (ONNX runtime, transformers). If not installed, it automatically falls back to `ADAPTIVE` mode.

## Quick Start

### Basic Example

```python
import asyncio
import os
from speechmatics.rt import Microphone
from speechmatics.voice import VoiceAgentClient, AgentServerMessageType

async def main():
    # Create client with preset
    client = VoiceAgentClient(
        api_key=os.getenv("SPEECHMATICS_API_KEY"),
        preset="scribe"
    )

    # Handle final segments
    @client.on(AgentServerMessageType.ADD_SEGMENT)
    def on_segment(message):
        for segment in message["segments"]:
            speaker = segment["speaker_id"]
            text = segment["text"]
            print(f"{speaker}: {text}")

    # Setup microphone
    mic = Microphone(sample_rate=16000, chunk_size=320)
    if not mic.start():
        print("Error: Microphone not available")
        return

    # Connect and stream
    await client.connect()

    try:
        while True:
            audio_chunk = await mic.read(320)
            await client.send_audio(audio_chunk)
    except KeyboardInterrupt:
        pass
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using Presets

Presets provide optimized configurations for common use cases:

```python
# Scribe preset - for note-taking
client = VoiceAgentClient(api_key=api_key, preset="scribe")

# Low latency preset - for fast responses
client = VoiceAgentClient(api_key=api_key, preset="low_latency")

# Conversation preset - for natural dialogue
client = VoiceAgentClient(api_key=api_key, preset="conversation_adaptive")

# Advanced conversation with ML turn detection
client = VoiceAgentClient(api_key=api_key, preset="conversation_smart_turn")

# Captions preset - for live captioning
client = VoiceAgentClient(api_key=api_key, preset="captions")
```

### Custom Configuration

```python
from speechmatics.voice import VoiceAgentClient, VoiceAgentConfig, EndOfUtteranceMode

config = VoiceAgentConfig(
    language="en",
    enable_diarization=True,
    max_delay=0.7,
    end_of_utterance_mode=EndOfUtteranceMode.ADAPTIVE,
)

client = VoiceAgentClient(api_key=api_key, config=config)
```

## Configuration

### Basic Parameters

**`language`** (str, default: `"en"`)
Language code for transcription (e.g., `"en"`, `"es"`, `"fr"`). See [supported languages](https://docs.speechmatics.com/speech-to-text/languages).

**`operating_point`** (OperatingPoint, default: `ENHANCED`)
Balance accuracy vs latency. Options: `STANDARD` or `ENHANCED`.

**`domain`** (str, default: `None`)
Domain-specific model (e.g., `"finance"`, `"medical"`). See [supported languages and domains](https://docs.speechmatics.com/speech-to-text/languages).

**`output_locale`** (str, default: `None`)
Output locale for formatting (e.g., `"en-GB"`, `"en-US"`). See [supported languages and locales](https://docs.speechmatics.com/speech-to-text/languages).

**`enable_diarization`** (bool, default: `False`)
Enable speaker diarization to identify and label different speakers.

### Turn Detection Parameters

**`end_of_utterance_mode`** (EndOfUtteranceMode, default: `FIXED`)
Controls how turn endings are detected:

- **`FIXED`** - Uses fixed silence threshold. Fast but may split slow speech.
- **`ADAPTIVE`** - Adjusts delay based on speech rate, pauses, and disfluencies. Best for natural conversation.
- **`SMART_TURN`** - Uses ML model to detect acoustic turn-taking cues. Requires `[smart]` extras.
- **`EXTERNAL`** - Manual control via `client.finalize()`. For custom turn logic.

**`end_of_utterance_silence_trigger`** (float, default: `0.2`)
Silence duration in seconds to trigger turn end.

**`end_of_utterance_max_delay`** (float, default: `10.0`)
Maximum delay before forcing turn end.

**`max_delay`** (float, default: `0.7`)
Maximum transcription delay for word emission.

### Speaker Configuration

**`speaker_sensitivity`** (float, default: `0.5`)
Diarization sensitivity between 0.0 and 1.0. Higher values detect more speakers.

**`max_speakers`** (int, default: `None`)
Limit maximum number of speakers to detect.

**`prefer_current_speaker`** (bool, default: `False`)
Give extra weight to current speaker for word grouping.

**`speaker_config`** (SpeakerFocusConfig, default: `SpeakerFocusConfig()`)
Configure speaker focus/ignore rules.

```python
from speechmatics.voice import SpeakerFocusConfig, SpeakerFocusMode

# Focus only on specific speakers
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
        ignore_speakers=["S3"],
        focus_mode=SpeakerFocusMode.IGNORE
    )
)
```

**`known_speakers`** (list[SpeakerIdentifier], default: `[]`)
Pre-enrolled speaker identifiers for speaker identification.

```python
from speechmatics.voice import SpeakerIdentifier

config = VoiceAgentConfig(
    enable_diarization=True,
    known_speakers=[
        SpeakerIdentifier(label="Alice", speaker_identifiers=["XX...XX"]),
        SpeakerIdentifier(label="Bob", speaker_identifiers=["YY...YY"])
    ]
)
```

### Language & Vocabulary

**`additional_vocab`** (list[AdditionalVocabEntry], default: `[]`)
Custom vocabulary for domain-specific terms.

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

**`punctuation_overrides`** (dict, default: `None`)
Custom punctuation rules.

### Audio Parameters

**`sample_rate`** (int, default: `16000`)
Audio sample rate in Hz.

**`audio_encoding`** (AudioEncoding, default: `PCM_S16LE`)
Audio encoding format.

### Advanced Parameters

**`transcription_update_preset`** (TranscriptionUpdatePreset, default: `COMPLETE`)
Controls when to emit updates: `COMPLETE`, `COMPLETE_PLUS_TIMING`, `WORDS`, `WORDS_PLUS_TIMING`, or `TIMING`.

**`speech_segment_config`** (SpeechSegmentConfig, default: `SpeechSegmentConfig()`)
Fine-tune segment generation and post-processing.

**`smart_turn_config`** (SmartTurnConfig, default: `None`)
Configure SMART_TURN behavior (buffer length, threshold).

**`include_results`** (bool, default: `False`)
Include word-level timing data in segments.

**`include_partials`** (bool, default: `True`)
Emit partial segments. Set to `False` for final-only output.

### Configuration with Overlays

Use presets as a starting point and customize with overlays:

```python
from speechmatics.voice import VoiceAgentConfigPreset, VoiceAgentConfig

# Use preset with custom overrides
config = VoiceAgentConfigPreset.SCRIBE(
    VoiceAgentConfig(
        language="es",
        max_delay=0.8
    )
)

# Available presets
presets = VoiceAgentConfigPreset.list_presets()
# ['low_latency', 'conversation_adaptive', 'conversation_smart_turn', 'scribe', 'captions']
```

### Configuration Serialization

Export and import configurations as JSON:

```python
from speechmatics.voice import VoiceAgentConfigPreset, VoiceAgentConfig

# Export preset to JSON
config_json = VoiceAgentConfigPreset.SCRIBE().to_json()

# Load from JSON
config = VoiceAgentConfig.from_json(config_json)

# Or create from JSON string
config = VoiceAgentConfig.from_json('{"language": "en", "enable_diarization": true}')
```

## Event Messages

The Voice SDK emits structured events via `AgentServerMessageType`. Register handlers using the `@client.on()` decorator or `client.on()` method.

> **Note:** The payloads shown below are the actual message payloads from the Voice SDK. When using the CLI example with `--output-file`, messages also include a `ts` timestamp field (e.g., `"ts": "2025-11-11 23:18:35.909"`), which is added by the CLI for logging purposes and is not part of the SDK payload.

### Core Events

#### RECOGNITION_STARTED

Emitted when transcription session starts. Contains session ID and language pack info.

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

Emitted continuously as speech is being processed. Contains interim text that updates in real-time.

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
      "annotation": ["has_partial"],
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
- `annotation` - Status flags (see annotation section below)
- `metadata.start_time` - Segment start time (seconds since session start)
- `metadata.end_time` - Segment end time (seconds since session start)

Top-level `metadata` contains the same timing plus `processing_time`.

#### ADD_SEGMENT

Emitted when a segment is finalized. Contains stable, final transcription text.

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
      "annotation": [
        "has_final",
        "starts_with_final",
        "ends_with_final",
        "ends_with_eos",
        "ends_with_punctuation"
      ],
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

**Annotation Flags:**

- `has_final` - Contains finalized words
- `has_partial` - Contains partial (interim) words
- `starts_with_final` - First word is finalized
- `ends_with_final` - Last word is finalized
- `ends_with_eos` - Ends with end-of-sentence
- `ends_with_punctuation` - Ends with punctuation
- `fast_speaker` - Speaker is speaking quickly (may appear in some segments)
- `has_disfluency` - Contains disfluencies like "um", "er" (may appear in some segments)

#### END_OF_TURN

Emitted when a speaker's turn is complete. Timing depends on `end_of_utterance_mode`.

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

### Speaker Events

#### SPEAKER_STARTED

Emitted when a speaker starts speaking (voice activity detected).

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

Emitted when a speaker stops speaking (silence detected).

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

Emitted when speaker enrollment completes.

```python
# Request speaker IDs at end of session
await client.send_message({"message": "GetSpeakers", "final": True})

@client.on(AgentServerMessageType.SPEAKERS_RESULT)
def on_speakers(message):
    for speaker in message["speakers"]:
        print(f"Speaker {speaker['label']}: {speaker['speaker_identifiers']}")
```

### Additional Events

**`START_OF_TURN`** - Emitted at the beginning of a new turn.

**`END_OF_TURN_PREDICTION`** - Emitted during `ADAPTIVE` or `SMART_TURN` mode to predict turn completion (fires before `END_OF_TURN`).

**`END_OF_UTTERANCE`** - Low-level STT engine event (fires when silence threshold is reached).

**`ADD_PARTIAL_TRANSCRIPT` / `ADD_TRANSCRIPT`** - Legacy word-level events from underlying Real-Time API (not typically needed with Voice SDK).

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

## API Reference

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
            preset: Preset name ("scribe", "low_latency", etc.) (optional)
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
- Speechmatics API key ([Get one here](https://portal.speechmatics.com/))

## Documentation

- [Speechmatics Documentation](https://docs.speechmatics.com/)
- [Real-Time Quickstart](https://docs.speechmatics.com/speech-to-text/realtime/quickstart)
- [Authentication](https://docs.speechmatics.com/get-started/authentication)

## License

[MIT](LICENSE)
