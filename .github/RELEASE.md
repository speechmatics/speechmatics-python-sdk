# Release Process Documentation

This document outlines the release process for the Speechmatics Python SDK packages.

## Overview

The Speechmatics Python SDK repository contains two separate packages:
- `speechmatics-rt` - Real-Time API Client
- `speechmatics-batch` - Batch API Client

Each package is released independently with its own versioning and release workflow.

## Pre-Release Checklist

Before creating a release, ensure the following steps are completed:

### Code Quality
- [ ] All tests pass locally (`make test-all`)
- [ ] Linting passes (`make lint-all`)
- [ ] Type checking passes (`make type-check-all`)
- [ ] Examples work correctly with the new version
- [ ] Documentation is up to date

### Version Management
- [ ] Review and update README files if needed
- [ ] Verify dependencies are correct in `pyproject.toml`

### Testing
- [ ] Test examples with fresh installations
- [ ] Verify environment variables work correctly
- [ ] Test error handling scenarios
- [ ] Validate API compatibility

## Release Process

### 1. RT SDK Release

To release a new version of the RT SDK:

1. **Create a Release Tag**
   ```bash
   git tag rt/v1.0.0
   git push origin rt/v1.0.0
   ```

2. **Automated Workflow**
   The `release-rt.yaml` workflow will automatically:
   - Extract version from tag (e.g., `rt/v1.0.0` → `1.0.0`)
   - Run comprehensive tests across Python versions
   - Update version in `sdk/rt/speechmatics/rt/__init__.py`
   - Build the package
   - Publish to PyPI

3. **Manual Steps After Release**
   - Verify the package is available on PyPI
   - Test installation: `pip install speechmatics-rt==1.0.0`
   - Update GitHub release notes
   - Announce the release

### 2. Batch SDK Release

To release a new version of the Batch SDK:

1. **Create a Release Tag**
   ```bash
   git tag batch/v1.0.0
   git push origin batch/v1.0.0
   ```

2. **Automated Workflow**
   The `release-batch.yaml` workflow will automatically:
   - Extract version from tag (e.g., `batch/v1.0.0` → `1.0.0`)
   - Run comprehensive tests across Python versions
   - Update version in `sdk/batch/speechmatics/batch/__init__.py`
   - Build the package
   - Publish to PyPI

3. **Manual Steps After Release**
   - Verify the package is available on PyPI
   - Test installation: `pip install speechmatics-batch==1.0.0`
   - Update GitHub release notes
   - Announce the release

## Version Management

### Version Format
Both packages follow semantic versioning (SemVer):
- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- `MAJOR.MINOR.PATCH-beta.N` for beta releases (e.g., `1.2.3-beta.1`)

### Version Update Process
1. **Development**: Versions remain as `0.0.0` in `__init__.py` files
2. **Release**: GitHub Actions automatically updates the version during release
3. **Post-Release**: The updated version remains in the repository

### Tag Naming Convention
- RT SDK: `rt/v{version}` (e.g., `rt/v1.0.0`)
- Batch SDK: `batch/v{version}` (e.g., `batch/v1.0.0`)

## Environment Setup

### PyPI Configuration
Both packages are published to PyPI using GitHub Actions with OpenID Connect (OIDC):
- RT SDK: Uses `pypi-rt` environment
- Batch SDK: Uses `pypi-batch` environment

### Required Secrets
No manual secrets are required as the workflows use OIDC for PyPI authentication.

## Testing Matrix

Both packages are tested against:
- Python versions: 3.9, 3.10, 3.11, 3.12, 3.13
- Operating system: Ubuntu (latest)
