# Makefile for Speechmatics Python SDKs

.PHONY: help test-all lint-all build-all clean-all rt-% batch-%

help:
	@echo "Available commands:"
	@echo "  test-all      Run tests for both RT and Batch SDKs"
	@echo "  lint-all      Run linting for both RT and Batch SDKs"
	@echo "  build-all     Build both RT and Batch SDKs"
	@echo "  clean-all     Clean both RT and Batch SDKs"
	@echo "  rt-*          Run command for RT SDK (e.g., rt-test, rt-build)"
	@echo "  batch-*       Run command for Batch SDK (e.g., batch-test, batch-build)"

test-all: rt-test batch-test

lint-all: rt-lint batch-lint

build-all: rt-build batch-build

clean-all: rt-clean batch-clean

rt-%:
	@$(MAKE) -C speechmatics/rt $*

batch-%:
	@$(MAKE) -C speechmatics/batch $*
