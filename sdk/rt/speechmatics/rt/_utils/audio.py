from __future__ import annotations

import base64
from typing import Any

from .._models import ClientMessageType


def b64_encode_audio(chan_id: str, chunk: bytes) -> dict[str, Any]:
    """
    Encode audio chunk as base64 within a JSON message for multi-channel audio.

    Args:
        chan_id: Channel identifier (e.g., "left", "right")
        chunk: Raw audio bytes to encode

    Returns:
        Dict with message type, channel ID, and base64-encoded audio

    Example:
        >>> frame = encode_audio_chunk("channel_1", b"\\x00\\x01")
        >>> # Returns: {"message": "AddChannelAudio", "channel": "channel_1", "data": "AAE="}
    """
    return {
        "message": ClientMessageType.ADD_CHANNEL_AUDIO,
        "channel": chan_id,
        "data": base64.b64encode(chunk).decode(),
    }
