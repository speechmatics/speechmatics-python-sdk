"""
Models for the Speechmatics TTS SDK.

This module contains all data models, enums, and configuration classes used
throughout the Speechmatics TTS SDK. These models
provide type-safe interfaces for configuration, job management, and
result handling based on the official Speechmatics API schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass
class ConnectionConfig:
    """
    Configuration for HTTP connection parameters.

    This class defines connection-related settings and timeouts.

    Attributes:
        connect_timeout: Timeout in seconds for connection establishment.
        operation_timeout: Default timeout for API operations.
    """

    connect_timeout: float = 30.0
    operation_timeout: float = 300.0


class OutputFormat(str, Enum):
    """
    Output format for the generated audio.

    Attributes:
        wav_16000: WAV audio format with 16kHz sample rate.
        raw_pcm_16000: Raw audio format with 16kHz sample rate.
    """

    WAV_16000 = "wav_16000"
    RAW_PCM_16000 = "pcm_16000"


class Voice(str, Enum):
    """
    Voice ID for the generated audio.

    Attributes:
        sarah: English (UK) female voice.
        theo: English (UK) male voice.
        megan: English (UK) female voice.
    """

    SARAH = "sarah"
    THEO = "theo"
    MEGAN = "megan"
