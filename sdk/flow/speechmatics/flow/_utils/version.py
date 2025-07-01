from __future__ import annotations

import importlib.metadata
from typing import Final

PACKAGE_NAME: Final = "speechmatics-flow"
FALLBACK_VERSION: Final = "0.0.0"


def get_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        try:
            from .. import __version__

            return __version__
        except ImportError:
            return FALLBACK_VERSION
