# Speechmatics Voice Agent SDK Examples

This directory contains practical demonstrations of the Speechmatics Voice Agent SDK for real-time speech-to-text applications.

### Setup

Install the Voice SDK to use the examples. Using a virtual environment is recommended.

```shell
# Voice examples
cd <project_directory>

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install requirements for the examples
pip install -r ./examples/voice/requirements-examples.txt
```

## Troubleshooting

**PyAudio installation issues:**

```shell
# macOS
brew install portaudio
pip install pyaudio

# Ubuntu/Debian
sudo apt-get install portaudio19-dev
pip install pyaudio
```

**API key issues:**

```bash
export SPEECHMATICS_API_KEY="your_api_key_here"
```
