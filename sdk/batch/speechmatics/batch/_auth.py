from __future__ import annotations

import abc
import os
import threading
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import Optional

from ._exceptions import AuthenticationError

if TYPE_CHECKING:
    import asyncio


# Kept as an ABC so the public class keeps its metaclass, even though neither
# authentication method is abstract any more.
class AuthBase(abc.ABC):  # noqa: B024
    """
    Base class for authentication methods.

    Subclasses implement whichever of the two methods they need: async-only
    callers implement ``get_auth_headers``, blocking callers implement
    ``get_auth_headers_sync``, and most implementations provide both. Neither is
    abstract, so a subclass used with only one client does not have to write a
    method it will never call.
    """

    BASE_URL = "https://mp.speechmatics.com"

    async def get_auth_headers(self) -> dict[str, str]:
        """
        Get authentication headers asynchronously, for use with ``AsyncClient``.

        Returns:
            A dictionary of authentication headers.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support asynchronous authentication. "
            "Implement get_auth_headers() to use this auth method with AsyncClient."
        )

    def get_auth_headers_sync(self) -> dict[str, str]:
        """
        Get authentication headers synchronously, for use with ``Client``.

        Returns:
            A dictionary of authentication headers.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support synchronous authentication. "
            "Implement get_auth_headers_sync() to use this auth method with the sync Client."
        )


class StaticKeyAuth(AuthBase):
    """
    Authentication using a static API key.

    This is the traditional authentication method where the same
    API key is used for all requests.

    Args:
        api_key: The Speechmatics API key.

    Examples:
        >>> auth = StaticKeyAuth("your-api-key")
        >>> headers = await auth.get_auth_headers()
        >>> print(headers)
        {'Authorization': 'Bearer your-api-key'}
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")

        if not self._api_key:
            raise ValueError("API key required: provide api_key or set SPEECHMATICS_API_KEY")

    async def get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def get_auth_headers_sync(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}


class JWTAuth(AuthBase):
    """
    Authentication using temporary JWT tokens.

    Generates short-lived JWTs for enhanced security.

    Args:
        api_key: The main Speechmatics API key used to generate JWTs.
        ttl: Time-to-live for tokens between 60 and 86400 seconds.
            For security reasons, we suggest using the shortest TTL possible.
        region: Self-Service customers are restricted to "eu".
            Enterprise customers can use this to specify which region the temporary key should be enabled in.
        client_ref: Optional client reference for JWT token.
            This parameter must be used if the temporary keys are exposed to the end-user's client
            to prevent a user from accessing the data of a different user.
        mp_url: Optional management platform URL override.
        request_id: Optional request ID for debugging purposes.

    Examples:
        >>> auth = JWTAuth("your-api-key")
        >>> headers = await auth.get_auth_headers()
        >>> print(headers)
        {'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIs...'}
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        ttl: int = 60,
        region: Literal["eu", "usa", "au"] = "eu",
        client_ref: Optional[str] = None,
        mp_url: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self._api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")
        self._ttl = ttl
        self._region = region
        self._client_ref = client_ref
        self._request_id = request_id
        self._mp_url = mp_url or os.getenv("SM_MANAGEMENT_PLATFORM_URL", self.BASE_URL)

        if not self._api_key:
            raise ValueError(
                "API key required: please provide api_key or set SPEECHMATICS_API_KEY environment variable"
            )

        if not 60 <= self._ttl <= 86_400:
            raise ValueError("ttl must be between 60 and 86400 seconds")

        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0
        # The cache is reachable from an event loop and from threads, so both
        # paths guard it with _cache_lock and serialise minting separately.
        self._cache_lock = threading.Lock()
        self._sync_mint_lock = threading.Lock()
        # Created on first async use: on Python 3.9 asyncio.Lock() binds to the
        # current event loop, so building one outside a loop (as sync-only
        # callers do) raises RuntimeError.
        self._token_lock: Optional[asyncio.Lock] = None

    def _async_mint_lock(self) -> asyncio.Lock:
        """The asyncio lock serialising async minting, created inside the loop."""
        import asyncio

        if self._token_lock is None:
            self._token_lock = asyncio.Lock()
        return self._token_lock

    def _cached_headers(self) -> Optional[dict[str, str]]:
        """Return headers from the cached token, if it is still valid."""
        with self._cache_lock:
            if self._cached_token and time.time() < self._token_expires_at - 10:
                return {"Authorization": f"Bearer {self._cached_token}"}
        return None

    def _store_token(self, token: str) -> dict[str, str]:
        """Cache a freshly minted token and return its headers."""
        with self._cache_lock:
            self._cached_token = token
            self._token_expires_at = time.time() + self._ttl
        return {"Authorization": f"Bearer {token}"}

    async def get_auth_headers(self) -> dict[str, str]:
        """Get JWT auth headers with caching."""
        headers = self._cached_headers()
        if headers is not None:
            return headers

        async with self._async_mint_lock():
            # Another coroutine may have minted a token while we waited.
            headers = self._cached_headers()
            if headers is not None:
                return headers
            return self._store_token(await self._generate_token())

    def get_auth_headers_sync(self) -> dict[str, str]:
        """Get JWT auth headers with caching, without an event loop."""
        headers = self._cached_headers()
        if headers is not None:
            return headers

        with self._sync_mint_lock:
            # Another thread may have minted a token while we waited.
            headers = self._cached_headers()
            if headers is not None:
                return headers
            return self._store_token(self._generate_token_sync())

    def _token_request(self) -> tuple[str, dict[str, str], dict[str, Any], dict[str, str]]:
        """Build the endpoint, params, payload and headers for minting a token."""
        endpoint = f"{self._mp_url}/v1/api_keys"
        params = {"type": "batch"}
        payload: dict[str, Any] = {"ttl": self._ttl, "region": str(self._region)}

        if self._client_ref:
            payload["client_ref"] = self._client_ref

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if self._request_id:
            headers["X-Request-Id"] = self._request_id

        return endpoint, params, payload, headers

    def _generate_token_sync(self) -> str:
        import httpx

        endpoint, params, payload, headers = self._token_request()

        try:
            response = httpx.post(endpoint, params=params, json=payload, headers=headers, timeout=10)
            if response.status_code != 201:
                raise AuthenticationError(f"Failed to generate JWT: HTTP {response.status_code}: {response.text}")

            return str(response.json()["key_value"])

        except httpx.HTTPError as e:
            raise AuthenticationError(f"Network error generating JWT: {e}")
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Unexpected error generating JWT: {e}")

    async def _generate_token(self) -> str:
        import aiohttp

        endpoint, params, payload, headers = self._token_request()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    params=params,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 201:
                        text = await response.text()
                        raise AuthenticationError(f"Failed to generate JWT: HTTP {response.status}: {text}")

                    data = await response.json()
                    return str(data["key_value"])

        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Network error generating JWT: {e}")
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Unexpected error generating JWT: {e}")
