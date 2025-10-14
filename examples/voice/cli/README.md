# Transcription CLI with Speaker Diarization

Command-line tool for real-time transcription using the Speechmatics Voice SDK. Supports both microphone input and audio file streaming with speaker diarization.

## Quick Start

**Microphone:**

```bash
python ./examples/voice/cli/main.py -p -k YOUR_API_KEY
```

**Audio file:**

```bash
python ./examples/voice/cli/main.py -p -k YOUR_API_KEY -i audio.wav
```

Press `CTRL+C` to stop.

## Requirements

- Speechmatics API key from the [portal](https://portal.speechmatics.com/)
- Install dependencies: see [examples README](../README.md)

## Usage

```bash
python ./examples/voice/cli/main.py [OPTIONS]
```

### Core Parameters

**`-k, --api-key`**
Speechmatics API key. Defaults to `SPEECHMATICS_API_KEY` environment variable.

**`-u, --url`**
Custom Speechmatics server URL. Also uses `SPEECHMATICS_SERVER_URL` environment variable, if not provided. Optional, defaults to production endpoint.

**`-i, --input-file FILE`**
Path to input audio file (WAV format, mono 16-bit). If not provided, uses microphone.

**`-p, --pretty`**
Enable formatted console output with colours and emojis.

**`-o, --output-file FILE`**
Save all output to a JSONL file for later analysis.

**`-v, --verbose`**
Increase logging verbosity. `-v` includes `END_OF_TURN_PREDICTION`. `-vv` adds additional payloads: `END_OF_UTTERANCE`, `ADD_PARTIAL_TRANSCRIPT`, and `ADD_TRANSCRIPT`. Useful for debugging or detailed analysis. Default: `0`.

### Audio Configuration

**`--sample-rate`**
Audio sample rate in Hz. Default: `16000`.

**`--chunk-size`**
Audio chunk size in bytes. Default: `320`.

**`-M, --mute`**
Mute audio playback for file input. When enabled, audio files are transcribed without playing through speakers. Default: `False`.

### Turn Detection

**`-m, --end-of-utterance-mode`**
Controls how turn endings are detected. Options:

- `FIXED` - Fixed silence threshold
- `ADAPTIVE` - Adjusts based on speaker characteristics
- `SMART_TURN` - ML-based turn detection
- `EXTERNAL` - Manual control via `finalize()`

**`-t, --end-of-utterance-silence-trigger`**
Silence duration in seconds to trigger turn end. Default: `0.5`.

**`-d, --max-delay`**
Maximum transcription delay in seconds. Default: `0.7`.

### Speaker Management

**`--focus-speakers S1 S2 ...`**
Speakers to focus on. Only these speakers will be emitted as finalized frames.

**`--ignore-speakers S1 S2 ...`**
Specific speakers to exclude from transcription.

**`--ignore-mode`**
Use ignore mode instead of focus mode for `--focus-speakers`.

### Speaker Identification

**`-e, --enrol`**
Enrol speakers and output their identifiers at the end of the session.

**`-s, --speakers JSON|FILE`**
Use known speakers from previous sessions. Provide as either:
- A JSON string: `'[{"label": "Alice", "speaker_identifiers": ["XX...XX"]}]'`
- A path to a JSON file: `speakers.json`

**`--preview`**
Enable preview features.

## Examples

### Microphone - basic transcription

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -p
```

### Audio file - basic transcription

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -i audio.wav -p
```

### Audio file - muted (no playback)

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -i audio.wav -Mp
```

### With adaptive turn detection

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -m ADAPTIVE -p
```

### Enrol speakers (microphone)

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -ep
```

Press `CTRL+C` when done. Speaker identifiers will be displayed:

```json
[{ "label": "S1", "speaker_identifiers": ["XX...XX"] }]
```

### Use known speakers (JSON string)

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -s '[{"label": "Alice", "speaker_identifiers": ["XX...XX"]}]' -p
```

### Use known speakers (JSON file)

Create a `speakers.json` file:

```json
[
  {
    "label": "Alice",
    "speaker_identifiers": ["XX...XX"]
  },
  {
    "label": "Bob",
    "speaker_identifiers": ["YY...YY"]
  }
]
```

Then run:

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -s speakers.json -p
```

Output shows speaker labels:

```
@Alice: Hello, how are you?
@Bob: I'm doing well, thanks!
```

### Focus on specific speakers

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY --focus-speakers S1 S2 -p
```

### Save to file

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -o output.jsonl -p
```

### Verbose logging

Show turn prediction events:

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -i audio.wav -v -p
```

Include additional payloads for debugging:

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -i audio.wav -vv -p
```

### Audio file with speaker focus

```bash
python ./examples/voice/cli/main.py -k YOUR_KEY -i audio.wav --focus-speakers S2 -p
```

## Speaker Identification

Speaker identifiers are encrypted and unique to your API key. They enable the engine to recognise speakers across sessions.

**Best practices:**

- Allow speakers to say at least 20 words before enrolling
- Avoid using labels `S1`, `S2` (reserved by engine)
- Labels in format `__XXX__` are automatically ignored

For more details, see the [Speechmatics documentation](https://docs.speechmatics.com/speech-to-text/realtime/realtime-speaker-identification).
