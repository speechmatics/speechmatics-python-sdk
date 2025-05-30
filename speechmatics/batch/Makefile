# Makefile for Speechmatics Batch SDK

.PHONY: help install-dev test lint build clean

help:
	@echo "Available commands:"
	@echo "  install-dev   Install with development dependencies"
	@echo "  test          Run tests"
	@echo "  lint          Run linting and type checking"
	@echo "  build         Build distribution packages"
	@echo "  clean         Clean build artifacts"

install-dev:
	pip install -e .
	pip install pytest pytest-cov pytest-mock black ruff mypy types-requests build

test:
	pytest ../../tests/batch/ -v

lint:
	@echo "No source code to lint in batch SDK yet"

build: clean
	pip install build
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info/
	find . -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
