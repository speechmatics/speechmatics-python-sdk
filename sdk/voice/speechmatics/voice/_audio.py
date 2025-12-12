#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import asyncio

import numpy as np


class AudioBuffer:
    """Rolling audio buffer.

    A rolling audio buffer that has a set sample_rate, sample_size,
    frame_size and total_seconds. As the buffer fills, the oldest
    data is removed and the start_time is updated.

    The function get_slice(start_time, end_time) will return a snapshot
    of the data between the start_time and end_time. If the start_time is
    before the start of the buffer, then the start_time will be set to the
    start of the buffer. If the end_time is after the end of the buffer,
    then the end_time will be set to the end of the buffer.

    Timing is based on the number of bytes added to the buffer.

    The buffer is thread-safe and can be used from multiple threads, using
    asyncio locks to ensure thread safety.
    """

    def __init__(self, sample_rate: int, frame_size: int, sample_width: int = 2, total_seconds: float = 20.0):
        """Initialise the audio buffer.

        Args:
            sample_rate: The sample rate of the audio.
            frame_size: The frame size of the audio.
            sample_width: The sample width in bytes (1 or 2).
            total_seconds: The total number of seconds to keep in the buffer.
        """
        # Store audio format info
        self._sample_rate: int = sample_rate
        self._sample_width: int = sample_width
        self._frame_size: int = frame_size
        self._frame_bytes: int = frame_size * sample_width
        self._frame_duration: float = round(frame_size / sample_rate, 3)

        # Queue
        self._frames: list[bytes] = []
        self._max_frames: int = int(total_seconds * (sample_rate / frame_size))
        self._lock = asyncio.Lock()

        # Under / overflow
        self._buffer: bytes = b""

        # Timing info
        self._total_frames: int = 0

    def _get_time_from_frame(self, frame_index: int) -> float:
        """Get the time from a frame index.

        Args:
            frame_index: The frame index.

        Returns:
            The time in seconds.
        """
        return frame_index * self._frame_duration

    def _get_frame_from_time(self, time: float) -> int:
        """Get the frame index from a time.

        Uses int() with a small epsilon to handle floating-point precision issues
        while maintaining consistent truncation behaviour.

        Args:
            time: The time in seconds.

        Returns:
            The frame index.
        """
        return int(time / self._frame_duration)  #  + 1e-9)

    async def put_bytes(self, data: bytes) -> None:
        """Add data to the buffer.

        Arbitrary length of bytes to save to buffer. Accumulates until there is
        a frame size worth of data, then puts a frame into the buffer.

        Args:
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

        Args:
            data: The data frame to add to the buffer.
        """

        # Add data to the buffer
        async with self._lock:
            self._frames.append(data)
            self._total_frames += 1
            if len(self._frames) > self._max_frames:
                self._frames = self._frames[-self._max_frames :]

    async def get_frames(self, start_time: float, end_time: float, fade_out: float = 0) -> bytes:
        """Get a slice of the buffer.

        Get a slice of the buffer between the start_time and end_time.
        If the start_time is before the start of the buffer, then the
        start_time will be set to the start of the buffer. If the end_time
        is after the end of the buffer, then the end_time will be set to
        the end of the buffer.

        If a fade out time is specified, then the end of the slice will be
        faded out by the specified amount of seconds.

        Args:
            start_time: The start time of the slice.
            end_time: The end time of the slice.
            fade_out: The fade out time in seconds.

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

            # Bytes
            data = b"".join(frames)

            # Fade out
            if fade_out > 0:
                data = self._fade_out_audio(data, fade_out=fade_out)

            # Return the joined frames
            return data

    def _fade_out_audio(self, data: bytes, fade_out: float = 0.01) -> bytes:
        """Apply a fade-out over the final `fade_out` seconds of PCM audio data.

        Args:
            data: Raw PCM audio data as bytes.
            fade_out: Duration of fade-out in seconds (e.g., 0.01 = 10 ms).

        Returns:
            Bytes with fade-out applied.
        """
        # Choose dtype
        dtype: type[np.signedinteger]
        if self._sample_width == 1:
            dtype = np.int8
        elif self._sample_width == 2:
            dtype = np.int16
        else:
            raise ValueError(f"Unsupported sample_width {self._sample_width}: must be 1 or 2")

        # Convert bytes to NumPy array
        samples = np.frombuffer(data, dtype=dtype)

        # Number of samples to fade
        fade_samples = int(self._sample_rate * fade_out)
        if fade_samples <= 0 or fade_samples > len(samples):
            return data

        # Linear fade envelope
        envelope = np.linspace(1.0, 0.0, fade_samples, endpoint=True)

        # Apply fade
        faded = samples.astype(np.float32)
        faded[-fade_samples:] *= envelope

        # Convert back to original dtype and bytes
        return bytes(faded.astype(dtype).tobytes())

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
        return self._total_frames * self._frame_duration

    @property
    def size(self) -> int:
        """Get the size of the buffer."""
        return len(self._frames)
