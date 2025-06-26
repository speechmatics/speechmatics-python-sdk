from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from typing import BinaryIO

from .constants import CHUNK_SIZE


class FileSource:
    """
    Audio buffer for a single file or stream.
    This source wraps a single file-like object and yields audio chunks.

    Args:
        fh: File-like object opened in binary read mode. Must have a read() method.
        chunk_size: Number of bytes to read per chunk. Defaults to 4096.

    Yields:
        Bytes: Audio chunks.

    Example:
        >>> async with aiofiles.open("speech.wav", "rb") as audio_file:
        ...     source = FileSource(audio_file, chunk_size=4096)
        ...     async for chunk in source:
        ...         pass
    """

    def __init__(self, fh: BinaryIO, *, chunk_size: int = CHUNK_SIZE):
        self._fh, self._n = fh, chunk_size

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """
        Asynchronously iterate over audio chunks from the file.

        Reads chunks of the specified size until EOF is reached. Each chunk
        is yielded as a bytes object. The iteration
        stops automatically when read() returns empty bytes.

        Yields:
            Bytes: Audio chunks.
        """
        async for chunk in _make_iter(self._fh, self._n):
            yield chunk


class MultiChanSource:
    """
    Audio source for multiple simultaneous file streams.
    This source manages multiple file-like objects, reading from each in a
    round-robin fashion to ensure fair bandwidth distribution across channels.

    Args:
        mapping: Dictionary mapping channel IDs to file-like objects.
                Keys are channel identifiers (e.g., "left", "right").
                Values must be file-like objects opened in binary read mode.
        chunk_size: Number of bytes to read per chunk from each file.
                   Defaults to 4096. Same size is used for all channels.

    Yields:
        Tuple[str, bytes]: Channel ID and audio chunk pairs until all streams are exhausted.

    Example:
        Stereo audio from separate files:
        >>> sources = {
        ...     "left": open("left_channel.pcm", "rb"),
        ...     "right": open("right_channel.pcm", "rb")
        ... }
        >>> source = MultiChanSource(sources, chunk_size=4096)
        >>> async for channel_id, chunk in source:
        ...     pass
    """

    def __init__(self, mapping: dict[str, BinaryIO], *, chunk_size: int = CHUNK_SIZE):
        self._mapping, self._n = mapping, chunk_size

    async def __aiter__(self) -> AsyncIterator[tuple[str, bytes]]:
        """
        Asynchronously iterate over audio chunks from all channels.
        The method supports both synchronous and asynchronous file handles.

        Implements round-robin reading across all channels. Each iteration
        attempts to read from the next channel in sequence. Iteration stops
        when a channel reaches EOF.

        Yields:
            Tuple[str, bytes]: Channel ID and audio chunk pairs.
        """
        # round-robin queue
        chan_iters = [(chan_id, _make_iter(fh, self._n)) for chan_id, fh in self._mapping.items()]

        i = 0
        while True:
            chan_id, it = chan_iters[i]
            try:
                chunk = await it.__anext__()
            except StopAsyncIteration:
                # Stop all iters when one reaches EOF
                break
            yield chan_id, chunk
            i = (i + 1) % len(chan_iters)


async def _make_iter(fh: BinaryIO, chunk_size: int) -> AsyncIterator[bytes]:
    assert chunk_size > 0, "chunk_size must be > 0"
    loop = asyncio.get_running_loop()

    async def read_chunk() -> bytes:
        if inspect.iscoroutinefunction(fh.read):
            return await fh.read(chunk_size)  # type: ignore[no-any-return]
        return await loop.run_in_executor(None, fh.read, chunk_size)

    while True:
        data = await read_chunk()
        if not data:
            break
        yield data
