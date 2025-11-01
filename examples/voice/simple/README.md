# Simple Microphone Transcription

Basic real-time transcription example using your default microphone with speaker diarization.

## Quick Start

```bash
export SPEECHMATICS_API_KEY=your_api_key
python app.py
```

Press `CTRL+C` to stop.

## What It Does

- Uses your default microphone
- Transcribes speech in real-time
- Identifies different speakers (S1, S2, etc.)
- Shows partial results as you speak
- Shows final results when complete
- Detects end of turn using adaptive mode

## Output Example

```
Microphone ready - speak now... (Press CTRL+C to stop)

[PARTIAL] S1: Hello
[PARTIAL] S1: Hello how
[PARTIAL] S1: Hello how are
[FINAL] S1: Hello, how are you?
[END OF TURN]
[PARTIAL] S2: I'm
[PARTIAL] S2: I'm good
[FINAL] S2: I'm good, thanks!
[END OF TURN]
```

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- PyAudio: `pip install pyaudio`
- Install SDK dependencies: see [examples README](../README.md)

## Configuration

This example uses standard settings:

- Language: English
- Turn detection: Adaptive (adjusts to speaker characteristics)
- Speaker diarization: Enabled
- Sample rate: 16kHz
- Chunk size: 320 bytes

For more advanced options, see the [transcribe_mic](../transcribe_mic) example.
