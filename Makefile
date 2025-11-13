# Makefile for Speechmatics Python SDKs

.PHONY: help
.PHONY: test-all test-rt test-batch test-flow test-tts test-voice
.PHONY: format-all format-rt format-batch format-flow format-tts format-voice format-sdk
.PHONY: lint-all lint-rt lint-batch lint-flow lint-tts lint-voice lint-sdk
.PHONY: type-check-all type-check-rt type-check-batch type-check-flow type-check-tts type-check-voice
.PHONY: build-all build-rt build-batch build-flow build-tts build-voice build-sdk
.PHONY: clean-all clean-rt clean-batch clean-flow clean-tts clean-voice clean-sdk


help:
	@echo "Available commands:"
	@echo "  help              Display this help message"
	@echo "Testing:"
	@echo "  test-all          Run tests for all SDKs"
	@echo "  test-rt           Run tests for RT SDK"
	@echo "  test-batch        Run tests for Batch SDK"
	@echo "  test-flow         Run tests for Flow SDK"
	@echo "  test-tts          Run tests for TTS SDK"
	@echo "  test-voice        Run tests for Voice Agent SDK"
	@echo ""
	@echo "Code formatting:"
	@echo "  format-all        Auto-fix formatting for all SDKs"
	@echo "  format-rt         Auto-fix formatting for RT SDK"
	@echo "  format-batch      Auto-fix formatting for Batch SDK"
	@echo "  format-flow       Auto-fix formatting for Flow SDK"
	@echo "  format-tts        Auto-fix formatting for TTS SDK"
	@echo "  format-voice      Auto-fix formatting for Voice Agent SDK"
	@echo "  format-sdk        Auto-fix formatting for SDK meta-package"
	@echo ""
	@echo "Linting:"
	@echo "  lint-all          Run linting for all SDKs"
	@echo "  lint-rt           Run linting for RT SDK"
	@echo "  lint-batch        Run linting for Batch SDK"
	@echo "  lint-flow         Run linting for Flow SDK"
	@echo "  lint-tts          Run linting for TTS SDK"
	@echo "  lint-voice        Run linting for Voice Agent SDK"
	@echo "  lint-sdk          Run linting for SDK meta-package"
	@echo ""
	@echo "Type checking:"
	@echo "  type-check-all    Run type checking for all SDKs"
	@echo "  type-check-rt     Run type checking for RT SDK"
	@echo "  type-check-batch  Run type checking for Batch SDK"
	@echo "  type-check-flow   Run type checking for Flow SDK"
	@echo "  type-check-tts    Run type checking for TTS SDK"
	@echo "  type-check-voice  Run type checking for Voice Agent SDK"
	@echo "  type-check-sdk    Run type checking for SDK meta-package"
	@echo ""
	@echo "Building:"
	@echo "  build-all         Build all SDKs"
	@echo "  build-rt          Build RT SDK"
	@echo "  build-batch       Build Batch SDK"
	@echo "  build-flow        Build Flow SDK"
	@echo "  build-tts         Build TTS SDK"
	@echo "  build-voice       Build Voice Agent SDK"
	@echo "  build-sdk         Build SDK meta-package"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean-all         Clean all SDKs"
	@echo "  clean-rt          Clean RT SDK build artifacts"
	@echo "  clean-batch       Clean Batch SDK build artifacts"
	@echo "  clean-flow        Clean Flow SDK build artifacts"
	@echo "  clean-tts         Clean TTS SDK build artifacts"
	@echo "  clean-voice       Clean Voice Agent SDK build artifacts"
	@echo "  clean-sdk         Clean SDK meta-package build artifacts"
	@echo ""

# Testing targets
test-all: test-rt test-batch test-flow test-tts test-voice
test-rt:
	pytest tests/rt/ -v -s

test-batch:
	pytest tests/batch/ -v -s

test-flow:
	pytest tests/flow/ -v -s

test-tts:
	pytest tests/tts/ -v -s

test-voice:
	pytest tests/voice/ -v -s

# Formatting targets
format-all: format-rt format-batch format-flow format-tts format-voice format-sdk format-tests format-examples

format-rt:
	cd sdk/rt/speechmatics && black .
	cd sdk/rt/speechmatics && ruff check --fix .

format-batch:
	cd sdk/batch/speechmatics && black .
	cd sdk/batch/speechmatics && ruff check --fix .

format-flow:
	cd sdk/flow/speechmatics && black .
	cd sdk/flow/speechmatics && ruff check --fix .

format-tts:
	cd sdk/tts/speechmatics && black .
	cd sdk/tts/speechmatics && ruff check --fix .

format-voice:
	cd sdk/voice/speechmatics && black .
	cd sdk/voice/speechmatics && ruff check --fix .

format-sdk:
	cd sdk/sdk/speechmatics && black .
	cd sdk/sdk/speechmatics && ruff check --fix .

format-tests:
	cd tests && black .
	cd tests && ruff check --fix .

format-examples:
	cd examples && black .
	cd examples && ruff check --fix .

# Linting targets
lint-all: lint-rt lint-batch lint-flow lint-tts lint-voice lint-sdk

lint-rt:
	cd sdk/rt/speechmatics && ruff check .

lint-batch:
	cd sdk/batch/speechmatics && ruff check .

lint-flow:
	cd sdk/flow/speechmatics && ruff check .

lint-tts:
	cd sdk/tts/speechmatics && ruff check .

lint-voice:
	cd sdk/voice/speechmatics && ruff check .

lint-sdk:
	cd sdk/sdk/speechmatics && ruff check .

# Type checking targets
type-check-all: type-check-rt type-check-batch type-check-flow type-check-tts type-check-voice type-check-sdk
type-check-rt:
	cd sdk/rt/speechmatics && mypy .

type-check-batch:
	cd sdk/batch/speechmatics && mypy .

type-check-flow:
	cd sdk/flow/speechmatics && mypy .

type-check-tts:
	cd sdk/tts/speechmatics && mypy .

type-check-voice:
	cd sdk/voice/speechmatics && mypy .

type-check-sdk:
	cd sdk/sdk/speechmatics && mypy .

# Installation targets
install-dev:
	python -m pip install --upgrade pip
	python -m pip install -e sdk/rt[dev]
	python -m pip install -e sdk/batch[dev]
	python -m pip install -e sdk/flow[dev]
	python -m pip install -e sdk/tts[dev]
	python -m pip install -e sdk/voice[dev]

install-build:
	python -m pip install --upgrade build

# Building targets
build-all: build-rt build-batch build-flow build-tts build-voice build-sdk

build-rt: install-build
	cd sdk/rt && python -m build

build-batch: install-build
	cd sdk/batch && python -m build

build-flow: install-build
	cd sdk/flow && python -m build

build-tts: install-build
	cd sdk/tts && python -m build

build-voice: install-build
	cd sdk/voice && python -m build

build-sdk: install-build
	cd sdk/sdk && python -m build

# Cleaning targets
clean-all: clean-rt clean-batch clean-flow clean-tts clean-voice clean-sdk clean-test clean-examples
clean-rt:
	rm -rf sdk/rt/dist sdk/rt/build sdk/rt/*.egg-info
	find sdk/rt -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-batch:
	rm -rf sdk/batch/dist sdk/batch/build sdk/batch/*.egg-info
	find sdk/batch -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-flow:
	rm -rf sdk/flow/dist sdk/flow/build sdk/flow/*.egg-info
	find sdk/flow -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-tts:
	rm -rf sdk/tts/dist sdk/tts/build sdk/tts/*.egg-info
	find sdk/tts -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-voice:
	rm -rf sdk/voice/dist sdk/voice/build sdk/voice/*.egg-info
	find sdk/voice -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-sdk:
	rm -rf sdk/sdk/dist sdk/sdk/build sdk/sdk/*.egg-info
	find sdk/sdk -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-test:
	find tests -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .mypy_cache

clean-examples:
	find examples -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
