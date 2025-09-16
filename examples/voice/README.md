# Speechmatics Voice Agent SDK Examples

This directory contains practical demonstrations of the Speechmatics Voice Agent SDK for real-time speech-to-text applications.

## Installation

```bash
pip install -r requirements-examples.txt
```

**Requirements:**

- Python 3.9+
- PyAudio for audio I/O
- Valid Speechmatics API key in `SPEECHMATICS_API_KEY` environment variable

## Examples

### Setup

Install the Voice SDK to use the examples. Using a virtual environment is recommended.

```bash
# Voice examples
cd examples/voice

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install requirements for the examples
pip install -r requirements-examples.txt
```

### File Transcription

An example that takes an audio file and sends it in real-time to the SDK and outputs the interim and final transcription to the console. The audio will also be played through the selected audio output device.

By default, this demo will focus on the second speaker and is set to ignore the first speaker altogether. This means that you may hear the first speaker's audio but not see their transcription. You can change this by modifying the `speaker_config` parameters in the `VoiceAgentConfig`.

Audio files should be in Mono 16kHz 16-bit WAV format.

```
usage: file_transcription.py [-h] [--api-key API_KEY] [--url URL]
                             [--focus-speakers [FOCUS_SPEAKERS ...]]
                             [--ignore-speakers [IGNORE_SPEAKERS ...]]
                             [--ignore-mode] [--max-delay MAX_DELAY]
                             [--end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER]
                             [--end-of-utterance-mode {FIXED,ADAPTIVE}]
                             [audio_file]

Transcribe an audio file with real-time playback and speaker diarisation using Speechmatics Voice API

positional arguments:
  audio_file            Path to the input audio file (WAV format, mono 16-bit). Defaults to '../example2.wav'

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)
  --url URL             Speechmatics server URL (optional)
  --focus-speakers [FOCUS_SPEAKERS ...]
                        Speakers to focus on (e.g., S1 S2). Use with --ignore-mode to ignore these speakers instead
  --ignore-speakers [IGNORE_SPEAKERS ...]
                        Specific speakers to ignore (e.g., S1 S2)
  --ignore-mode         Use ignore mode instead of focus mode for --focus-speakers
  --max-delay MAX_DELAY
                        Maximum delay for transcription results in seconds (default: 0.7)
  --end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER
                        Silence duration to trigger end of utterance in seconds (default: 0.5)
  --end-of-utterance-mode {FIXED,ADAPTIVE}
                        End of utterance detection mode (default: ADAPTIVE)

Example: python file_transcription.py audio.wav --focus-speakers S1 --max-delay 1.0
```

```bash
# Transcribe the default example audio file
python file_transcription.py

# Transcribe a custom audio file (16kHz Mono 16-bit WAV)
python file_transcription.py path/to/your/audio.wav
```

**Features:**

- File streaming
- Audio playback through selected device
- Real-time transcription
- Speaker diarization
- Speaker start / stop events

### Microphone Transcription

An example that takes audio from a microphone and sends it in real-time to the SDK and outputs the interim and final transcription to the console.

By default this will focus on the first speaker only. Adjust the `speaker_config` parameters in the `VoiceAgentConfig` to change this.

```
usage: microphone_transcription.py [-h] [--api-key API_KEY] [--url URL]
                                   [--sample-rate SAMPLE_RATE] [--chunk-size CHUNK_SIZE]
                                   [--focus-speakers [FOCUS_SPEAKERS ...]] [--ignore-speakers [IGNORE_SPEAKERS ...]]
                                   [--ignore-mode] [--max-delay MAX_DELAY]
                                   [--end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER]
                                   [--end-of-utterance-mode {FIXED,ADAPTIVE}]

Live microphone transcription with speaker diarisation using Speechmatics Voice API

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)
  --url URL             Speechmatics server URL (optional)
  --sample-rate SAMPLE_RATE
                        Audio sample rate in Hz (default: 16000)
  --chunk-size CHUNK_SIZE
                        Audio chunk size in bytes (default: 320)
  --focus-speakers [FOCUS_SPEAKERS ...]
                        Speakers to focus on (e.g., S1 S2). Use with --ignore-mode to ignore these speakers instead
  --ignore-speakers [IGNORE_SPEAKERS ...]
                        Specific speakers to ignore (e.g., S1 S2)
  --ignore-mode         Use ignore mode instead of focus mode for --focus-speakers
  --max-delay MAX_DELAY
                        Maximum delay for transcription results in seconds (default: 0.7)
  --end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER
                        Silence duration to trigger end of utterance in seconds (default: 0.5)
  --end-of-utterance-mode {FIXED,ADAPTIVE}
                        End of utterance detection mode (default: ADAPTIVE)

Example: python microphone_transcription.py --focus-speakers S1 S2 --max-delay 1.0
```

```bash
# Real-time microphone transcription
python microphone_transcription.py
```

**Features:**

- Live microphone input with device selection
- Real-time transcription
- Speaker diarization
- Speaker start / stop events

### File to JSONL

An example that takes an audio file and sends it in real-time to the SDK and outputs the transcription to a JSONL file. This can be useful for debugging or for processing the transcription results in a different way.

```
usage: file_to_jsonl.py input_file
                        [-h] [--api-key API_KEY] [--url URL] [--output OUTPUT]
                        [--focus-speakers [FOCUS_SPEAKERS ...]] [--ignore-speakers [IGNORE_SPEAKERS ...]] [--ignore-mode]
                        [--max-delay MAX_DELAY]
                        [--end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER]
                        [--end-of-utterance-mode {FIXED,ADAPTIVE}]

Transcribe an audio file to JSONL format using Speechmatics Voice API

positional arguments:
  input_file            Path to the input audio file (WAV format)

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     Speechmatics API key (defaults to SPEECHMATICS_API_KEY environment variable)
  --url URL             Speechmatics server URL (optional)
  --output OUTPUT, -o OUTPUT
                        Output JSONL file (defaults to stdout)
  --focus-speakers [FOCUS_SPEAKERS ...]
                        Speakers to focus on (e.g., S1 S2). Use with --ignore-mode to ignore these speakers instead
  --ignore-speakers [IGNORE_SPEAKERS ...]
                        Specific speakers to ignore (e.g., S1 S2)
  --ignore-mode         Use ignore mode instead of focus mode for --focus-speakers
  --max-delay MAX_DELAY
                        Maximum delay for transcription results in seconds (default: 0.7)
  --end-of-utterance-silence-trigger END_OF_UTTERANCE_SILENCE_TRIGGER
                        Silence duration to trigger end of utterance in seconds (default: 0.5)
  --end-of-utterance-mode {FIXED,ADAPTIVE}
                        End of utterance detection mode (default: FIXED)

Example: python file_to_jsonl.py --output transcription.jsonl --focus-speakers S1 example1.wav
```

```bash
# Transcribe the default example audio file
python file_to_jsonl.py ../example1.wav --api-key $SPEECHMATICS_API_KEY
```

## Troubleshooting

**PyAudio installation issues:**

```bash
# macOS
brew install portaudio
pip install pyaudio

# Ubuntu/Debian
sudo apt-get install portaudio19-dev
pip install pyaudio
```

**No audio devices found:**

- Ensure PyAudio is properly installed
- Check system audio permissions
- Verify audio devices are connected and recognised

**API key issues:**

```bash
export SPEECHMATICS_API_KEY="your_api_key_here"
```

For more information, see the main SDK documentation in [OVERVIEW.md](../../OVERVIEW.md).
