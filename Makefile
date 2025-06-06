# Makefile for Speechmatics Python SDKs

.PHONY: help
.PHONY: test-all test-rt test-batch
.PHONY: format-all format-rt format-batch
.PHONY: lint-all lint-rt lint-batch
.PHONY: type-check-all type-check-rt type-check-batch
.PHONY: build-all build-rt build-batch
.PHONY: clean-all clean-rt clean-batch

help:
	@echo "Available commands:"
	@echo "  help              Display this help message"
	@echo "Testing:"
	@echo "  test-all          Run tests for both RT and Batch SDKs"
	@echo "  test-rt           Run tests for RT SDK"
	@echo "  test-batch        Run tests for Batch SDK"
	@echo ""
	@echo "Code formatting:"
	@echo "  format-all        Auto-fix formatting for both SDKs"
	@echo "  format-rt         Auto-fix formatting for RT SDK"
	@echo "  format-batch      Auto-fix formatting for Batch SDK"
	@echo ""
	@echo "Linting:"
	@echo "  lint-all          Run linting for both SDKs"
	@echo "  lint-rt           Run linting for RT SDK"
	@echo "  lint-batch        Run linting for Batch SDK"
	@echo ""
	@echo "Type checking:"
	@echo "  type-check-all    Run type checking for both SDKs"
	@echo "  type-check-rt     Run type checking for RT SDK"
	@echo "  type-check-batch  Run type checking for Batch SDK"
	@echo ""
	@echo "Building:"
	@echo "  build-all         Build both RT and Batch SDKs"
	@echo "  build-rt          Build RT SDK"
	@echo "  build-batch       Build Batch SDK"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean-dist        Clean distribution artifacts"
	@echo "  clean-all         Clean both RT and Batch SDKs"
	@echo "  clean-rt          Clean RT SDK build artifacts"
	@echo "  clean-batch       Clean Batch SDK build artifacts"

# Testing targets
test-all: test-rt test-batch

test-rt:
	pytest tests/rt/ -v

test-batch:
	pytest tests/batch/ -v

# Formatting targets
format-all: format-rt format-batch

format-rt:
	cd sdk/rt/speechmatics && black .
	cd sdk/rt/speechmatics && ruff check --fix .

format-batch:
	cd sdk/batch/speechmatics && black .
	cd sdk/batch/speechmatics && ruff check --fix .

# Linting targets
lint-all: lint-rt lint-batch

lint-rt:
	cd sdk/rt/speechmatics && ruff check .

lint-batch:
	cd sdk/batch/speechmatics && ruff check .

# Type checking targets
type-check-all: type-check-rt type-check-batch

type-check-rt:
	cd sdk/rt/speechmatics && mypy .

type-check-batch:
	cd sdk/batch/speechmatics && mypy .

# Installation targets
install-dev:
	python -m pip install --upgrade pip
	python -m pip install -e sdk/rt[dev]
	python -m pip install -e sdk/batch[dev]

install-build:
	python -m pip install --upgrade build

# Building targets
build-all: build-rt build-batch

build-rt: install-build
	cd sdk/rt && python -m build

build-batch: install-build
	cd sdk/batch && python -m build

# Cleaning targets
clean-all: clean-rt clean-batch

clean-dist:
	rm -rf dist/

clean-rt:
	rm -rf sdk/rt/dist sdk/rt/build sdk/rt/*.egg-info
	find sdk/rt -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

clean-batch:
	rm -rf sdk/batch/dist sdk/batch/build sdk/batch/*.egg-info
	find sdk/batch -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
