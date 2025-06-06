"""
Utility functions for the Speechmatics Batch SDK.
"""

from __future__ import annotations

import importlib.metadata
import io
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import BinaryIO
from typing import Union

import aiofiles  # type: ignore[import-untyped]


@asynccontextmanager
async def prepare_audio_file(audio_file: Union[str, BinaryIO]) -> AsyncGenerator[tuple[str, BinaryIO], None]:
    """
    Async context manager for file handling with proper resource management.

    Args:
        audio_file: Path to audio file or file-like object containing audio data.

    Yields:
        Tuple of (filename, file_data)

    Examples:
        >>> async with prepare_audio_file("audio.wav") as (filename, file_data):
        ...     # Use file_data for upload
        ...     pass
    """
    if isinstance(audio_file, str):
        # Read file asynchronously and create BytesIO object
        async with aiofiles.open(audio_file, "rb") as f:
            content = await f.read()
            filename = os.path.basename(audio_file)
            file_data = io.BytesIO(content)
            try:
                yield filename, file_data
            finally:
                file_data.close()
    else:
        # It's already a file-like object
        filename = getattr(audio_file, "name", "audio.wav")
        if hasattr(filename, "split"):
            filename = os.path.basename(filename)
        yield filename, audio_file


def get_version() -> str:
    """
    Get SDK version from package metadata or version file.

    Returns:
        Version string
    """
    try:
        return importlib.metadata.version("speechmatics-batch")
    except importlib.metadata.PackageNotFoundError:
        version_path = os.path.join("_version")
        try:
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "0.0.0"
