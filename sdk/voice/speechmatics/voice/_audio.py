#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import asyncio


class AudioBuffer:
    """Rolling audio buffer.

    A rolling audio buffer that has a set sample_rate, sample_size,
    frame_size and total_seconds. As the buffer fills, the oldest
    data is removed and the start_time is updated.

    The function get_slice(start_time, end_time) will return a snapshot
    ot the data between the start_time and end_time. If the start_time is
    before the start of the buffer, then the start_time will be set to the
    start of the buffer. If the end_time is after the end of the buffer,
    then the end_time will be set to the end of the buffer.

    Timing is based on the number of bytes added to the buffer.

    The buffer is thread-safe and can be used from multiple threads, using
    asyncio locks to ensure thread safety.

    Parameters:
        sample_rate: The sample rate of the audio.
        frame_size: The frame size of the audio.
        total_seconds: The total number of seconds to keep in the buffer.
    """

    def __init__(self, sample_rate: int, frame_size: int, sample_width: int = 2, total_seconds: float = 20.0):
        # Store audio format info
        self._sample_rate: int = sample_rate
        self._sample_width: int = sample_width
        self._frame_size: int = frame_size
        self._frame_bytes: int = frame_size * sample_width

        # Queue
        self._frames: list[bytes] = []
        self._max_frames: int = int(total_seconds * (sample_rate / frame_size))
        self._lock = asyncio.Lock()

        # Under / overflow
        self._buffer: bytes = b""

        # Timing info
        self._total_frames: int = 0

    def _get_time_from_frame(self, frame_index: int) -> float:
        """Get the time from a frame index."""
        return frame_index / (self._sample_rate / self._frame_size)

    def _get_frame_from_time(self, time: float) -> int:
        """Get the frame index from a time.

        Uses int() with a small epsilon to handle floating-point precision issues
        while maintaining consistent truncation behaviour.
        """
        return int(time * (self._sample_rate / self._frame_size) + 1e-9)

    async def put_bytes(self, data: bytes) -> None:
        """Add data to the buffer.

        Arbitrary length of bytes to save to buffer. Accumulates until there is
        a frame size worth of data, then puts a frame into the buffer.

        Arguments:
            data: The data frame to add to the buffer.
        """

        # If the right length and buffer zero
        if len(data) // self._sample_width == self._frame_size and len(self._buffer) == 0:
            return await self.put_frame(data)

        # Add to the buffer
        self._buffer += data

        # While the buffer is greater than or equal to the frame size
        while len(self._buffer) >= self._frame_bytes:
            # Get the frame
            frame = self._buffer[: self._frame_bytes]

            # Remove the frame from the buffer
            self._buffer = self._buffer[self._frame_bytes :]

            # Put the frame into the queue
            await self.put_frame(frame)

    async def put_frame(self, data: bytes) -> None:
        """Add data to the buffer.

        New data added to the end of the buffer. The oldest data is removed
        to maintain the total number of seconds in the buffer.

        Arguments:
            data: The data frame to add to the buffer.
        """

        # Add data to the buffer
        async with self._lock:
            self._frames.append(data)
            self._total_frames += 1
            if len(self._frames) > self._max_frames:
                self._frames = self._frames[-self._max_frames :]

    async def get_frames(self, start_time: float, end_time: float) -> bytes:
        """Get a slice of the buffer.

        Get a slice of the buffer between the start_time and end_time.
        If the start_time is before the start of the buffer, then the
        start_time will be set to the start of the buffer. If the end_time
        is after the end of the buffer, then the end_time will be set to
        the end of the buffer.

        Arguments:
            start_time: The start time of the slice.
            end_time: The end time of the slice.

        Returns:
            The slice of the buffer between the start_time and end_time.
        """

        # Get the slice of the buffer
        async with self._lock:
            # Get the start and end frame indices (absolute frame numbers)
            start_index = self._get_frame_from_time(start_time)
            end_index = self._get_frame_from_time(end_time)

            # Calculate the range of frames currently in the buffer
            buffer_start_frame = self._total_frames - len(self._frames)
            buffer_end_frame = self._total_frames

            # Check if the requested range is entirely outside the buffer
            if end_index <= buffer_start_frame or start_index >= buffer_end_frame:
                return b""

            # Clamp the requested range to what's available in the buffer
            clamped_start = max(start_index, buffer_start_frame)
            clamped_end = min(end_index, buffer_end_frame)

            # Convert absolute frame indices to buffer indices
            actual_start_index = clamped_start - buffer_start_frame
            actual_end_index = clamped_end - buffer_start_frame

            # Get what frames are available
            frames = self._frames[actual_start_index:actual_end_index]

            # Return the joined frames
            return b"".join(frames)

    async def reset(self) -> None:
        """Reset the buffer."""
        async with self._lock:
            self._frames = []

    @property
    def total_frames(self) -> int:
        """Get the total number of frames added to the buffer."""
        return self._total_frames

    @property
    def total_time(self) -> float:
        """Get the total time added to the buffer."""
        return self._get_time_from_frame(self._total_frames)

    @property
    def size(self) -> int:
        """Get the size of the buffer."""
        return len(self._frames)
