# Transcription CLI with Speaker Diarization

Real-time transcription tool using the Speechmatics Voice SDK. Supports microphone input and audio file streaming with speaker diarization.

## Quick Start

**Microphone:**
```bash
python cli.py -p -k YOUR_API_KEY
```

**Audio file:**
```bash
python cli.py -p -k YOUR_API_KEY -i audio.wav
```

Press `CTRL+C` to stop.

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- Install dependencies: see [examples README](../README.md)

## Options

### Core

- `-k, --api-key` - API key (defaults to `SPEECHMATICS_API_KEY` env var)
- `-u, --url` - Server URL (defaults to `SPEECHMATICS_RT_URL` env var)
- `-i, --input-file` - Audio file path (WAV, mono 16-bit). Uses microphone if not specified
- `-c, --config` - JSON config string or file path (overrides other Voice Agent options)

### Output

- `-p, --pretty` - Formatted console output with colors
- `-o, --output-file` - Save output to JSONL file
- `-v, --verbose` - Increase verbosity (can repeat: `-v`, `-vv`, `-vvv`, `-vvvv`, `-vvvvv`)
  - `-v` - Add speaker VAD events
  - `-vv` - Add turn predictions
  - `-vvv` - Add segment annotations
  - `-vvvv` - Add metrics
  - `-vvvvv` - Add STT events
- `-L, --legacy` - Show only legacy transcript messages
- `--results` - Include word-level results in segments

### Audio

- `--sample-rate` - Sample rate in Hz (default: 16000)
- `--chunk-size` - Chunk size in bytes (default: 320)
- `-M, --mute` - Mute audio playback for file input
- `-D, --default-device` - Use default audio device (skip selection)

### Voice Agent Config

- `-l, --language` - Language code (default: en)
- `-d, --max-delay` - Max transcription delay in seconds (default: 0.7)
- `-t, --end-of-utterance-silence-trigger` - Silence duration for turn end (default: 0.5)
- `-m, --end-of-utterance-mode` - Turn detection mode: `FIXED`, `ADAPTIVE`, `SMART_TURN`, or `EXTERNAL`
- `-e, --emit-sentences` - Emit sentence-level segments
- `--forced-eou` - Enable forced end of utterance

### Speaker Management

- `-f, --focus-speakers` - Speakers to focus on (e.g., `S1 S2`)
- `-I, --ignore-speakers` - Speakers to ignore (e.g., `S1 S2`)
- `-x, --ignore-mode` - Use ignore mode (instead of retain) for focus speakers

### Speaker Identification

- `-E, --enrol` - Enrol speakers and output identifiers at end
- `-s, --speakers` - Known speakers JSON string or file path

## Examples

**Basic microphone:**
```bash
python cli.py -k YOUR_KEY -p
```

**Audio file:**
```bash
python cli.py -k YOUR_KEY -i audio.wav -p
```

**Audio file (muted):**
```bash
python cli.py -k YOUR_KEY -i audio.wav -Mp
```

**Save output:**
```bash
python cli.py -k YOUR_KEY -o output.jsonl -p
```

**Verbose logging:**
```bash
python cli.py -k YOUR_KEY -vv -p
```

**Focus on speakers:**
```bash
python cli.py -k YOUR_KEY -f S1 S2 -p
```

**Enrol speakers:**
```bash
python cli.py -k YOUR_KEY -Ep
```
Press `CTRL+C` when done to see speaker identifiers.

**Use known speakers:**
```bash
python cli.py -k YOUR_KEY -s speakers.json -p
```

Example `speakers.json`:
```json
[
  {"label": "Alice", "speaker_identifiers": ["XX...XX"]},
  {"label": "Bob", "speaker_identifiers": ["YY...YY"]}
]
```

**Custom config:**
```bash
python cli.py -k YOUR_KEY -c config.json -p
```

## Notes

- Speaker identifiers are encrypted and unique to your API key
- Allow speakers to say at least 20 words before enrolling
- Avoid labels `S1`, `S2` (reserved by engine)
- Labels like `__XXX__` are automatically ignored

See the [Speechmatics documentation](https://docs.speechmatics.com/speech-to-text/realtime/realtime-speaker-identification) for more details.
