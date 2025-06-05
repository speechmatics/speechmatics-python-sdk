"""
Transport layer for Speechmatics RT WebSocket communication.

This module provides the Transport class that handles low-level WebSocket
communication with the Speechmatics RT API, including connection management,
message sending/receiving, and temporary token authentication.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from typing import Optional
from typing import Union
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

from .exceptions import ConnectionError
from .exceptions import TransportError
from .helpers import get_version
from .logging import get_logger

try:
    from websockets.asyncio.client import ClientConnection
    from websockets.asyncio.client import connect

    WS_HEADERS_KEY = "additional_headers"
except ImportError:
    from websockets.legacy.client import WebSocketClientProtocol
    from websockets.legacy.client import connect  # type: ignore

    WS_HEADERS_KEY = "extra_headers"


class Transport:
    """
    WebSocket transport layer for Speechmatics RT API communication.

    This class handles low-level WebSocket communication with the Speechmatics
    RT API, including connection establishment, message sending/receiving, and
    connection lifecycle management.

    The transport supports both modern and legacy websockets library versions and
    handles SSL/TLS connections automatically for secure endpoints.

    Args:
        url: WebSocket URL for the Speechmatics RT API.
        api_key: API key or JWT token for authentication.
        request_id: Optional unique identifier for request tracking. Generated
                   automatically if not provided.

    Attributes:
        url: The WebSocket URL.
        api_key: The authentication token.
        request_id: Unique identifier for this transport instance.

    Examples:
        Basic usage:
            >>> transport = Transport(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-api-key"
            ... )
            >>> await transport.connect()
            >>> await transport.send_message({"message": "test"})
            >>> response = await transport.receive_message()
            >>> await transport.close()
    """

    def __init__(self, url: str, api_key: str, request_id: Optional[str] = None) -> None:
        """
        Initialize the transport with connection parameters.

        Args:
            url: WebSocket URL for the Speechmatics RT API.
            api_key: API key or JWT token for authentication.
            request_id: Optional unique identifier for request tracking.
                       Generated automatically if not provided.
        """
        self._url = url
        self._api_key = api_key
        self._request_id = request_id or str(uuid.uuid4())
        self._websocket: Optional[Union[ClientConnection, WebSocketClientProtocol]] = None
        self._closed = False
        self._logger = get_logger(__name__, self._request_id)

    async def connect(self, ws_headers: Optional[dict] = None) -> None:
        """
        Establish WebSocket connection to the Speechmatics RT API.

        This method establishes a WebSocket connection using the configured URL
        and authentication credentials. It handles SSL/TLS for secure connections
        and includes proper timeout handling.

        Args:
            ws_headers: Optional additional HTTP headers to include in the WebSocket
                    handshake request.

        Raises:
            ConnectionError: If the connection cannot be established within the
                           specified timeout or if the server rejects the connection.

        Examples:
            >>> await transport.connect()
            >>> # Connection is now established and ready for communication

            >>> # With additional headers
            >>> await transport.connect(ws_headers={"User-Agent": "MyApp/1.0"})
        """
        if self._websocket or self._closed:
            return

        url_with_params = self._prepare_url()
        ws_headers = self._prepare_headers(ws_headers)

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
            return json.loads(raw_message)  # type: ignore[no-any-return]
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

        parsed = urlparse(self._url)
        query_params = dict(parse_qsl(parsed.query))
        query_params["sm-sdk"] = f"python-{get_version()}"

        updated_query = urlencode(query_params)
        return urlunparse(parsed._replace(query=updated_query))

    def _prepare_headers(self, extra_headers: Optional[dict] = None) -> dict:
        """
        Prepare HTTP headers for the WebSocket handshake with authentication.

        This method constructs the headers dictionary including authentication
        headers using the provided API key or JWT token.

        Args:
            extra_headers: Optional additional headers to include.

        Returns:
            Complete headers dictionary ready for WebSocket handshake.
        """
        headers = {"X-Request-Id": self._request_id}

        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        if extra_headers:
            headers.update(extra_headers)

        return headers
