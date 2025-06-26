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

from ._auth import AuthBase
from ._exceptions import ConnectionError
from ._exceptions import TimeoutError
from ._exceptions import TransportError
from ._logging import get_logger
from ._models import ConnectionConfig
from ._utils.version import get_version

try:
    # Try to import from new websockets >=13.0
    from websockets.asyncio.client import ClientConnection
    from websockets.asyncio.client import connect

    WS_HEADERS_KEY = "additional_headers"
except ImportError:
    # Fall back to legacy websockets
    from websockets.legacy.client import WebSocketClientProtocol
    from websockets.legacy.client import connect  # type: ignore

    WS_HEADERS_KEY = "extra_headers"


class Transport:
    """
    WebSocket transport layer for Speechmatics RT API communication.

    This class handles all low-level WebSocket communication with the Speechmatics
    RT API, including connection establishment, message serialization/deserialization,
    authentication, and connection lifecycle management.

    The transport supports both modern and legacy websockets library versions and
    handles SSL/TLS connections automatically for secure endpoints.

    Args:
        url: The WebSocket URL to connect to.
        config: Connection configuration and timeouts.
        auth: Authentication mechanism for the connection.
        request_id: Optional unique identifier for request tracking.
            Generated automatically if not provided.
    """

    def __init__(
        self,
        url: str,
        conn_config: ConnectionConfig,
        auth: AuthBase,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the transport with connection configuration.

        Args:
            url: The base URL for the Speechmatics RT API.
            conn_config: Connection configuration object containing timeouts, max_size,
                and other websocket connection parameters.
            auth: Authentication object containing credentials.
            request_id: Optional unique identifier for request tracking.
                Generated automatically if not provided.
        """
        self._url = url
        self._auth = auth
        self._conn_config = conn_config
        self._request_id = request_id or str(uuid.uuid4())
        self._websocket: Optional[Union[ClientConnection, WebSocketClientProtocol]] = None
        self._closed = False
        self._logger = get_logger(__name__)

        self._logger.debug("Transport initialized (request_id=%s, url=%s)", self._request_id, self._url)

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
        self._logger.debug("Connecting to WebSocket: %s", url_with_params)

        if ws_headers is None:
            ws_headers = {}
        ws_headers.update(await self._auth.get_auth_headers())

        try:
            ws_kwargs: dict = {
                WS_HEADERS_KEY: ws_headers,
                **self._conn_config.to_dict(),
            }

            self._websocket = await connect(
                url_with_params,
                **ws_kwargs,
            )
        except asyncio.TimeoutError as e:
            self._logger.error("WebSocket connection timeout: %s", e)
            raise TimeoutError(f"WebSocket connection timeout: {str(e)}")
        except Exception as e:
            self._logger.error("WebSocket connection error: %s", e)
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
            if isinstance(message, dict):
                data = json.dumps(message)
            else:
                data = message  # assume bytes
            await self._websocket.send(data)
        except Exception as e:
            self._logger.error("Send message failed: %s", e)
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
            parsed_message = json.loads(raw_message)
            self._logger.debug("Received message=%s", parsed_message)
            return parsed_message  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            self._logger.error("Invalid JSON received: %s", e)
            raise TransportError(f"Invalid JSON received: {e}")
        except Exception as e:
            self._logger.error("Receive message failed: %s", e)
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
            self._logger.debug("Closing WebSocket connection")
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
        query_params["sm-sdk"] = f"python-rt-sdk-v{get_version()}"

        updated_query = urlencode(query_params)
        return urlunparse(parsed._replace(query=updated_query))
