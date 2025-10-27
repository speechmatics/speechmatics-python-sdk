"""
Asynchronous client for Speechmatics TTS transcription.

This module provides the main AsyncClient class that handles text-to-speech
using the Speechmatics TTS API.
"""

from __future__ import annotations

import os
import uuid
from typing import Any
from typing import Optional

import aiohttp

from ._auth import AuthBase
from ._auth import StaticKeyAuth
from ._logging import get_logger
from ._models import ConnectionConfig
from ._models import OutputFormat
from ._models import Voice
from ._transport import Transport


class AsyncClient:
    """
    Asynchronous client for Speechmatics TTS transcription.

    This client provides a full-featured async interface to the Speechmatics TTS API,
    supporting job submission, monitoring, and result retrieval with comprehensive
    error management. It properly implements the Speechmatics REST API.

    The client handles the complete batch transcription workflow:
    1. Job submission with audio file and configuration
    2. Job status monitoring (with polling helpers)
    3. Result retrieval when transcription is complete
    4. Proper cleanup and error handling

    Args:
        auth: Authentication instance. If not provided, uses StaticKeyAuth
              with api_key parameter or SPEECHMATICS_API_KEY environment variable.
        api_key: Speechmatics API key (used only if auth not provided).
        url: REST API endpoint URL. If not provided, uses SPEECHMATICS_TTS_URL
             environment variable or defaults to production endpoint.
        conn_config: Complete connection configuration object. If provided, overrides
               other parameters.

    Raises:
        ConfigurationError: If required configuration is missing or invalid.

    Examples:
        Basic usage:
            >>> async with AsyncClient(api_key="your-key") as client:
            ...     response = await client.generate(text="Hello world")
            ...     print(response)

        With JWT authentication:
            >>> from speechmatics.batch import JWTAuth
            >>> auth = JWTAuth("your-api-key", ttl=3600)
            >>> async with AsyncClient(auth=auth) as client:
            ...     # Use client with JWT auth
            ...     pass
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        """
        Initialize the AsyncClient.

        Args:
            auth: Authentication method, it can be StaticKeyAuth or JWTAuth.
                If None, creates StaticKeyAuth with the api_key.
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: REST API endpoint URL. If None, uses SPEECHMATICS_TTS_URL env var
                 or defaults to production endpoint.
            conn_config: Complete connection configuration.

        Raises:
            ConfigurationError: If auth is None and API key is not provided/found.
        """
        self._auth = auth or StaticKeyAuth(api_key)
        self._url = url or os.environ.get("SPEECHMATICS_TTS_URL") or "https://preview.tts.speechmatics.com"
        self._conn_config = conn_config or ConnectionConfig()
        self._request_id = str(uuid.uuid4())
        self._transport = Transport(self._url, self._conn_config, self._auth, self._request_id)

        self._logger = get_logger(__name__)
        self._logger.debug("AsyncClient initialized (request_id=%s, url=%s)", self._request_id, self._url)

    async def __aenter__(self) -> AsyncClient:
        """
        Async context manager entry.

        Returns:
            Self for use in async with statements.

        Examples:
            >>> async with AsyncClient(api_key="key") as client:
            ...     response = await client.generate(text="Hello world")
            ...     print(response)
        """
        return self

    async def generate(
        self,
        *,
        text: str = "",
        voice: Voice = Voice.SARAH,
        output_format: OutputFormat = OutputFormat.RAW_PCM_16000,
    ) -> aiohttp.ClientResponse:
        """
        Convert text to speech audio.

        Args:
            text: Text to convert to speech.
            voice: Voice ID to use for synthesis (e.g., "en-US-neural-1").
            output_format: Audio format ("wav", "mp3", "ogg").

        Returns:
            Audio data as bytes.

        Raises:
            AuthenticationError: If API key is invalid.
            TransportError: If synthesis fails.

        Examples:
            >>> response = await client.generate(text="Hello world")
            >>> audio_data = await response.read()
            >>> with open("output.wav", "wb") as f:
            ...     f.write(audio_data)
        """
        # Prepare synthesis request
        request_data = {
            "text": text,
        }

        response = await self._transport.post(
            f"/generate/{voice.value}?output_format={output_format.value}", json_data=request_data
        )
        return response

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Async context manager exit with automatic cleanup.

        Ensures all resources are properly cleaned up when exiting the
        async context manager, including closing HTTP connections.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        await self.close()

    async def close(self) -> None:
        """
        Close the client and cleanup all resources.

        This method ensures proper cleanup of all client resources including
        closing HTTP connections and sessions.

        This method is safe to call multiple times and will handle cleanup
        gracefully even if errors occur during the process.

        Examples:
            >>> client = AsyncClient(api_key="key")
            >>> try:
            ...     result = await client.generate(text="Hello world")
            >>> finally:
            ...     await client.close()
        """
        try:
            await self._transport.close()
        except Exception:
            pass  # Best effort cleanup
