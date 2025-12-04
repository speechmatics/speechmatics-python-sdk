# Transcription CLI with Speaker Diarization

Real-time transcription tool using the Speechmatics Voice SDK. Supports microphone input and audio file streaming with speaker diarization.

## Quick Start

**Microphone:**

```bash
# Quick example
python cli.py -k YOUR_API_KEY -p

# Example that saves the output in verbose mode using a preset
python cli.py -k YOUR_API_KEY -vvvvvpDSr -P smart_turn
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
- `-r` record | `-P` preset | `-w` show compact config | `-W` show complete config
- `-s` known speakers | `-E` enrol

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
- `-r, --record` - Record microphone audio to recording.wav (microphone input only)
- `-p, --pretty` - Formatted console output with colors
- `-v, --verbose` - Increase verbosity (can repeat: `-v`, `-vv`, `-vvv`, `-vvvv`, `-vvvvv`)
  - `-v` - Add speaker VAD events
  - `-vv` - Add turn predictions
  - `-vvv` - Add segment annotations
  - `-vvvv` - Add metrics
  - `-vvvvv` - Add STT events
- `-L, --legacy` - Show only legacy transcript messages
- `-D, --default-device` - Use default audio device (skip selection)
- `--results` - Include word-level results in segments

### Audio

- `--sample-rate` - Sample rate in Hz (default: 16000)
- `--chunk-size` - Chunk size in bytes (default: 320)
- `-M, --mute` - Mute audio playback for file input

### Voice Agent Config

**Configuration (Required):**

You must provide either a preset or a config file:

- `-P, --preset` - Use preset configuration: `scribe`, `fast`, `adaptive`, `smart_turn`, or `captions`
- `-c, --config` - JSON config string or file path (complete configuration)
- `--list-presets` - List available presets and exit

**Note:** `--preset` and `--config` are mutually exclusive. You cannot use both together.

**Display Configuration:**

- `-w, --show-compact` - Display compact configuration as JSON and exit (excludes unset and None values)
- `-W, --show-complete` - Display complete configuration as JSON and exit (includes all defaults)

### Speaker Identification

- `-E, --enrol` - Enrol speakers and output identifiers at end
- `-s, --speakers` - Known speakers JSON string or file path (can be used with preset or config)

## Examples

**List presets:**

```bash
python cli.py --list-presets
```

**Show compact config (from preset):**

```bash
python cli.py -P scribe -w
```

**Show complete config (from preset):**

```bash
python cli.py -P scribe -W
```

**Use preset:**

```bash
python cli.py -k YOUR_KEY -P scribe -p
```

**Basic microphone (requires preset or config):**

```bash
python cli.py -k YOUR_KEY -P adaptive -p
```

Output saved to `./output/YYYYMMDD_HHMMSS/log.jsonl`

**Record microphone audio:**

```bash
python cli.py -k YOUR_KEY -P adaptive -r -p
```

Recording saved to `./output/YYYYMMDD_HHMMSS/recording.wav`

**Custom output directory:**

```bash
python cli.py -k YOUR_KEY -P adaptive -o ./my_sessions -p
```

Output saved to `./my_sessions/YYYYMMDD_HHMMSS/log.jsonl`

**Audio file:**

```bash
python cli.py -k YOUR_KEY -P scribe -i audio.wav -p
```

**Audio file (muted):**

```bash
python cli.py -k YOUR_KEY -P scribe -i audio.wav -Mp
```

**Verbose logging:**

```bash
python cli.py -k YOUR_KEY -P adaptive -vv -p
```

Shows additional events (speaker VAD, turn predictions, etc.)

**Enrol speakers:**

```bash
python cli.py -k YOUR_KEY -P adaptive -Ep
```

Press `CTRL+C` when done to see speaker identifiers.

**Use known speakers:**

```bash
python cli.py -k YOUR_KEY -P adaptive -s speakers.json -p
```

Example `speakers.json`:

```json
[
  { "label": "Alice", "speaker_identifiers": ["XX...XX"] },
  { "label": "Bob", "speaker_identifiers": ["YY...YY"] }
]
```

**Custom config file:**

```bash
python cli.py -k YOUR_KEY -c config.json -p
```

**Custom config with known speakers:**

```bash
python cli.py -k YOUR_KEY -c config.json -s speakers.json -p
```

## Notes

- Output directory (`-o`) defaults to `./output`
- Each session creates a timestamped subdirectory (YYYYMMDD_HHMMSS format)
- Session directory contains:
  - `log.jsonl` - All events with timestamps
  - `recording.wav` - Microphone recording (if `-r` is used)
- Session subdirectories prevent accidental data loss from multiple runs
- Speaker identifiers are encrypted and unique to your API key
- Allow speakers to say at least 20 words before enrolling
- Avoid labels `S1`, `S2` (reserved by engine)
- Labels like `__XXX__` are automatically ignored

See the [Speechmatics documentation](https://docs.speechmatics.com/speech-to-text/realtime/realtime-speaker-identification) for more details.
