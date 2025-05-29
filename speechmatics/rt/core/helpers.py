"""
Simplified and focused utility functions for the Speechmatics RT SDK.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import os
from collections.abc import AsyncGenerator
from typing import Any, BinaryIO, Union


async def read_audio_chunks(stream: Union[BinaryIO, Any], chunk_size: int) -> AsyncGenerator[bytes | Any]:
    """
    Read audio stream in chunks with async support.

    Args:
        stream: Audio stream with read() method
        chunk_size: Size of each chunk in bytes

    Yields:
        Audio data chunks

    Raises:
        TypeError: If stream doesn't have read method
        IOError: If error reading from stream
    """
    if not hasattr(stream, "read"):
        raise TypeError("Stream must have read() method")

    try:
        while True:
            # Handle both async and sync streams
            if inspect.iscoroutinefunction(stream.read):
                chunk = await stream.read(chunk_size)
            else:
                # Run sync read in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                chunk = await loop.run_in_executor(None, stream.read, chunk_size)

            if not chunk:
                break

            yield chunk

    except Exception as e:
        raise OSError(f"Error reading from stream: {e}")


def get_version() -> str:
    """
    Get SDK version from package metadata or VERSION file.

    Returns:
        Version string
    """
    try:
        return importlib.metadata.version("speechmatics-rt")
    except importlib.metadata.PackageNotFoundError:
        # Fall back to VERSION file for development
        version_path = os.path.join(os.path.dirname(__file__), "VERSION")
        try:
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "unknown"
