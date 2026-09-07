from __future__ import annotations

import importlib.metadata


def get_version() -> str:
    """
    Get the installed version of the speechmatics-agent-stt package.

    This function attempts to retrieve the package version using multiple
    fallback strategies to ensure it works in various deployment scenarios.

    Returns:
        str: The package version string (e.g., "1.2.3"), or "0.0.0" if
             version cannot be determined.
    """
    try:
        return importlib.metadata.version("speechmatics-agent-stt")
    except importlib.metadata.PackageNotFoundError:
        try:
            from . import __version__

            return __version__
        except ImportError:
            return "0.0.0"
