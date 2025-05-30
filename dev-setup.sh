#!/bin/bash
# Development setup script for Speechmatics Python SDK
# Installs all packages in development mode

set -e

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating the environment with:"
echo "source .venv/bin/activate"
source .venv/bin/activate

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    pip install uv
fi

# Install development dependencies
echo "Installing development dependencies..."
uv pip install pytest pytest-cov black ruff mypy pre-commit

# Install all packages in development mode
echo "Installing all packages in development mode..."
uv pip install -e ./speechmatics/rt && uv pip install -e ./speechmatics/batch

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

echo "Development setup complete!"
echo "Pre-commit hooks are now installed and will run on every commit."
echo "To run pre-commit on all files manually: pre-commit run --all-files"
