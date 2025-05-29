# Makefile for Speechmatics RT SDK Development

.PHONY: help install install-dev clean test test-verbose test-coverage lint format type-check security-check pre-commit build publish docs serve-docs clean-build clean-pyc clean-test

# Default target
help:
	@echo "Available commands:"
	@echo "  install       Install package in development mode"
	@echo "  install-dev   Install with development dependencies"
	@echo "  clean         Clean all build artifacts"
	@echo "  test          Run tests"
	@echo "  test-verbose  Run tests with verbose output"
	@echo "  test-coverage Run tests with coverage report"
	@echo "  lint          Run linting (ruff)"
	@echo "  format        Format code with black and ruff"
	@echo "  type-check    Run type checking with mypy"
	@echo "  security-check Run security checks with bandit"
	@echo "  pre-commit    Run all quality checks"
	@echo "  build         Build distribution packages"
	@echo "  publish       Publish to PyPI (requires auth)"
	@echo "  docs          Build documentation"
	@echo "  serve-docs    Serve documentation locally"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e .[dev]
	pre-commit install

# Cleaning
clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

# Testing
test:
	pytest

test-verbose:
	pytest -v

test-coverage:
	pytest --cov=rt --cov-report=html --cov-report=term-missing

# Code Quality
lint:
	ruff check .
	ruff format --check .

format:
	black .
	ruff format .
	ruff check --fix .

type-check:
	mypy rt/

security-check:
	bandit -r rt/ -f json

# Combined quality check
pre-commit: format lint type-check test

# Build and publish
build: clean
	python -m build

publish: build
	python -m twine upload dist/*

# Documentation
docs:
	@echo "Documentation generation not yet configured"

serve-docs:
	@echo "Documentation serving not yet configured"

# Development server for testing
dev-server:
	@echo "Starting development environment..."
	@echo "Run 'make test-coverage' to verify everything works"
