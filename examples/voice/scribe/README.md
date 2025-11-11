# Ambient Scribe

Real-time transcription for note-taking and documentation. Uses the default microphone and the SCRIBE preset.

A custom dictionary can be used to improve accuracy for domain-specific terms. The example `vocab.json` is loaded automatically if present.

## Quick Start

```bash
export SPEECHMATICS_API_KEY=your_api_key
python scribe.py
```

Press `CTRL+C` to stop.

## Features

- Real-time transcription with speaker diarization
- Partial results (yellow) update as speech continues
- Final results (green) shown with timestamps
- Automatically loads custom vocabulary from `vocab.json` if present
- Uses SCRIBE preset (fixed EOU, 1s max delay, sentence emission)

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- PyAudio: `pip install pyaudio`
- See [examples README](../README.md) for SDK dependencies

## Output Example

```
Microphone ready - speak now... (Press CTRL+C to stop)

00:00:03 - S1: Hello, how are you today?
00:00:07 - S2: I'm doing great, thanks for asking.
00:00:12 - S1: That's wonderful to hear.
 listening ...
```

## Custom Vocabulary

Create `vocab.json` to improve accuracy for domain-specific terms:

```json
[
  {
    "content": "Speechmatics",
    "sounds_like": ["speech matics"]
  },
  {
    "content": "API"
  }
]
```
