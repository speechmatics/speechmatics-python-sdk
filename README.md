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

### 2. (Coming Soon) Batch API Client (`speechmatics-batch`)

A Python client for Speechmatics Batch ASR API.

```bash
pip install speechmatics-batch
```

### 3. (Coming Soon) Flow AI Agent Client (`speechmatics-flow`)

A Python client for Speechmatics Flow AI Agent API.

```bash
pip install speechmatics-flow
```

### 4. (Coming Soon) Command Line Interface (`speechmatics-cli`)

A unified CLI for all Speechmatics products, including ASR metrics tools.

```bash
pip install speechmatics-cli
```

## Development

### Repository Structure

```
speechmatics-python-sdk/     # Main repository name
├── speechmatics/             # Main package namespace
│   ├── batch/                # Batch package
│   │   ├── pyproject.toml
│   │   ├── setup.py          # name="speechmatics-batch"
│   │   ├── VERSION
│   │   └── README.md
│   │
│   ├── rt/                   # Real-time package
│   │   ├── pyproject.toml
│   │   ├── setup.py          # name="speechmatics-rt"
│   │   ├── VERSION
│   │   └── README.md
│   │
│   ├── flow/                 # Flow package
│   │   ├── pyproject.toml
│   │   ├── setup.py          # name="speechmatics-flow"
│   │   ├── VERSION
│   │   └── README.md
│   │
│   └── cli/                  # Combined CLI and ASR metrics package
│       ├── pyproject.toml
│       ├── setup.py          # name="speechmatics-cli"
│       ├── VERSION
│       └── README.md
│
└── LICENSE
```

### Setting Up Development Environment

To set up your development environment for working on one or more packages:

```bash
# Clone the repository
git clone https://github.com/speechmatics/speechmatics-python-sdk.git
cd speechmatics-python-sdk

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install packages in development mode
pip install -e ./speechmatics/rt  # For the RT package
pip install -e ./speechmatics/batch  # For the Batch package
pip install -e ./speechmatics/flow  # For the Flow package
pip install -e ./speechmatics/cli  # For the CLI package
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

### Flow AI Agent Client

- Support for Speechmatics Flow conversational AI capabilities
- Template-based agent configuration
- Tool function support

### Command Line Interface

- Unified CLI for all Speechmatics APIs
- Commands for Batch, Real-Time, and Flow APIs
- ASR metrics tools for evaluating transcription quality

## Installation

Each package can be installed separately:

```bash
# Install individual packages
pip install speechmatics-rt      # Real-Time API client
pip install speechmatics-batch   # Batch API client
pip install speechmatics-flow    # Flow AI client
pip install speechmatics-cli     # Command-line interface
```

## License

MIT
