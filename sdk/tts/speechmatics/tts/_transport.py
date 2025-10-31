"""
Transport layer for Speechmatics Batch HTTP communication.

This module provides the Transport class that handles low-level HTTP
communication with the Speechmatics Batch API, including connection management,
request/response handling, and authentication.
"""

from __future__ import annotations

import asyncio
import io
import sys
import uuid
from typing import Any
from typing import Optional

import aiohttp

from ._auth import AuthBase
from ._exceptions import AuthenticationError
from ._exceptions import ConnectionError
from ._exceptions import TransportError
from ._helpers import get_version
from ._logging import get_logger
from ._models import ConnectionConfig


class Transport:
    """
    HTTP transport layer for Speechmatics Batch API communication.

    This class handles all low-level HTTP communication with the Speechmatics
    Batch API, including connection management, request serialization,
    authentication, and response handling.

    Args:
        url: Base URL for the Speechmatics Batch API.
        conn_config: Connection configuration including URL and timeouts.
        auth: Authentication instance for handling credentials.
        request_id: Optional unique identifier for request tracking. Generated
                   automatically if not provided.

    Attributes:
        conn_config: The connection configuration object.
        request_id: Unique identifier for this transport instance.

    Examples:
        Basic usage:
            >>> from ._auth import StaticKeyAuth
            >>> conn_config = ConnectionConfig()
            >>> auth = StaticKeyAuth("your-api-key")
            >>> transport = Transport(conn_config, auth)
            >>> response = await transport.get("/jobs")
            >>> await transport.close()
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
            conn_config: Connection configuration object containing connection parameters.
            auth: Authentication instance for handling credentials.
            request_id: Optional unique identifier for request tracking.
                Generated automatically if not provided.
        """
        self._url = url
        self._conn_config = conn_config
        self._auth = auth
        self._request_id = request_id or str(uuid.uuid4())
        self._session: Optional[aiohttp.ClientSession] = None
        self._closed = False
        self._logger = get_logger(__name__)

        self._logger.debug("Transport initialized (request_id=%s, url=%s)", self._request_id, self._url)

    async def __aenter__(self) -> Transport:
        """Async context manager entry."""
        self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with automatic cleanup."""
        await self.close()

    async def post(
        self,
        path: str,
        json_data: Optional[dict[str, Any]] = None,
        multipart_data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> aiohttp.ClientResponse:
        """
        Send POST request to the API.

        Args:
            path: API endpoint path
            json_data: Optional JSON data for request body
            multipart_data: Optional multipart form data
            timeout: Optional request timeout

        Returns:
            HTTP response object

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return await self._request("POST", path, json_data=json_data, multipart_data=multipart_data, timeout=timeout)

    async def close(self) -> None:
        """
        Close the HTTP session and cleanup resources.

        This method gracefully closes the HTTP session and marks the
        transport as closed. It's safe to call multiple times.
        """
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._session = None
                self._closed = True

    @property
    def is_connected(self) -> bool:
        """
        Check if the transport has an active session.

        Returns:
            True if session is active, False otherwise
        """
        return self._session is not None and not self._closed

    def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None and not self._closed:
            self._logger.debug(
                "Creating HTTP session (connect_timeout=%.1fs, operation_timeout=%.1fs)",
                self._conn_config.connect_timeout,
                self._conn_config.operation_timeout,
            )
            timeout = aiohttp.ClientTimeout(
                total=self._conn_config.operation_timeout,
                connect=self._conn_config.connect_timeout,
            )
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        multipart_data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> aiohttp.ClientResponse:
        """
        Send HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API endpoint path
            params: Optional query parameters
            json_data: Optional JSON data for request body
            multipart_data: Optional multipart form data
            timeout: Optional request timeout

        Returns:
            HTTP response object

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
            TransportError: For other transport errors
        """
        self._ensure_session()

        if self._session is None:
            raise ConnectionError("Failed to create HTTP session")

        url = f"{self._url.rstrip('/')}{path}"
        headers = await self._prepare_headers()

        self._logger.debug(
            "Sending HTTP request %s %s (json=%s, multipart=%s)",
            method,
            url,
            json_data is not None,
            multipart_data is not None,
        )

        # Override timeout if specified
        if timeout:
            request_timeout = aiohttp.ClientTimeout(total=timeout)
        else:
            request_timeout = None

        try:
            # Prepare request arguments
            kwargs: dict[str, Any] = {
                "headers": headers,
                "params": params,
                "timeout": request_timeout,
            }

            if json_data:
                kwargs["json"] = json_data
            elif multipart_data:
                # Force multipart encoding even when no files are present (for fetch_data support)
                form_data = aiohttp.FormData(default_to_multipart=True)
                for key, value in multipart_data.items():
                    if isinstance(value, tuple) and len(value) == 3:
                        # File data: (filename, file_data, content_type)
                        filename, file_data, content_type = value
                        # aiohttp cannot serialize io.BytesIO directly; convert to bytes
                        if isinstance(file_data, io.BytesIO):
                            file_payload = file_data.getvalue()
                        else:
                            file_payload = file_data
                        form_data.add_field(key, file_payload, filename=filename, content_type=content_type)
                    else:
                        # Regular form field
                        if isinstance(value, dict):
                            import json

                            value = json.dumps(value)
                        form_data.add_field(key, value)
                kwargs["data"] = form_data

            response = await self._session.request(method, url, **kwargs)
            try:
                return await self._handle_response(response)
            except Exception:
                response.close()
                raise

        except asyncio.TimeoutError:
            self._logger.error(
                "Request timeout %s %s (timeout=%.1fs)", method, path, self._conn_config.operation_timeout
            )
            raise TransportError(f"Request timeout for {method} {path}") from None
        except aiohttp.ClientError as e:
            self._logger.error("Request failed %s %s: %s", method, path, e)
            raise ConnectionError(f"Request failed: {e}") from e
        except Exception as e:
            self._logger.error("Unexpected error %s %s: %s", method, path, e)
            raise TransportError(f"Unexpected error: {e}") from e

    async def _prepare_headers(self) -> dict[str, str]:
        """
        Prepare HTTP headers for requests.

        Returns:
            Headers dictionary with authentication and tracking info
        """
        auth_headers = await self._auth.get_auth_headers()
        auth_headers["User-Agent"] = (
            f"speechmatics-batch-v{get_version()} python/{sys.version_info.major}.{sys.version_info.minor}"
        )

        if self._request_id:
            auth_headers["X-Request-Id"] = self._request_id

        return auth_headers

    async def _handle_response(self, response: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        """
        Handle HTTP response and extract JSON data.

        Args:
            response: HTTP response object

        Returns:
            HTTP response object

        Raises:
            AuthenticationError: For 401/403 responses
            TransportError: For other error responses
        """
        try:
            if response.status == 401:
                raise AuthenticationError("Invalid API key - authentication failed")
            elif response.status == 403:
                raise AuthenticationError("Access forbidden - check API key permissions")
            elif response.status >= 400:
                error_text = await response.text()
                self._logger.error("HTTP error %d %s: %s", response.status, response.reason, error_text)
                raise TransportError(f"HTTP {response.status}: {response.reason} - {error_text}")
            return response

        except aiohttp.ContentTypeError as e:
            self._logger.error("Failed to parse JSON response: %s", e)
            raise TransportError(f"Failed to parse response: {e}") from e
        except Exception as e:
            self._logger.error("Error handling response: %s", e)
            raise TransportError(f"Error handling response: {e}") from e
