#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

from dataclasses import asdict
from dataclasses import is_dataclass
from typing import Any
from typing import cast


def to_serializable(obj: Any):
    """Convert an object into a JSON-serializable form.

    Args:
        obj: The object to convert.

    Returns:
        The JSON-serializable form of the object.
    """

    # Dataclasses → dict
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_serializable(v) for k, v in asdict(cast(Any, obj)).items()}

    # dicts → dict with serializable values
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}

    # lists/tuples → list with serializable items
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]

    # basic types → leave as is
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    # fallback → string
    return str(obj)
