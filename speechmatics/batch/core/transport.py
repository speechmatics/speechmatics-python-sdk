"""
Transport layer for Speechmatics Batch HTTP communication.

This module provides the Transport class that handles low-level HTTP
communication with the Speechmatics Batch API, including connection management,
request/response handling, and authentication.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import aiohttp

from .exceptions import AuthenticationError, ConnectionError, TransportError
from .helpers import get_version
from .logging import get_logger
from .models import ConnectionConfig


class Transport:
    """
    HTTP transport layer for Speechmatics Batch API communication.

    This class handles all low-level HTTP communication with the Speechmatics
    Batch API, including connection management, request serialization,
    authentication, and response handling.

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
            ...     url="https://asr.api.speechmatics.com/v2",
            ...     api_key="your-api-key"
            ... )
            >>> transport = Transport(config)
            >>> response = await transport.get("/jobs")
            >>> await transport.close()
    """

    def __init__(self, config: ConnectionConfig, request_id: str | None = None) -> None:
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
        self._session: aiohttp.ClientSession | None = None
        self._closed = False
        self._logger = get_logger(__name__, self._request_id)

    async def __aenter__(self) -> Transport:
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with automatic cleanup."""
        await self.close()

    async def get(
        self, path: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> dict[str, Any]:
        """
        Send GET request to the API.

        Args:
            path: API endpoint path (e.g., "/jobs")
            params: Optional query parameters
            timeout: Optional request timeout

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return await self._request("GET", path, params=params, timeout=timeout)

    async def post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        multipart_data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Send POST request to the API.

        Args:
            path: API endpoint path
            json_data: Optional JSON data for request body
            multipart_data: Optional multipart form data
            timeout: Optional request timeout

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return await self._request("POST", path, json_data=json_data, multipart_data=multipart_data, timeout=timeout)

    async def delete(self, path: str, timeout: float | None = None) -> dict[str, Any]:
        """
        Send DELETE request to the API.

        Args:
            path: API endpoint path
            timeout: Optional request timeout

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return await self._request("DELETE", path, timeout=timeout)

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

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None and not self._closed:
            timeout = aiohttp.ClientTimeout(total=self._config.operation_timeout, connect=self._config.connect_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        multipart_data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
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
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
            TransportError: For other transport errors
        """
        await self._ensure_session()

        if self._session is None:
            raise ConnectionError("Failed to create HTTP session")

        url = f"{self._config.url.rstrip('/')}{path}"
        headers = self._prepare_headers()

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
                # Create proper multipart/form-data
                form_data = aiohttp.FormData()
                for key, value in multipart_data.items():
                    if isinstance(value, tuple) and len(value) == 3:
                        # File data: (filename, file_data, content_type)
                        filename, file_data, content_type = value
                        form_data.add_field(key, file_data, filename=filename, content_type=content_type)
                    else:
                        # Regular form field
                        if isinstance(value, dict):
                            import json

                            value = json.dumps(value)
                        form_data.add_field(key, value)
                kwargs["data"] = form_data

            async with self._session.request(method, url, **kwargs) as response:
                return await self._handle_response(response)

        except asyncio.TimeoutError:
            self._logger.error("request_timeout", method=method, path=path)
            raise TransportError(f"Request timeout for {method} {path}") from None
        except aiohttp.ClientError as e:
            self._logger.error("request_failed", method=method, path=path, error=str(e))
            raise ConnectionError(f"Request failed: {e}") from e
        except Exception as e:
            self._logger.error("unexpected_error", method=method, path=path, error=str(e))
            raise TransportError(f"Unexpected error: {e}") from e

    def _prepare_headers(self) -> dict[str, str]:
        """
        Prepare HTTP headers for requests.

        Returns:
            Headers dictionary with authentication and tracking info
        """
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "User-Agent": f"speechmatics-python-batch/{get_version()}",
            "X-Request-Id": self._request_id,
        }
        return headers

    async def _handle_response(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        """
        Handle HTTP response and extract JSON data.

        Args:
            response: HTTP response object

        Returns:
            JSON response as dictionary

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
                self._logger.error("http_error", status=response.status, reason=response.reason, body=error_text)
                raise TransportError(f"HTTP {response.status}: {response.reason} - {error_text}")

            # Try to parse JSON response
            if (
                response.content_type == "application/json"
                or response.content_type == "application/vnd.speechmatics.v2+json"
            ):
                return await response.json()
            else:
                # For non-JSON responses (like plain text transcripts)
                text = await response.text()
                return {"content": text, "content_type": response.content_type}

        except aiohttp.ContentTypeError as e:
            self._logger.error("json_parse_error", error=str(e))
            raise TransportError(f"Failed to parse response: {e}") from e
        except Exception as e:
            self._logger.error("response_handling_error", error=str(e))
            raise TransportError(f"Error handling response: {e}") from e
