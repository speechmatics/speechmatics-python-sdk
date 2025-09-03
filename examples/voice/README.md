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

### File Transcription

An example that takes an audio file and sends it in real-time to the SDK and outputs the interim and final transcription to the console. The audio will also be played through the selected audio output device.

Audio files should be in Mono 16kHz 16-bit WAV format.

```bash
cd examples/voice
pip install -r requirements-examples.txt

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

```bash
cd examples/voice
pip install -r requirements-examples.txt

# Real-time microphone transcription
python microphone_transcription.py
```

**Features:**

- Live microphone input with device selection
- Real-time transcription
- Speaker diarization
- Speaker start / stop events

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

For more information, see the main SDK documentation in [OVERVIEW.md](../OVERVIEW.md).
