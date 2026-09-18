"""
Blocking transport layer for Speechmatics Batch HTTP communication.

This module provides the SyncTransport class, the blocking counterpart of
``Transport``. It exposes the same request interface, so both clients can share
all request construction and response parsing logic.
"""

from __future__ import annotations

import json as _json
import sys
import uuid
from typing import Any
from typing import Optional

import httpx

from ._auth import AuthBase
from ._exceptions import AuthenticationError
from ._exceptions import ConnectionError
from ._exceptions import TransportError
from ._helpers import get_version
from ._logging import get_logger
from ._models import ConnectionConfig

_JSON_CONTENT_TYPES = ("application/json", "application/vnd.speechmatics.v2+json")


class SyncTransport:
    """
    Blocking HTTP transport layer for Speechmatics Batch API communication.

    This class handles all low-level HTTP communication with the Speechmatics
    Batch API without requiring an event loop, including connection pooling,
    request serialization, authentication, and response handling.

    Args:
        url: Base URL for the Speechmatics Batch API.
        conn_config: Connection configuration including timeouts.
        auth: Authentication instance for handling credentials.
        request_id: Optional unique identifier for request tracking. Generated
                   automatically if not provided.

    Examples:
        Basic usage:
            >>> from ._auth import StaticKeyAuth
            >>> transport = SyncTransport(
            ...     "https://asr.api.speechmatics.com/v2",
            ...     ConnectionConfig(),
            ...     StaticKeyAuth("your-api-key"),
            ... )
            >>> response = transport.get("/jobs")
            >>> transport.close()
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
            url: Base URL for the Speechmatics Batch API.
            conn_config: Connection configuration object containing connection parameters.
            auth: Authentication instance for handling credentials.
            request_id: Optional unique identifier for request tracking.
                Generated automatically if not provided.
        """
        self._url = url
        self._conn_config = conn_config
        self._auth = auth
        self._request_id = request_id or str(uuid.uuid4())
        self._client: Optional[httpx.Client] = None
        self._closed = False
        self._logger = get_logger(__name__)

        self._logger.debug("SyncTransport initialized (request_id=%s, url=%s)", self._request_id, self._url)

    def __enter__(self) -> SyncTransport:
        """Context manager entry."""
        self._ensure_client()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with automatic cleanup."""
        self.close()

    def get(
        self, path: str, params: Optional[dict[str, Any]] = None, timeout: Optional[float] = None
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
        return self._request("GET", path, params=params, timeout=timeout)

    def post(
        self,
        path: str,
        json_data: Optional[dict[str, Any]] = None,
        multipart_data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        extra_headers: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send POST request to the API.

        Args:
            path: API endpoint path
            json_data: Optional JSON data for request body
            multipart_data: Optional multipart form data
            timeout: Optional request timeout
            extra_headers: Optional additional headers to include in the request
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return self._request(
            "POST",
            path,
            json_data=json_data,
            multipart_data=multipart_data,
            timeout=timeout,
            extra_headers=extra_headers,
            params=params,
        )

    def delete(
        self, path: str, timeout: Optional[float] = None, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Send DELETE request to the API.

        Args:
            path: API endpoint path
            timeout: Optional request timeout
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            TransportError: If request fails
        """
        return self._request("DELETE", path, timeout=timeout, params=params)

    def close(self) -> None:
        """
        Close the HTTP client and cleanup resources.

        This method gracefully closes the HTTP client and marks the
        transport as closed. It's safe to call multiple times.
        """
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._client = None
                self._closed = True

    @property
    def is_connected(self) -> bool:
        """
        Check if the transport has an active client.

        Returns:
            True if the client is active, False otherwise
        """
        return self._client is not None and not self._closed

    def _ensure_client(self) -> None:
        """Ensure the HTTP client is created."""
        if self._client is None and not self._closed:
            self._logger.debug(
                "Creating HTTP client (connect_timeout=%.1fs, operation_timeout=%.1fs)",
                self._conn_config.connect_timeout,
                self._conn_config.operation_timeout,
            )
            timeout = httpx.Timeout(
                self._conn_config.operation_timeout,
                connect=self._conn_config.connect_timeout,
            )
            self._client = httpx.Client(timeout=timeout)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        multipart_data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        extra_headers: Optional[dict[str, Any]] = None,
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
            extra_headers: Optional additional headers to include in the request

        Returns:
            JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
            TransportError: For other transport errors
        """
        self._ensure_client()

        if self._client is None:
            raise ConnectionError("Failed to create HTTP client")

        url = f"{self._url.rstrip('/')}{path}"
        headers = self._prepare_headers()
        if extra_headers:
            for k, v in extra_headers.items():
                headers[k] = _json.dumps(v) if isinstance(v, dict) else v

        self._logger.debug(
            "Sending HTTP request %s %s (json=%s, multipart=%s)",
            method,
            url,
            json_data is not None,
            multipart_data is not None,
        )

        kwargs: dict[str, Any] = {
            "headers": headers,
            "params": params,
        }

        if timeout:
            kwargs["timeout"] = httpx.Timeout(timeout)

        if json_data:
            kwargs["json"] = json_data
        elif multipart_data:
            kwargs["files"] = self._encode_multipart(multipart_data)

        try:
            response = self._client.request(method, url, **kwargs)
            return self._handle_response(response)

        except httpx.TimeoutException:
            self._logger.error(
                "Request timeout %s %s (timeout=%.1fs)",
                method,
                path,
                timeout or self._conn_config.operation_timeout,
            )
            raise TransportError(f"Request timeout for {method} {path}") from None
        except (AuthenticationError, TransportError):
            raise
        except httpx.HTTPError as e:
            self._logger.error("Request failed %s %s: %s", method, path, e)
            raise ConnectionError(f"Request failed: {e}") from e
        except Exception as e:
            self._logger.error("Unexpected error %s %s: %s", method, path, e)
            raise TransportError(f"Unexpected error: {e}") from e

    @staticmethod
    def _encode_multipart(multipart_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert shared multipart fields into httpx's files mapping.

        Every field goes through ``files`` (non-file fields with a None
        filename) because httpx would otherwise url-encode a body that has no
        file in it, and the API requires multipart for fetch_data submissions.
        """
        files: dict[str, Any] = {}
        for key, value in multipart_data.items():
            if isinstance(value, tuple) and len(value) == 3:
                files[key] = value
            elif isinstance(value, dict):
                files[key] = (None, _json.dumps(value), "application/json")
            else:
                files[key] = (None, value)
        return files

    def _prepare_headers(self) -> dict[str, str]:
        """
        Prepare HTTP headers for requests.

        Returns:
            Headers dictionary with authentication and tracking info
        """
        auth_headers = self._auth.get_auth_headers_sync()
        auth_headers[
            "User-Agent"
        ] = f"speechmatics-batch-v{get_version()} python/{sys.version_info.major}.{sys.version_info.minor}"

        if self._request_id:
            auth_headers["X-Request-Id"] = self._request_id

        return auth_headers

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
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
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key - authentication failed")
        elif response.status_code == 403:
            raise AuthenticationError("Access forbidden - check API key permissions")
        elif response.status_code >= 400:
            self._logger.error("HTTP error %d %s: %s", response.status_code, response.reason_phrase, response.text)
            raise TransportError(
                f"HTTP {response.status_code}: {response.reason_phrase} - {response.text}",
                status_code=response.status_code,
            )

        content_type = response.headers.get("content-type", "").split(";")[0].strip()

        if content_type in _JSON_CONTENT_TYPES:
            try:
                return dict(response.json())
            except ValueError as e:
                self._logger.error("Failed to parse JSON response: %s", e)
                raise TransportError(f"Failed to parse response: {e}") from e

        # For non-JSON responses (like plain text transcripts)
        self._logger.debug("Parsing text response (content_type=%s)", content_type)
        return {"content": response.text, "content_type": content_type}
