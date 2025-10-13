# Transcription CLI with Speaker Diarization

Command-line tool for real-time transcription using the Speechmatics Voice SDK. Supports both microphone input and audio file streaming with speaker diarization.

## Quick Start

**Microphone:**

```bash
python ./examples/voice/cli/main.py --pretty --api-key YOUR_API_KEY
```

**Audio file:**

```bash
python ./examples/voice/cli/main.py --pretty --api-key YOUR_API_KEY --input-file audio.wav
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

**`--api-key`**
Speechmatics API key. Defaults to `SPEECHMATICS_API_KEY` environment variable.

**`--url`**
Custom Speechmatics server URL. Optional, defaults to production endpoint.

**`--input-file FILE`**
Path to input audio file (WAV format, mono 16-bit). If not provided, uses microphone.

**`--pretty`**
Enable formatted console output with colours and emojis.

**`--jsonl FILE`**
Save all output to a JSONL file for later analysis.

### Audio Configuration

**`--sample-rate`**
Audio sample rate in Hz. Default: `16000`.

**`--chunk-size`**
Audio chunk size in bytes. Default: `320`.

### Turn Detection

**`--end-of-utterance-mode`**
Controls how turn endings are detected. Options:

- `FIXED` - Fixed silence threshold
- `ADAPTIVE` - Adjusts based on speaker characteristics
- `SMART_TURN` - ML-based turn detection
- `EXTERNAL` - Manual control via `finalize()`

**`--end-of-utterance-silence-trigger`**
Silence duration in seconds to trigger turn end. Default: `0.5`.

**`--max-delay`**
Maximum transcription delay in seconds. Default: `0.7`.

### Speaker Management

**`--focus-speakers S1 S2 ...`**
Speakers to focus on. Only these speakers will be emitted as finalized frames.

**`--ignore-speakers S1 S2 ...`**
Specific speakers to exclude from transcription.

**`--ignore-mode`**
Use ignore mode instead of focus mode for `--focus-speakers`.

### Speaker Identification

**`--enrol`**
Enrol speakers and output their identifiers at the end of the session.

**`--speakers JSON`**
Use known speakers from previous sessions. Provide as JSON array.

**`--preview`**
Enable preview features.

## Examples

### Microphone - basic transcription

```bash
python ./examples/voice/cli/main.py --api-key YOUR_KEY --pretty
```

### Audio file - basic transcription

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --input-file audio.wav \
  --pretty
```

### With adaptive turn detection

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --end-of-utterance-mode ADAPTIVE \
  --pretty
```

### Enrol speakers (microphone)

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --enrol \
  --pretty
```

Press `CTRL+C` when done. Speaker identifiers will be displayed:

```json
[{ "label": "S1", "speaker_identifiers": ["XX...XX"] }]
```

### Use known speakers

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --speakers '[{"label": "Alice", "speaker_identifiers": ["XX...XX"]}]' \
  --pretty
```

Output shows speaker labels:

```
@Alice: Hello, how are you?
```

### Focus on specific speakers

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --focus-speakers S1 S2 \
  --pretty
```

### Save to file

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --jsonl output.jsonl \
  --pretty
```

### Audio file with speaker focus

```bash
python ./examples/voice/cli/main.py \
  --api-key YOUR_KEY \
  --input-file audio.wav \
  --focus-speakers S2 \
  --pretty
```

## Speaker Identification

Speaker identifiers are encrypted and unique to your API key. They enable the engine to recognise speakers across sessions.

**Best practices:**

- Allow speakers to say at least 20 words before enrolling
- Avoid using labels `S1`, `S2` (reserved by engine)
- Labels in format `__XXX__` are automatically ignored

For more details, see the [Speechmatics documentation](https://docs.speechmatics.com/speech-to-text/realtime/realtime-speaker-identification).
