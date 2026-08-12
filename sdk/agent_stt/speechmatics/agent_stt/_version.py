from __future__ import annotations

import importlib.metadata


def get_version() -> str:
    """
    Get the installed version of the speechmatics-agent-stt package.

    Returns:
        The package version, or "0.0.0" when it cannot be determined.
    """
    try:
        return importlib.metadata.version("speechmatics-agent-stt")
    except importlib.metadata.PackageNotFoundError:
        try:
            from . import __version__

            return __version__
        except ImportError:
            return "0.0.0"
