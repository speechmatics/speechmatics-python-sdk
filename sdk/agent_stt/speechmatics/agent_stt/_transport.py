from __future__ import annotations

from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

from speechmatics.rt._transport import Transport

from ._version import get_version


class AgentTransport(Transport):
    """
    RT transport that identifies itself as the Agent STT SDK.

    Only the SDK identifier on the connection URL differs; the WebSocket handling,
    authentication and message framing are the RT transport's.
    """

    def _prepare_url(self) -> str:
        """Return the connection URL with the Agent STT SDK version as `sm-sdk`."""
        parsed = urlparse(self._url)
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params["sm-sdk"] = f"python-agent-stt-sdk-v{get_version()}"
        return urlunparse(parsed._replace(query=urlencode(params)))
