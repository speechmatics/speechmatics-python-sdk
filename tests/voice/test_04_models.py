import json

import pytest

from speechmatics.voice import AnnotationFlags
from speechmatics.voice import AnnotationResult


@pytest.mark.asyncio
async def test_annotation_result():
    """Test AnnotationResult."""

    # Create a new annotation
    annotation = AnnotationResult()
    assert annotation is not None

    # Add flags
    annotation.add(AnnotationFlags.NO_TEXT)
    annotation.add(AnnotationFlags.HAS_DISFLUENCY)
    annotation.add(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Has a flag
    assert annotation.has(AnnotationFlags.NO_TEXT)
    assert annotation.has(AnnotationFlags.HAS_DISFLUENCY)
    assert annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Remove a flag
    annotation.remove(AnnotationFlags.MULTIPLE_SPEAKERS)
    assert not annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS)

    # Add existing flag
    annotation.add(AnnotationFlags.NO_TEXT)
    assert annotation.has(AnnotationFlags.NO_TEXT)
    assert str(annotation) == "['no_text', 'has_disfluency']"

    # Add multiple flags
    annotation.add(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)
    assert annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)

    # Remove multiple flags
    annotation.remove(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)
    assert not annotation.has(AnnotationFlags.MULTIPLE_SPEAKERS, AnnotationFlags.STARTS_WITH_DISFLUENCY)

    # Compare
    assert annotation == AnnotationResult([AnnotationFlags.HAS_DISFLUENCY, AnnotationFlags.NO_TEXT])

    # Compare with non AnnotationResult
    assert annotation != "string"
    assert annotation != 123

    # String representation
    assert str(annotation) == "['no_text', 'has_disfluency']"
    assert str({"annotation": annotation}) == "{'annotation': ['no_text', 'has_disfluency']}"
    assert json.dumps({"annotation": annotation}) == '{"annotation": ["no_text", "has_disfluency"]}'
