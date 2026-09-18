"""
Utility functions for the Speechmatics Batch SDK.
"""

from __future__ import annotations

import importlib.metadata
import os
from collections.abc import AsyncGenerator
from collections.abc import Generator
from contextlib import asynccontextmanager
from contextlib import contextmanager
from typing import BinaryIO
from typing import Union

import aiofiles

from ._common import resolve_stream_filename


@asynccontextmanager
async def prepare_audio_file(
    audio_file: Union[str, BinaryIO],
) -> AsyncGenerator[tuple[str, Union[BinaryIO, bytes]], None]:
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
        async with aiofiles.open(audio_file, "rb") as f:
            content = await f.read()
            filename = os.path.basename(audio_file)
            yield filename, content
    else:
        # It's already a file-like object
        yield resolve_stream_filename(audio_file), audio_file


@contextmanager
def prepare_audio_file_sync(
    audio_file: Union[str, BinaryIO],
) -> Generator[tuple[str, Union[BinaryIO, bytes]], None, None]:
    """
    Context manager for file handling with proper resource management.

    The open file handle is yielded rather than its contents so that the upload
    is streamed; a multi-hour audio file never has to fit in memory.

    Args:
        audio_file: Path to audio file or file-like object containing audio data.

    Yields:
        Tuple of (filename, file_data)

    Examples:
        >>> with prepare_audio_file_sync("audio.wav") as (filename, file_data):
        ...     # Use file_data for upload
        ...     pass
    """
    if isinstance(audio_file, str):
        with open(audio_file, "rb") as f:
            yield os.path.basename(audio_file), f
    else:
        yield resolve_stream_filename(audio_file), audio_file


def get_version() -> str:
    try:
        return importlib.metadata.version("speechmatics-batch")
    except importlib.metadata.PackageNotFoundError:
        try:
            from . import __version__

            return __version__
        except ImportError:
            return "0.0.0"
