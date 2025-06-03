"""
Version utilities for Speechmatics SDKs.
"""

import importlib.metadata
import os


def get_version(package_name: str, fallback_module_path: str) -> str:
    """
    Get SDK version from package metadata or VERSION file.

    Args:
        package_name: Name of the package to get version for
        fallback_module_path: Path to the module containing VERSION file

    Returns:
        Version string
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        # Fall back to VERSION file for development
        version_path = os.path.join(fallback_module_path, "VERSION")
        try:
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "unknown"
