from __future__ import annotations

import os
from typing import Optional
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

from ._version import get_version

DEFAULT_RT_URL = "wss://eu2.rt.speechmatics.com/v2"
AGENT_PATH_SEGMENT = "agent"


def resolve_url(
    url: Optional[str] = None,
    profile: Optional[str] = None,
    app: Optional[str] = None,
) -> str:
    """
    Resolve the Agent STT WebSocket URL.

    The Agent STT endpoint is the RT endpoint plus an `/agent` path segment, optionally
    followed by a service profile name.

    Args:
        url: Explicit endpoint. Falls back to the `SPEECHMATICS_RT_URL` environment
            variable, then the EU endpoint.
        profile: Optional service profile, appended as a final path segment.
        app: Optional application name reported to the service as `sm-app`.

    Returns:
        The complete WebSocket URL.

    Examples:
        >>> resolve_url()
        'wss://eu2.rt.speechmatics.com/v2/agent?sm-app=agent-stt-sdk%2F0.0.0'
        >>> resolve_url("wss://host/v2", profile="default", app="pipecat/1.0")
        'wss://host/v2/agent/default?sm-app=pipecat%2F1.0'
    """
    base = url or os.getenv("SPEECHMATICS_RT_URL") or DEFAULT_RT_URL
    parsed = urlparse(base)
    return urlunparse(
        parsed._replace(
            path=_resolve_path(parsed.path, profile),
            query=_resolve_query(parsed.query, app),
        )
    )


def _resolve_path(path: str, profile: Optional[str]) -> str:
    """Append the /agent segment and the profile to the path, skipping any already present."""
    segments = [segment for segment in path.split("/") if segment]

    if AGENT_PATH_SEGMENT not in segments:
        segments.append(AGENT_PATH_SEGMENT)

    if profile:
        normalized = profile.strip("/")
        if normalized and segments[-1] != normalized:
            segments.append(normalized)

    return "/" + "/".join(segments)


def _resolve_query(query: str, app: Optional[str]) -> str:
    """Set the sm-app parameter, keeping any parameters already on the URL."""
    params = parse_qs(query, keep_blank_values=True)
    existing_app = params.get("sm-app", [None])[0]
    params["sm-app"] = [app or existing_app or f"agent-stt-sdk/{get_version()}"]
    return urlencode(params, doseq=True)
