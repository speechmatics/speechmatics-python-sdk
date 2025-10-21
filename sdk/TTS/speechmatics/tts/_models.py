"""
Models for the Speechmatics TTS SDK.

This module contains all data models, enums, and configuration classes used
throughout the Speechmatics TTS SDK. These models
provide type-safe interfaces for configuration, job management, and
result handling based on the official Speechmatics API schema.
"""

from __future__ import annotations

from dataclasses import dataclass





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
