# Speechmatics Python SDK

A collection of Python clients for Speechmatics APIs packaged as separate installable packages.
NOTE: These packages are released as Beta versions and may change frequently.

## Packages

This repository contains the following packages:

### 1. (Beta) Real-Time API Client (`speechmatics-rt`)

A Python client for Speechmatics Real-Time ASR API.

```bash
pip install speechmatics-rt
```

### 2. (Beta) Batch API Client (`speechmatics-batch`)

An async Python client for Speechmatics Batch ASR API.

```bash
pip install speechmatics-batch
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
│   └── rt/
│       ├── pyproject.toml
│       └── README.md
│
├── tests/
│   ├── batch/
│   └── rt/
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

# Install development dependencies for both SDKs
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

## Features

### Real-Time API Client

- Async-first design with synchronous wrappers for compatibility
- Comprehensive error handling with detailed error messages
- Type hints throughout for excellent IDE support and code safety
- Environment variable support for secure credential management
- Event-driven architecture for real-time transcript processing
- Structured logging with request tracing for debugging
- Simple connection management with clear error reporting

### Batch API Client

- Async API client with comprehensive error handling
- Type hints throughout for better IDE support
- Environment variable support for credentials
- Easy-to-use interface for submitting, monitoring, and retrieving transcription jobs
- Full job configuration support with all Speechmatics features
- Intelligent transcript formatting with speaker diarization
- Support for multiple output formats (JSON, TXT, SRT)

## Installation

Each package can be installed separately:

```bash
pip install speechmatics-rt
pip install speechmatics-batch
```

## License

MIT
