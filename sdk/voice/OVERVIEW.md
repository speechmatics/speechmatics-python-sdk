# Speechmatics Voice Agent Client Overview

The Speechmatics Voice Agent Client provides a comprehensive set of utilities for building voice agents with real-time speech-to-text capabilities, speaker diarization, and advanced transcription processing.

## Key Features

- **Real-time transcription** with partial and final results
- **Speaker diarization** with configurable focus modes
- **Voice activity detection** (VAD) with adaptive end-of-utterance detection
- **Event-driven architecture** with callback registration
- **TTFB (Time to First Byte) metrics** for performance monitoring

## Installation

```bash
pip install speechmatics-voice
```

## Quick Start

### Basic Voice Agent Setup

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
        end_of_utterance_mode=EndOfUtteranceMode.FIXED
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
        @client.on(AgentServerMessageType.END_OF_UTTERANCE)
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

## Core Components

### VoiceAgentClient

The main client class is the `VoiceAgentClient` which extends `AsyncClient` from the Speechmatics Real-Time SDK.

```python
VoiceAgentClient(
    api_key: Optional[str] = None,              # Speechmatics API key
    url: Optional[str] = None,                  # REST API endpoint URL
    app: Optional[str] = None,                  # Optional application name
    config: Optional[VoiceAgentConfig] = None,  # Optional voice agent config
)
```

**Key Methods:**

- `connect()` - Establish WebSocket connection
- `disconnect()` - Disconnect from WebSocket connection
- `update_diarization_config(config)` - Update the diarization configuration
- `send_audio(frame)` - Send audio data for transcription
- `on(event_type)` - Register event callbacks

**Authentication:**

- Uses `SPEECHMATICS_API_KEY` environment variable
- Custom API key via constructor parameter

### VoiceAgentConfig

Configuration class for voice agent behaviour.

```python
from speechmatics.voice import (
    AdditionalVocabEntry,
    AudioEncoding,
    DiarizationSpeakerConfig,
    EndOfUtteranceMode,
    OperatingPoint,
    VoiceAgentConfig,
)

config = VoiceAgentConfig(
    # Service Configuration
    operating_point=OperatingPoint.ENHANCED,       # Accuracy vs latency tradeoff
    domain=None,                                   # Optional domain specification
    language="en",                                 # Language code (ISO 639-1)
    output_locale="en-GB",                         # Output locale format

    # Timing & Finalisation Control
    max_delay=1.0,                                 # Max delay for transcription (seconds)
    end_of_utterance_silence_trigger=0.5,          # Silence threshold for EOU (seconds)
    end_of_utterance_mode=EndOfUtteranceMode.FIXED,  # EOU detection mode

    # Vocabulary Enhancement
    additional_vocab=[                             # Custom vocabulary entries
        AdditionalVocabEntry(
            content="Speechmatics",
            sounds_like=["speech matters", "speech magic"]
        )
    ],
    punctuation_overrides={},                      # Custom punctuation rules

    # Speaker diarization
    enable_diarization=True,                       # Enable speaker separation
    speaker_sensitivity=0.5,                       # diarization sensitivity (0.0-1.0)
    max_speakers=None,                             # Max speakers to detect
    prefer_current_speaker=False,                  # Prefer grouping words to current speaker
    speaker_config=DiarizationSpeakerConfig(),     # Advanced speaker configuration
    known_speakers=[],                             # Pre-identified speakers

    # Audio Configuration
    sample_rate=16000,                             # Audio sample rate (Hz)
    chunk_size=160,                                # Audio chunk size (samples)
    audio_encoding=AudioEncoding.PCM_S16LE,        # Audio encoding format
)
```

### Event Types

The SDK provides comprehensive event handling through `AgentServerMessageType` (shadows `ServerMessageType` from the RT SDK):

**API Control Messages:**

- `RECOGNITION_STARTED` - Recognition session has started
- `END_OF_TRANSCRIPT` - Recognition session has ended
- `INFO` - Informational message
- `WARNING` - Warning message
- `ERROR` - Error message

**Transcription Messages:**

- `ADD_TRANSCRIPT` - Final transcription results
- `ADD_PARTIAL_TRANSCRIPT` - Partial transcription updates

**Speaker Segments:**

- `ADD_SEGMENTS` - Final speaker segments
- `ADD_INTERIM_SEGMENTS` - Interim speaker segments

**Voice Activity Detection (VAD):**

- `USER_SPEECH_STARTED` - Voice activity detected
- `USER_SPEECH_ENDED` - Voice activity ended

**Speaker Information:**

- `SPEAKERS_RESULT` - Speaker identification results

**Performance Metrics:**

- `METRICS` - General STT engine metrics
- `TTFB_METRICS` - Time to First Byte metrics

### SpeakerSegment

Represents a segment of speech from a specific speaker:

```python
def format_segment(segment: SpeakerSegment) -> str:
    if segment.is_active:
        return segment.format_text("@{speaker_id}: {text}")
    else:
        return segment.format_text("@{speaker_id} (background): {text}")
```

The `format_text()` method uses the following placeholders:

- `{speaker_id}`: The speaker ID (empty if no speaker) (e.g. `S1`).
- `{text}`: The formatted text of the segment (e.g. `Hello, how are you?`).
- `{ts}`: The timestamp of the segment (e.g. `2025-09-03T16:05:01.000Z`).
- `{lang}`: The language of the segment (e.g. `en`).

## Advanced Configuration

### End of Utterance Modes

The end of utterance mode controls how the STT engine detects the end of a user's speech. This can either be fixed silence threshold (defaults to `0.5s`) or it can be adaptive based on speech patterns, rate, pauses, and disfluencies.

```python
from speechmatics.voice import EndOfUtteranceMode

# Fixed silence threshold
EndOfUtteranceMode.FIXED

# Adaptive silence detection (recommended)
EndOfUtteranceMode.ADAPTIVE
```

### Speaker Diarization

The configuration below would:

- focus on speakers `S1` and `S2`
- ignore speakers `S3` and `S4`
- retain words from all other speakers

```python
from speechmatics.voice import DiarizationSpeakerConfig, DiarizationKnownSpeaker

config = VoiceAgentConfig(
    enable_diarization=True,
    diarization_config=DiarizationSpeakerConfig(
        focus_speakers=["S1", "S2"],
        ignore_speakers=["S3", "S4"],
        focus_mode=DiarizationFocusMode.RETAIN,
    )
)
```

### Additional Vocabulary

If you have specific words that you need to make sure are transcribed properly, you can add in up to 1,000 additional vocabulary entries. You can optionally provide a list of words that sound like the word you are adding.

```python
from speechmatics.voice import AdditionalVocabEntry

config = VoiceAgentConfig(
    additional_vocab=[
        AdditionalVocabEntry(
            content="Speechmatics",
            sounds_like=["speech matters", "speech magic"]
        )
    ]
)
```

## Environment Variables

- `SPEECHMATICS_API_KEY` - Your Speechmatics API key
- `SPEECHMATICS_RT_URL` - Custom WebSocket endpoint (optional)
- `SPEECHMATICS_DEBUG_MORE` - Enable verbose debugging
