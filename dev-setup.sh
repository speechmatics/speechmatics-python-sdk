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
uv pip install pytest pytest-cov black ruff mypy

# Install all packages in development mode
echo "Installing all packages in development mode..."
uv pip install -e ./speechmatics/rt && uv pip install -e ./speechmatics/batch

echo "Development setup complete!"
