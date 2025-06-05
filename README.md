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

A Python client for Speechmatics Batch ASR API.

```bash
pip install speechmatics-batch
```

## Development

### Repository Structure

```
speechmatics-python-sdk/
├── speechmatics/
│   ├── batch/
│   │   ├── pyproject.toml
│   │   ├── requirements.txt
│   │   ├── VERSION
│   │   └── README.md
│   │
│   ├── rt/
│   │   ├── pyproject.toml
│   │   ├── requirements.txt
│   │   ├── VERSION
│   │   └── README.md
│   │
└── LICENSE
```

### Setting Up Development Environment

```bash
git clone https://github.com/speechmatics/speechmatics-python-sdk.git
cd speechmatics-python-sdk

python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
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

- Async-first design with sync wrappers
- Comprehensive error handling
- Type hints throughout for better IDE support
- Environment variable support for credentials
- Event-driven architecture for handling transcription results

### Batch API Client

- Async and sync API clients
- Full support for all Batch API features
- Easy-to-use interface for submitting, monitoring, and retrieving transcription jobs

## Installation

Each package can be installed separately:

```bash
pip install speechmatics-rt
pip install speechmatics-batch
```

## License

MIT
