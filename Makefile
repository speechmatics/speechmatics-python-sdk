# Makefile for Speechmatics Python SDKs

.PHONY: help
.PHONY: test-all test-rt test-batch test-flow test-tts
.PHONY: format-all format-rt format-batch format-flow format-tts
.PHONY: lint-all lint-rt lint-batch lint-flow lint-tts
.PHONY: type-check-all type-check-rt type-check-batch type-check-flow type-check-tts
.PHONY: build-all build-rt build-batch build-flow build-tts
.PHONY: clean-all clean-rt clean-batch clean-flow clean-tts

help:
	@echo "Available commands:"
	@echo "  help              Display this help message"
	@echo "Testing:"
	@echo "  test-all          Run tests for all SDKs"
	@echo "  test-rt           Run tests for RT SDK"
	@echo "  test-batch        Run tests for Batch SDK"
	@echo "  test-flow         Run tests for Flow SDK"
	@echo ""
	@echo "Code formatting:"
	@echo "  format-all        Auto-fix formatting for all SDKs"
	@echo "  format-rt         Auto-fix formatting for RT SDK"
	@echo "  format-batch      Auto-fix formatting for Batch SDK"
	@echo "  format-flow       Auto-fix formatting for Flow SDK"
	@echo ""
	@echo "Linting:"
	@echo "  lint-all          Run linting for all SDKs"
	@echo "  lint-rt           Run linting for RT SDK"
	@echo "  lint-batch        Run linting for Batch SDK"
	@echo "  lint-flow         Run linting for Flow SDK"
	@echo ""
	@echo "Type checking:"
	@echo "  type-check-all    Run type checking for all SDKs"
	@echo "  type-check-rt     Run type checking for RT SDK"
	@echo "  type-check-batch  Run type checking for Batch SDK"
	@echo "  type-check-flow   Run type checking for Flow SDK"
	@echo ""
	@echo "Building:"
	@echo "  build-all         Build all SDKs"
	@echo "  build-rt          Build RT SDK"
	@echo "  build-batch       Build Batch SDK"
	@echo "  build-flow        Build Flow SDK"
	@echo "  build-tts         Build TTS SDK"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean-all         Clean all SDKs"
	@echo "  clean-rt          Clean RT SDK build artifacts"
	@echo "  clean-batch       Clean Batch SDK build artifacts"
	@echo "  clean-flow        Clean Flow SDK build artifacts"
	@echo "  clean-tts         Clean TTS SDK build artifacts"
	@echo ""

# Testing targets
test-all: test-rt test-batch test-flow test-tts

test-rt:
	pytest tests/rt/ -v

test-batch:
	pytest tests/batch/ -v

test-flow:
	pytest tests/flow/ -v

# Formatting targets
format-all: format-rt format-batch format-flow format-tts

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

# Linting targets
lint-all: lint-rt lint-batch lint-flow lint-tts

lint-rt:
	cd sdk/rt/speechmatics && ruff check .

lint-batch:
	cd sdk/batch/speechmatics && ruff check .

lint-flow:
	cd sdk/flow/speechmatics && ruff check .

lint-tts:
	cd sdk/tts/speechmatics && ruff check .

# Type checking targets
type-check-all: type-check-rt type-check-batch type-check-flow type-check-tts

type-check-rt:
	cd sdk/rt/speechmatics && mypy .

type-check-batch:
	cd sdk/batch/speechmatics && mypy .

type-check-flow:
	cd sdk/flow/speechmatics && mypy .

type-check-tts:
	cd sdk/tts/speechmatics && mypy .

# Installation targets
install-dev:
	python -m pip install --upgrade pip
	python -m pip install -e sdk/rt[dev]
	python -m pip install -e sdk/batch[dev]
	python -m pip install -e sdk/flow[dev]
	python -m pip install -e sdk/tts[dev]

install-build:
	python -m pip install --upgrade build

# Building targets
build-all: build-rt build-batch build-flow build-tts

build-rt: install-build
	cd sdk/rt && python -m build

build-batch: install-build
	cd sdk/batch && python -m build

build-flow: install-build
	cd sdk/flow && python -m build

build-tts: install-build
	cd sdk/tts && python -m build

# Cleaning targets
clean-all: clean-rt clean-batch clean-flow clean-tts

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