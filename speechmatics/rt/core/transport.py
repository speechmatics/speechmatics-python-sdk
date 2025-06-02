"""
Transport layer for Speechmatics RT WebSocket communication.

This module provides the Transport class that handles low-level WebSocket
communication with the Speechmatics RT API, including connection management,
message sending/receiving, and temporary token authentication.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any
from typing import Optional
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

import aiohttp

from .exceptions import ConnectionError
from .exceptions import TransportError
from .helpers import get_version
from .logging import get_logger
from .models import ConnectionConfig

try:
    from websockets.asyncio.client import ClientConnection
    from websockets.asyncio.client import connect

    WS_HEADERS_KEY = "additional_headers"
except ImportError:
    from websockets.legacy.client import WebSocketClientProtocol as ClientConnection  # type: ignore
    from websockets.legacy.client import connect  # type: ignore

    WS_HEADERS_KEY = "extra_headers"


class Transport:
    """
    WebSocket transport layer for Speechmatics RT API communication.

    This class handles all low-level WebSocket communication with the Speechmatics
    RT API, including connection establishment, message serialization/deserialization,
    authentication (including temporary tokens), and connection lifecycle management.

    The transport supports both modern and legacy websockets library versions and
    handles SSL/TLS connections automatically for secure endpoints.

    Args:
        config: Connection configuration including URL, API key, and timeouts.
        request_id: Optional unique identifier for request tracking. Generated
                   automatically if not provided.

    Attributes:
        config: The connection configuration object.
        request_id: Unique identifier for this transport instance.

    Examples:
        Basic usage:
            >>> config = ConnectionConfig(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-api-key"
            ... )
            >>> transport = Transport(config)
            >>> await transport.connect()
            >>> await transport.send_message({"message": "test"})
            >>> response = await transport.receive_message()
            >>> await transport.close()
    """

    def __init__(self, config: ConnectionConfig, request_id: Optional[str] = None) -> None:
        """
        Initialize the transport with connection configuration.

        Args:
            config: Connection configuration object containing URL, API key,
                   timeouts, and other connection parameters.
            request_id: Optional unique identifier for request tracking.
                       Generated automatically if not provided.
        """
        self._config = config
        self._request_id = request_id or str(uuid.uuid4())
        self._websocket: Optional[ClientConnection] = None
        self._closed = False
        self._logger = get_logger(__name__, self._request_id)

    async def connect(self, ws_headers: Optional[dict] = None) -> None:
        """
        Establish WebSocket connection to the Speechmatics RT API.

        This method establishes a WebSocket connection using the configured URL
        and authentication credentials. It handles SSL/TLS for secure connections
        and includes proper timeout handling.

        If temporary token generation is enabled, it will automatically generate
        a temporary token using the main API key before establishing the connection.

        Args:
            ws_headers: Optional additional HTTP headers to include in the WebSocket
                    handshake request.

        Raises:
            ConnectionError: If the connection cannot be established within the
                           specified timeout or if the server rejects the connection.
            TransportError: If temporary token generation fails (when enabled).

        Examples:
            >>> await transport.connect()
            >>> # Connection is now established and ready for communication

            >>> # With additional headers
            >>> await transport.connect(ws_headers={"User-Agent": "MyApp/1.0"})
        """
        if self._websocket or self._closed:
            return

        url_with_params = self._prepare_url()
        ws_headers = await self._prepare_headers(ws_headers)

        try:
            ws_kwargs: dict = {
                WS_HEADERS_KEY: ws_headers,
            }

            self._websocket = await connect(
                url_with_params,
                **ws_kwargs,
            )
        except asyncio.TimeoutError as e:
            self._logger.error("connection_timeout", error=str(e))
            raise TimeoutError(f"WebSocket connection timeout: {str(e)}")
        except Exception as e:
            self._logger.error("connection_error", error=str(e))
            raise ConnectionError(f"WebSocket connection error: {str(e)}")

    async def send_message(self, message: Any) -> None:
        """
        Send a message through the WebSocket connection.

        This method handles different message types automatically:
        - Dictionaries and lists are serialized to JSON
        - Strings are sent as text messages
        - Bytes are sent as binary messages (typically for audio data)

        Args:
            message: The message to send. Can be a dictionary (for JSON messages),
                    string (for text messages), or bytes (for binary audio data).

        Raises:
            TransportError: If the message cannot be sent or if not connected.

        Examples:
            >>> # Send JSON message
            >>> await transport.send_message({"message": "StartRecognition", ...})

            >>> # Send audio data
            >>> audio_chunk = b""
            >>> await transport.send_message(audio_chunk)
        """
        if not self._websocket:
            raise TransportError("Not connected")

        try:
            if isinstance(message, (dict, list)):
                data = json.dumps(message)
            else:
                data = message

            await self._websocket.send(data)
        except Exception as e:
            self._logger.error("send_failed", error=str(e))
            raise TransportError(f"Send message failed: {e}")

    async def receive_message(self) -> dict:
        """
        Receive and parse a message from the WebSocket connection.

        This method waits for an incoming message from the server, automatically
        handles text/binary message types, and parses JSON payload.

        Returns:
            The parsed message as a dictionary. The structure depends on the
            message type received from the Speechmatics RT API.

        Raises:
            TransportError: If receiving the message fails, if the message contains
                          invalid JSON, or if not connected.

        Examples:
            >>> message = await transport.receive_message()
            >>> if message["message"] == "RecognitionStarted":
            ...     print("Recognition has started")
            >>> elif message["message"] == "AddTranscript":
            ...     transcript = message["metadata"]["transcript"]
            ...     print(f"Transcript: {transcript}")
        """
        if not self._websocket:
            raise TransportError("Not connected")

        try:
            raw_message = await self._websocket.recv()
            return json.loads(raw_message)
        except json.JSONDecodeError as e:
            self._logger.error("invalid_json_received", error=str(e))
            raise TransportError(f"Invalid JSON received: {e}")
        except Exception as e:
            self._logger.error("receive_failed", error=str(e))
            raise TransportError(f"Receive message failed: {e}")

    async def close(self) -> None:
        """
        Close the WebSocket connection and cleanup resources.

        This method gracefully closes the WebSocket connection and marks the
        transport as closed. It's safe to call multiple times and will handle
        cleanup gracefully even if errors occur.

        The method performs best-effort cleanup, suppressing any exceptions
        that occur during the close process to ensure the transport is properly
        marked as closed.

        Examples:
            >>> await transport.close()
            >>> # Connection is now closed and transport cannot be used
        """
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            finally:
                self._websocket = None
                self._closed = True

    @property
    def is_connected(self) -> bool:
        """
        Check if the WebSocket connection is currently active.

        Returns:
            True if the connection is active and ready for communication,
            False otherwise.

        Examples:
            >>> if transport.is_connected:
            ...     await transport.send_message(message)
        """
        return self._websocket is not None and self._closed is False

    def _prepare_url(self) -> str:
        """
        Prepare the WebSocket URL with SDK version information.

        This method adds the SDK version as a query parameter to the WebSocket
        URL for server-side tracking and debugging purposes.

        Returns:
            The complete WebSocket URL with SDK version parameter.
        """

        parsed = urlparse(self._config.url)
        query_params = dict(parse_qsl(parsed.query))
        query_params["sm-sdk"] = f"python-{get_version()}"

        updated_query = urlencode(query_params)
        return urlunparse(parsed._replace(query=updated_query))

    async def _prepare_headers(self, extra_headers: Optional[dict] = None) -> dict:
        """
        Prepare HTTP headers for the WebSocket handshake with authentication.

        This method constructs the headers dictionary including authentication
        headers. If temporary token generation is enabled, it will generate a
        temporary token using the API key. Otherwise, it uses the API key
        directly.

        Args:
            extra_headers: Optional additional headers to include.

        Returns:
            Complete headers dictionary ready for WebSocket handshake.

        Raises:
            TransportError: If temporary token generation fails.
        """
        headers = {}
        headers["X-Request-Id"] = self._request_id

        if self._config.api_key:
            if self._config.generate_temp_token:
                temp_token = await self._get_temp_token(self._config.api_key)
                headers["Authorization"] = f"Bearer {temp_token}"
            else:
                headers["Authorization"] = f"Bearer {self._config.api_key}"

        if extra_headers:
            headers.update(extra_headers)

        return headers

    async def _get_temp_token(self, api_key: str) -> str:
        """
        Generate a temporary token from the Speechmatics management platform API.

        This function exchanges a main API key for a short-lived temporary token
        that can be used for RT API authentication.

        The function makes an HTTP POST request to the management platform to
        generate the temporary token with appropriate metadata for tracking.

        Args:
            api_key: The main Speechmatics API key used to generate the temporary token.

        Returns:
            A temporary token string that can be used for RT API authentication.

        Raises:
            TransportError: If the temporary token generation fails due to network
                        errors, authentication failures, or server errors.

        Examples:
            >>> temp_token = _get_temp_token("your-main-api-key")
            >>> # Use temp_token for RT API authentication
            >>> headers = {"Authorization": f"Bearer {temp_token}"}

        Note:
            Temporary tokens have a 60-second TTL and are intended for single-use
            RT sessions. They should not be cached or reused across sessions.
        """

        version = get_version()
        mp_api_url = os.getenv("SM_MANAGEMENT_PLATFORM_URL", "https://mp.speechmatics.com")
        endpoint = f"{mp_api_url}/v1/api_keys"

        params = {"type": "rt", "sm-sdk": f"python-{version}"}
        endpoint_with_params = f"{endpoint}?{urlencode(params)}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint_with_params,
                    json={"ttl": 60},
                    headers=headers,
                    timeout=10,
                ) as response:
                    if response.status != 201:
                        error_content = await response.text()
                        raise TransportError(
                            f"Failed to get temporary token: HTTP {response.status}: {response.reason} - {error_content}"
                        )
                    key_object = await response.json()
                    return key_object["key_value"]
        except Exception as e:
            self._logger.error("temp_token_fetch_failed", error=str(e))
            raise TransportError(f"Failed to get temporary token: {e}") from e
