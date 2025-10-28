# Speechmatics Voice Agent SDK Examples

This directory contains practical demonstrations of the Speechmatics Voice Agent SDK for real-time speech-to-text applications.

### Setup

Install the Voice SDK to use the examples. Using a virtual environment is recommended.

```shell
# Voice examples
cd <project_directory>

# Create a virtual environment
python -m venv .venv

# Activate : macOS / Ubuntu / Debian
source .venv/bin/activate

# Activate : Windows
.venv\Scripts\activate

# Update pip
python -m pip install --upgrade pip
```

**PyAudio installation:**

For macOS and Linux you need to install the `portaudio` package.

```shell
# macOS
brew install portaudio

# Ubuntu/Debian
sudo apt-get install portaudio19-dev
```

**Package dependencies:**

Install dependencies from the project root.

```shell
# Voice SDK
python -m pip install -e 'sdk/voice[dev,smart]'

# Required packages
python -m pip install pyaudio certifi
```
