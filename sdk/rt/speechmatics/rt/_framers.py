"""
Audio framing utilities for Speechmatics Real-Time API.

This module provides framers that transform raw audio chunks into the appropriate
wire format for transmission to the Speechmatics RT API. Different framers support
different use cases:

- **RawFramer**: For single-stream audio, sends raw binary data directly
- **JsonB64Framer**: For multi-channel audio, wraps chunks in JSON with base64 encoding

The framer abstraction allows the same audio source to be used with different
transmission formats without changing the core audio handling logic.

Example:
    Single-stream with raw frames:
    >>> framer = RawFramer()
    >>> chunk = b"\\x00\\x01\\x02\\x03"  # Raw PCM audio
    >>> frame = framer.encode("channel_0", chunk)
    >>> # frame is the raw bytes, ready to send

    Multi-channel with JSON frames:
    >>> framer = JsonB64Framer()
    >>> left_chunk = b"\\x00\\x01\\x02\\x03"
    >>> frame = framer.encode("left", left_chunk)
    >>> # frame is {"message": "AddChannelAudio", "channel": "left", "data": "AAECAw=="}
"""

from __future__ import annotations

import base64
from typing import Any
from typing import Protocol

from ._models import ClientMessageType


class Framer(Protocol):
    """
    Protocol defining the interface for audio framers.

    Framers are responsible for transforming raw audio chunks into the
    appropriate format for transmission over WebSocket. All framers must
    implement the encode() and eos() methods.

    This protocol ensures that different framing strategies can be used
    interchangeably by the client code.
    """

    def encode(self, cid: str, chunk: bytes) -> bytes | dict:
        """
        Encode an audio chunk for transmission.

        Args:
            cid: Channel identifier (e.g., "0" for single stream, "left"/"right" for stereo)
            chunk: Raw audio data bytes

        Returns:
            Either raw bytes (for binary frames) or dict (for JSON frames)
        """
        ...

    def eos(self, cid: str, last_seq_no: int) -> bytes | dict | None:
        """
        Generate end-of-stream marker for a channel.

        Args:
            cid: Channel identifier
            last_seq_no: Sequence number of the last chunk

        Returns:
            End-of-stream frame, or None if not needed
        """
        ...


class RawFramer:
    """
    Framer for single-stream audio that sends raw binary data.

    This framer is used for traditional single-channel audio streaming where
    raw PCM audio bytes are sent directly over the WebSocket as binary frames.
    No additional metadata or encoding is applied.

    The channel ID is ignored since there's only one audio stream.

    Example:
        >>> framer = RawFramer()
        >>>
        >>> # Encoding audio chunks
        >>> audio_chunk = b"\\x00\\x01\\x02\\x03\\x04\\x05"  # Raw PCM data
        >>> frame = framer.encode("0", audio_chunk)
        >>> assert frame == audio_chunk  # No transformation applied
        >>>
        >>> # eos handling (not needed for raw frames)
        >>> eos_frame = framer.eos("0")
        >>> assert eos_frame is None
    """

    def encode(self, chunk: bytes) -> bytes:
        """
        Pass through raw audio bytes unchanged.

        Args:
            chunk: Raw audio bytes

        Returns:
            The same audio bytes, unchanged
        """
        return chunk

    def eos(self, last_seq_no: int) -> dict[str, Any]:
        """
        Return None as raw frames don't need eos markers.

        The Speechmatics RT API detects end-of-stream for raw audio
        based on the WebSocket connection state, not explicit markers.

        Args:
            last_seq_no: Sequence number of the last packet sent

        Returns:
            Always None
        """
        return {"message": "EndOfStream", "last_seq_no": last_seq_no}


class JsonB64Framer:
    """
    Framer for multi-channel audio using JSON messages with base64-encoded data.

    This framer is used when multiple audio streams need to be sent over a single
    WebSocket connection. Each audio chunk is base64-encoded and wrapped in a JSON
    message that includes the channel identifier.

    The JSON format allows the server to demultiplex the audio streams and process
    each channel independently while maintaining synchronization.

    Message Format:
        - Regular audio: {"message": "AddAudio", "channel": "left", "data": "base64data"}
        - eos marker: {"message": "AddChannelAudio", "channel": "left", "last_seq_no": 123}

    Example:
        >>> framer = JsonB64Framer()
        >>>
        >>> # Encoding audio for different channels
        >>> left_audio = b"\\x00\\x01\\x02\\x03"
        >>> left_frame = framer.encode("left", left_audio)
        >>> # left_frame = {
        >>> #     "message": "AddChannelAudio",
        >>> #     "channel": "left",
        >>> #     "data": "AAECAw=="
        >>> # }
        >>>
        >>> right_audio = b"\\x04\\x05\\x06\\x07"
        >>> right_frame = framer.encode("right", right_audio)
        >>> # right_frame = {
        >>> #     "message": "AddChannelAudio",
        >>> #     "channel": "right",
        >>> #     "data": "BAUGGB=="
        >>> # }
        >>>
        >>> # Sending eos for a channel
        >>> eos_frame = framer.eos("left")
        >>> # eos_frame = {
        >>> #     "message": "AddChannelAudio",
        >>> #     "channel": "left",
        >>> #     "last_seq_no": 123,
        >>> # }
    """

    def encode(self, cid: str, chunk: bytes) -> dict[str, Any]:
        """
        Encode audio chunk as base64 within a JSON message.

        The audio data is base64-encoded to allow binary data to be
        transmitted within a JSON text message. The channel ID is
        included to identify which stream this chunk belongs to.

        Args:
            cid: Channel identifier (e.g., "left", "right", "speaker1")
            chunk: Raw audio bytes to encode

        Returns:
            Dict with message type, channel ID, and base64-encoded audio

        Example:
            >>> framer = JsonB64Framer()
            >>> frame = framer.encode("channel_1", b"\\x00\\x01")
            >>> # Returns: {"message": "AddChannelAudio", "channel": "channel_1", "data": "AAE="}
        """
        return {
            "message": "AddChannelAudio",
            "channel": cid,
            "data": base64.b64encode(chunk).decode(),
        }

    def eos(self, cid: str, last_seq_no: int) -> dict[str, Any]:
        """
        Generate end-of-stream message for a specific channel.

        This creates a special JSON message that signals the end of audio
        for a particular channel. The server uses this to know when a
        channel has finished streaming.

        Args:
            cid: Channel identifier to mark as complete
            last_seq_no: Sequence number of the last packet sent

        Returns:
            Dict with eos marker for the specified channel

        Example:
            >>> framer = JsonB64Framer()
            >>> eos = framer.eos("left", 123)
            >>> # Returns: {"message": "EndOfChannel", "channel": "left", "last_seq_no": 123}
        """
        return {"message": ClientMessageType.END_OF_CHANNEL, "channel": cid, "last_seq_no": last_seq_no}
