import abc
import os
from typing import Literal
from typing import Optional

from ._exceptions import AuthenticationError


class AuthBase(abc.ABC):
    """
    Abstract base class for authentication methods.
    """

    BASE_URL = "https://mp.speechmatics.com"

    @abc.abstractmethod
    async def get_auth_headers(self) -> dict[str, str]:
        """
        Get authentication headers asynchronously.

        Returns:
            Dictionary of headers to include in the request.
        """
        raise NotImplementedError


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
        region: Literal["eu", "usa"] = "eu",
        client_ref: Optional[str] = None,
        mp_url: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self._api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")
        self._ttl = ttl
        self._region = region
        self._client_ref = client_ref
        self._request_id = request_id
        self._mp_url = mp_url or os.environ.get("SM_MANAGEMENT_PLATFORM_URL", self.BASE_URL)

        if not self._api_key:
            raise ValueError(
                "API key required: please provide api_key or set SPEECHMATICS_API_KEY environment variable"
            )

        if not 60 <= self._ttl <= 86_400:
            raise ValueError("ttl must be between 60 and 86400 seconds")

    async def get_auth_headers(self) -> dict[str, str]:
        """Get JWT auth headers."""

        jwt = await self._generate_token()
        return {"Authorization": f"Bearer {jwt}"}

    async def _generate_token(self) -> str:
        try:
            import aiohttp
        except ImportError:
            raise ImportError(
                "aiohttp is required for JWT authentication. Please install it with `pip install 'speechmatics-rt[jwt]'`"
            )

        endpoint = f"{self._mp_url}/v1/api_keys"
        params = {"type": "rt"}
        payload = {"ttl": self._ttl, "region": str(self._region)}

        if self._client_ref:
            payload["client_ref"] = self._client_ref

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if self._request_id:
            headers["X-Request-Id"] = self._request_id

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
        except Exception as e:
            raise AuthenticationError(f"Unexpected error generating JWT: {e}")
