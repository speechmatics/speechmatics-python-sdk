from __future__ import annotations

import asyncio
import logging
from typing import Any
from typing import Optional

logger = logging.getLogger(__name__)


class Microphone:
    """
    Microphone audio capture for streaming live audio.
    Requires pyaudio to be installed for actual microphone access.

    Examples:
        Basic usage:
            >>> mic = Microphone()
            >>> if mic.start():
            ...     await client.transcribe(mic)
            >>> mic.stop()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 4096,
        device_index: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        if sample_rate <= 0 or channels <= 0 or chunk_size <= 0:
            raise ValueError("Sample rate, channels, and chunk size must be positive")

        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = chunk_size
        self._device_index = device_index
        self._is_recording = False
        self._audio: Optional[Any] = None
        self._stream: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = loop

        # Check if pyaudio is available
        try:
            import pyaudio

            self._pyaudio = pyaudio

        except ImportError:
            self._pyaudio = None

    def start(self) -> bool:
        """Start microphone recording. Returns True if successful."""
        if not self._pyaudio:
            return False

        if self._is_recording:
            return True

        try:
            self._audio = self._pyaudio.PyAudio()
            self._stream = self._audio.open(
                format=self._pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk_size,
                input_device_index=self._device_index,
            )
            self._is_recording = True
            logger.info(f"Microphone started: {self._sample_rate}Hz, {self._channels} channel(s)")
            return True

        except Exception as e:
            logger.error(f"Failed to start microphone: {e}")
            self._cleanup()
            return False

    def stop(self) -> None:
        """Stop microphone recording and cleanup resources."""
        if not self._is_recording:
            return

        self._is_recording = False
        self._cleanup()
        logger.info("Microphone stopped")

    def _cleanup(self) -> None:
        """Clean up audio resources."""
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._audio:
            try:
                self._audio.terminate()
            except Exception:
                pass
            self._audio = None

    async def read(self, chunk_size: int) -> bytes:
        """Read audio chunk."""
        if not self._is_recording or not self._stream:
            raise RuntimeError("Microphone not recording")

        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        frames = int(chunk_size / (self._channels * self._pyaudio.get_sample_size(self._pyaudio.paInt16)))
        try:
            data: bytes = await asyncio.to_thread(
                self._stream.read,
                frames,
                exception_on_overflow=False,
            )
        except asyncio.CancelledError:
            raise

        return data

    def readable(self) -> bool:
        """Check if stream is readable."""
        return self._is_recording

    @property
    def is_available(self) -> bool:
        """Check if microphone is available (pyaudio installed)."""
        return self._pyaudio is not None

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @classmethod
    def list_devices(cls) -> list[dict[str, Any]]:
        """List available audio input devices."""
        devices = []
        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            try:
                for i in range(audio.get_device_count()):
                    info = audio.get_device_info_by_index(i)
                    if int(info.get("maxInputChannels", 0)) > 0:
                        devices.append(
                            {
                                "index": i,
                                "name": info.get("name", "Unknown"),
                                "channels": info.get("maxInputChannels", 0),
                            }
                        )
            finally:
                audio.terminate()
        except (ImportError, Exception) as e:
            logger.warning(f"Cannot list devices: {e}")
        return devices
