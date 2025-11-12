# Transcription CLI with Speaker Diarization

Real-time transcription tool using the Speechmatics Voice SDK. Supports microphone input and audio file streaming with speaker diarization.

## Quick Start

**Microphone:**
```bash
python cli.py -k YOUR_API_KEY -p
```
Output saved to `./output/YYYYMMDD_HHMMSS/log.jsonl`

**Audio file:**
```bash
python cli.py -k YOUR_API_KEY -i audio.wav -p
```
Output saved to `./output/YYYYMMDD_HHMMSS/log.jsonl`

Press `CTRL+C` to stop.

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- Install dependencies: see [examples README](../README.md)

## Options

### Quick Reference

Common short codes:
- `-k` API key | `-i` input file | `-o` output dir | `-p` pretty print | `-v` verbose
- `-r` record | `-S` save slices | `-P` preset | `-W` show config
- `-l` language | `-m` mode | `-d` max delay | `-t` silence trigger
- `-f` focus speakers | `-s` known speakers | `-E` enrol

### Core

- `-k, --api-key` - API key (defaults to `SPEECHMATICS_API_KEY` env var)
- `-u, --url` - Server URL (defaults to `SPEECHMATICS_RT_URL` env var)
- `-i, --input-file` - Audio file path (WAV, mono 16-bit). Uses microphone if not specified

### Output

- `-o, --output-dir` - Base output directory (default: ./output)
  - Creates a session subdirectory with timestamp (YYYYMMDD_HHMMSS)
  - Inside session directory:
    - `log.jsonl` - All events with timestamps
    - `recording.wav` - Microphone recording (if `-r` is used)
    - `slice_*.wav` and `slice_*.json` - Audio slices (if `-S` is used)
- `-r, --record` - Record microphone audio to recording.wav (microphone input only)
- `-S, --save-slices` - Save audio slices on SPEAKER_ENDED events (SMART_TURN mode only)
- `-p, --pretty` - Formatted console output with colors
- `-v, --verbose` - Increase verbosity (can repeat: `-v`, `-vv`, `-vvv`, `-vvvv`, `-vvvvv`)
  - `-v` - Add speaker VAD events
  - `-vv` - Add turn predictions
  - `-vvv` - Add segment annotations
  - `-vvvv` - Add metrics
  - `-vvvvv` - Add STT events
- `-L, --legacy` - Show only legacy transcript messages
- `-D, --default-device` - Use default audio device (skip selection)
- `-w, --results` - Include word-level results in segments

### Audio

- `-R, --sample-rate` - Sample rate in Hz (default: 16000)
- `-C, --chunk-size` - Chunk size in bytes (default: 320)
- `-M, --mute` - Mute audio playback for file input

### Voice Agent Config

**Configuration Priority:**
1. Use `--preset` to start with a preset configuration (recommended)
2. Use `-c/--config` to provide a complete JSON configuration
3. Use individual parameters (`-l`, `-d`, `-t`, `-m`) to override preset settings or create custom config

**Preset Options:**

- `-P, --preset` - Use preset configuration: `scribe`, `low_latency`, `conversation_adaptive`, `conversation_smart_turn`, or `captions`
- `--list-presets` - List available presets and exit
- `-W, --show` - Display the final configuration as JSON and exit (after applying preset/config and overrides)

**Configuration Options:**

- `-c, --config` - JSON config string or file path (complete configuration)
- `-l, --language` - Language code (overrides preset if used together)
- `-d, --max-delay` - Max transcription delay in seconds (overrides preset if used together)
- `-t, --end-of-utterance-silence-trigger` - Silence duration for turn end in seconds (overrides preset if used together)
- `-m, --end-of-utterance-mode` - Turn detection mode: `FIXED`, `ADAPTIVE`, `SMART_TURN`, or `EXTERNAL` (overrides preset if used together)

**Note:** When using `-c/--config`, you cannot use `-l`, `-d`, `-t`, `-m`, `-f`, `-I`, `-x`, or `-s` as the config JSON should contain all settings.

### Speaker Management

- `-f, --focus-speakers` - Speakers to focus on (e.g., `S1 S2`)
- `-I, --ignore-speakers` - Speakers to ignore (e.g., `S1 S2`)
- `-x, --ignore-mode` - Use ignore mode (instead of retain) for focus speakers

### Speaker Identification

- `-E, --enrol` - Enrol speakers and output identifiers at end
- `-s, --speakers` - Known speakers JSON string or file path

## Examples

**List presets:**
```bash
python cli.py --list-presets
```

**Show config (from preset):**
```bash
python cli.py -P scribe -W
```

**Show config (with overrides):**
```bash
python cli.py -P scribe -l fr -d 1.0 -W
```

**Use preset:**
```bash
python cli.py -k YOUR_KEY -P scribe -p
```

**Use preset with overrides:**
```bash
python cli.py -k YOUR_KEY -P scribe -l fr -d 1.0 -p
```

**Basic microphone:**
```bash
python cli.py -k YOUR_KEY -p
```
Output saved to `./output/YYYYMMDD_HHMMSS/log.jsonl`

**Record microphone audio:**
```bash
python cli.py -k YOUR_KEY -r -p
```
Recording saved to `./output/YYYYMMDD_HHMMSS/recording.wav`

**Custom output directory:**
```bash
python cli.py -k YOUR_KEY -o ./my_sessions -p
```
Output saved to `./my_sessions/YYYYMMDD_HHMMSS/log.jsonl`

**EXTERNAL mode with manual turn control:**
```bash
python cli.py -k YOUR_KEY -m EXTERNAL -p
```
Press 't' or 'T' to manually signal end of turn.

**Save audio slices (SMART_TURN mode):**
```bash
python cli.py -k YOUR_KEY -P conversation_smart_turn -S -p
```
Audio slices (~8 seconds) saved to `./output/YYYYMMDD_HHMMSS/slice_*.wav` with matching `.json` metadata files on each SPEAKER_ENDED event.

**Audio file:**
```bash
python cli.py -k YOUR_KEY -i audio.wav -p
```

**Audio file (muted):**
```bash
python cli.py -k YOUR_KEY -i audio.wav -Mp
```

**Verbose logging:**
```bash
python cli.py -k YOUR_KEY -vv -p
```
Shows additional events (speaker VAD, turn predictions, etc.)

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

- Output directory (`-o`) defaults to `./output`
- Each session creates a timestamped subdirectory (YYYYMMDD_HHMMSS format)
- Session directory contains:
  - `log.jsonl` - All events with timestamps
  - `recording.wav` - Microphone recording (if `-r` is used)
  - `slice_*.wav` and `slice_*.json` - Audio slices (if `--save-slices` is used in SMART_TURN mode)
- Session subdirectories prevent accidental data loss from multiple runs
- Audio slices are ~8 seconds and saved on each SPEAKER_ENDED event
- JSON metadata includes event details, speaker ID, timing, and slice duration
- Speaker identifiers are encrypted and unique to your API key
- Allow speakers to say at least 20 words before enrolling
- Avoid labels `S1`, `S2` (reserved by engine)
- Labels like `__XXX__` are automatically ignored

See the [Speechmatics documentation](https://docs.speechmatics.com/speech-to-text/realtime/realtime-speaker-identification) for more details.
