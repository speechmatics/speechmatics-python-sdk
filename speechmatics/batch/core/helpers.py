"""
Utility functions for the Speechmatics Batch SDK.
"""

from __future__ import annotations
import io
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from typing import BinaryIO
from typing import Union

import aiofiles  # type: ignore[import-untyped]

from speechmatics.shared.version import get_version as _get_version


def get_version() -> str:
    """
    Get SDK version from package metadata or VERSION file.

    Returns:
        Version string
    """
    return _get_version("speechmatics-batch", os.path.dirname(__file__))


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


def prepare_file_data(file_path_or_data: Union[str, BinaryIO]) -> tuple[str, BinaryIO]:
    """
    Prepare file data for upload (synchronous version for backward compatibility).

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
