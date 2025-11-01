# Ambient Scribe / Note-Taking

Real-time ambient transcription for note-taking and documentation. Designed for continuous background transcription where the output feeds into another system.

## Quick Start

```bash
export SPEECHMATICS_API_KEY=your_api_key   # Required
export SPEECHMATICS_RT_URL=endpoint_url    # Optional
python scribe.py
```

Press `CTRL+C` to stop.

## What It Does

- Transcribes conversations in real-time for note-taking
- Uses the SCRIBE preset optimized for ambient transcription
- Shows partial results (yellow) that update as speech continues
- Shows final results (green) with timestamps when sentences complete
- Identifies different speakers (S1, S2, etc.)
- Ideal for meeting notes, interview transcription, or ambient documentation

## Output Example

```
Microphone ready - speak now... (Press CTRL+C to stop)

00:00:03 - S1: Hello, how are you today?
00:00:07 - S2: I'm doing great, thanks for asking.
00:00:12 - S1: That's wonderful to hear.
 listening ...
```

Partial results appear in yellow and update on the same line. Once finalized, they turn green with a timestamp showing elapsed time since session start.

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- PyAudio: `pip install pyaudio`
- Install SDK dependencies: see [examples README](../README.md)

## Configuration

This example uses the SCRIBE preset:

- Fixed end of utterance detection
- 1.2s max delay for smooth note-taking
- Emits finalized sentences as they complete
- Speaker diarization enabled

### Custom Vocabulary

The example automatically loads custom vocabulary from `vocab.json` if present. This helps improve transcription accuracy for domain-specific terms, brand names, or technical jargon.

**Example `vocab.json`:**

```json
[
  {
    "content": "Speechmatics",
    "sounds_like": ["speech matics", "speech mattics"]
  },
  {
    "content": "API"
  }
]
```

Edit `vocab.json` to add your own terms without modifying the Python code.
