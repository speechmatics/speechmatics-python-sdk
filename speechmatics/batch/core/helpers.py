"""
Utility functions for the Speechmatics Batch SDK.
"""

from __future__ import annotations

import importlib.metadata
import os
from typing import BinaryIO


def get_version() -> str:
    """
    Get SDK version from package metadata or VERSION file.

    Returns:
        Version string
    """
    try:
        return importlib.metadata.version("speechmatics-batch")
    except importlib.metadata.PackageNotFoundError:
        # Fall back to VERSION file for development
        version_path = os.path.join(os.path.dirname(__file__), "VERSION")
        try:
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "unknown"


def prepare_file_data(file_path_or_data: str | BinaryIO) -> tuple[str, BinaryIO]:
    """
    Prepare file data for upload.

    Args:
        file_path_or_data: Either a file path string or a file-like object

    Returns:
        Tuple of (filename, file_data)
    """
    if isinstance(file_path_or_data, str):
        # It's a file path
        filename = os.path.basename(file_path_or_data)
        file_data = open(file_path_or_data, "rb")
        return filename, file_data
    else:
        # It's a file-like object
        filename = getattr(file_path_or_data, "name", "audio.wav")
        if hasattr(filename, "split"):
            filename = filename.split("/")[-1]  # Get basename
        return filename, file_path_or_data
