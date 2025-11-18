# Speechmatics Python SDK

[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/speechmatics/speechmatics-python-sdk/blob/master/LICENSE)

A collection of Python clients for Speechmatics APIs packaged as separate installable packages. These packages replace the old [speechmatics-python](https://pypi.org/project/speechmatics-python) package, which will be deprecated soon.

Each client targets a specific Speechmatics API (e.g. real-time, batch transcription), making it easier to install only what you need and keep dependencies minimal.

## Packages

This repository contains the following packages:

### (Beta) Real-Time Client (`speechmatics-rt`)

A Python client for Speechmatics Real-Time API.

```bash
pip install speechmatics-rt
```

### (Beta) Batch Client (`speechmatics-batch`)

An async Python client for Speechmatics Batch API.

```bash
pip install speechmatics-batch
```

### (Beta) Flow Client (`speechmatics-flow`)

An async Python client for Speechmatics Flow API.

```bash
pip install speechmatics-flow
```

### (Beta) Voice Agent Client (`speechmatics-voice`)

A Voice Agent Python client for Speechmatics Real-Time API.

```bash
# Standard installation
pip install speechmatics-voice

# With SMART_TURN (ML-based turn detection)
pip install speechmatics-voice[smart]
```

### (Beta) TTS Client (`speechmatics-tts`)

An async Python client for Speechmatics TTS API.

```bash
pip install speechmatics-tts
```

## Development

### Repository Structure

```
speechmatics-python-sdk/
├── sdk/
│   ├── batch/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── rt/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── flow/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── voice/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── tts/
│   │   ├── pyproject.toml
│   │   └── README.md
│
├── tests/
│   ├── batch/
│   ├── rt/
│   ├── flow/
│   ├── voice/
│   └── tts/
│
├── examples/
├── Makefile
├── pyproject.toml
└── LICENSE
```

### Setting Up Development Environment

```bash
git clone https://github.com/speechmatics/speechmatics-python-sdk.git
cd speechmatics-python-sdk

python -m venv .venv
source .venv/bin/activate

# Install development dependencies for SDKs
make install-dev
```

On Windows:

```bash
.venv\Scripts\activate
```

### Install pre-commit hooks

```bash
pre-commit install
```

## Installation

Each package can be installed separately:

```bash
pip install speechmatics-rt
pip install speechmatics-batch
pip install speechmatics-flow
pip install speechmatics-voice[smart]
pip install speechmatics-tts
```

## Docs

The Speechmatics API and product documentation can be found at https://docs.speechmatics.com

## License

[MIT](LICENSE)
