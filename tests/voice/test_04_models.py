import json

import pytest

from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import AdditionalVocabEntry
from speechmatics.voice._models import AnnotationFlags
from speechmatics.voice._models import AnnotationResult
from speechmatics.voice._models import SpeakerFocusConfig
from speechmatics.voice._models import SpeakerFocusMode
from speechmatics.voice._models import SpeakerIdentifier
from speechmatics.voice._models import SpeakerSegment
from speechmatics.voice._models import SpeechFragment
from speechmatics.voice._models import SpeechSegmentConfig
from speechmatics.voice._presets import VoiceAgentConfigPreset


@pytest.mark.asyncio
async def test_voice_agent_config():
    """Test VoiceAgentConfig Pydantic serialisation and deserialisation."""
    # Create instance with custom values
    config = VoiceAgentConfig(
        language="en",
        max_delay=1.5,
        enable_diarization=True,
        speaker_sensitivity=0.7,
        additional_vocab=[AdditionalVocabEntry(content="Speechmatics", sounds_like=["speech matics"])],
        known_speakers=[SpeakerIdentifier(label="John", speaker_identifiers=["78673523465237xx"])],
    )

    # Test JSON serialisation
    json_data = config.model_dump()
    assert json_data["language"] == "en"
    assert json_data["max_delay"] == 1.5
    assert json_data["enable_diarization"] is True
    assert json_data["speaker_sensitivity"] == 0.7
    assert len(json_data["additional_vocab"]) == 1
    assert json_data["additional_vocab"][0]["content"] == "Speechmatics"
    assert len(json_data["known_speakers"]) == 1
    assert json_data["known_speakers"][0]["label"] == "John"

    # Test JSON deserialisation
    config_from_json = VoiceAgentConfig.model_validate(json_data)
    assert config_from_json.language == config.language
    assert config_from_json.max_delay == config.max_delay
    assert config_from_json.enable_diarization == config.enable_diarization
    assert config_from_json.speaker_sensitivity == config.speaker_sensitivity
    assert len(config_from_json.additional_vocab) == 1
    assert config_from_json.additional_vocab[0].content == "Speechmatics"
    assert len(config_from_json.known_speakers) == 1
    assert config_from_json.known_speakers[0].label == "John"


@pytest.mark.asyncio
async def test_annotation_result():
    """Test AnnotationResult.

    - create new annotation
    - add, remove, check for flags
    - serialize to JSON
    """

    # Create a new annotation
    annotation = AnnotationResult.from_flags(AnnotationFlags.NO_TEXT, AnnotationFlags.HAS_DISFLUENCY)
    assert annotation is not None

    # Add extra flag
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


@pytest.mark.asyncio
async def test_additional_vocab_entry():
    """Test AdditionalVocabEntry serialisation and deserialisation.

    - create instance
    - serialize to JSON
    - deserialize from JSON
    """

    # Create instance
    entry = AdditionalVocabEntry(content="hello", sounds_like=["helo", "hallo"])

    # Test JSON serialisation
    json_data = entry.model_dump()
    assert json_data["content"] == "hello"
    assert json_data["sounds_like"] == ["helo", "hallo"]

    # Test JSON deserialisation
    entry_from_json = AdditionalVocabEntry.model_validate(json_data)
    assert entry_from_json.content == entry.content
    assert entry_from_json.sounds_like == entry.sounds_like

    # Test with defaults
    entry_minimal = AdditionalVocabEntry(content="test")
    json_minimal = entry_minimal.model_dump()
    assert json_minimal["sounds_like"] == []


@pytest.mark.asyncio
async def test_speaker_focus_config():
    """Test SpeakerFocusConfig serialisation and deserialisation.

    - create instance with custom values
    - serialize to JSON
    - deserialize from JSON
    """

    # Create instance with custom values
    config = SpeakerFocusConfig(
        focus_speakers=["S1", "S2"],
        ignore_speakers=["__ASSISTANT__", "__SYSTEM__"],
        focus_mode=SpeakerFocusMode.IGNORE,
    )

    # Test JSON serialisation
    json_data = config.model_dump()
    assert json_data["focus_speakers"] == ["S1", "S2"]
    assert json_data["ignore_speakers"] == ["__ASSISTANT__", "__SYSTEM__"]
    assert json_data["focus_mode"] == SpeakerFocusMode.IGNORE

    # Test JSON deserialisation
    config_from_json = SpeakerFocusConfig.model_validate(json_data)
    assert config_from_json.focus_speakers == config.focus_speakers
    assert config_from_json.ignore_speakers == config.ignore_speakers
    assert config_from_json.focus_mode == config.focus_mode

    # Test with defaults
    config_default = SpeakerFocusConfig()
    json_default = config_default.model_dump()
    assert json_default["focus_speakers"] == []
    assert json_default["ignore_speakers"] == []
    assert json_default["focus_mode"] == SpeakerFocusMode.RETAIN


@pytest.mark.asyncio
async def test_speech_fragment():
    """Test SpeechFragment serialisation and deserialisation.

    - create instance with annotation
    - serialize to JSON
    - deserialize from JSON
    """

    # Create instance with annotation
    annotation = AnnotationResult.from_flags(AnnotationFlags.HAS_FINAL, AnnotationFlags.ENDS_WITH_EOS)

    # Create fragment
    fragment = SpeechFragment(
        idx=1,
        start_time=0.5,
        end_time=1.2,
        language="en",
        content="Hello",
        speaker="S1",
        is_final=True,
        confidence=0.95,
        annotation=annotation,
    )

    # Test JSON serialisation
    json_data = fragment.model_dump()
    assert json_data["idx"] == 1
    assert json_data["start_time"] == 0.5
    assert json_data["end_time"] == 1.2
    assert json_data["content"] == "Hello"
    assert json_data["speaker"] == "S1"
    assert json_data["is_final"] is True
    assert json_data["confidence"] == 0.95
    assert isinstance(json_data["annotation"], list)


@pytest.mark.asyncio
async def test_speaker_segment():
    """Test SpeakerSegment serialisation and deserialisation.

    - create instance with annotation
    - serialize to JSON
    - deserialize from JSON
    """

    # Create fragments
    fragment1 = SpeechFragment(idx=1, start_time=0.5, end_time=1.0, content="Hello", speaker="S1")
    fragment2 = SpeechFragment(idx=2, start_time=1.0, end_time=1.5, content="world", speaker="S1")

    # Create annotation
    annotation = AnnotationResult.from_flags(AnnotationFlags.HAS_FINAL, AnnotationFlags.MULTIPLE_SPEAKERS)

    # Create instance
    segment = SpeakerSegment(
        speaker_id="S1",
        is_active=True,
        timestamp="2025-01-01T12:00:00.500",
        language="en",
        fragments=[fragment1, fragment2],
        text="Hello world",
        annotation=annotation,
    )

    # Test model_dump() default behavior (should exclude fragments by default)
    json_data = segment.model_dump()
    assert json_data["speaker_id"] == "S1"
    assert json_data["is_active"] is True
    assert json_data["timestamp"] == "2025-01-01T12:00:00.500"
    assert json_data["text"] == "Hello world"
    assert "fragments" not in json_data
    assert "results" not in json_data
    assert isinstance(json_data["annotation"], list)

    # Test model_dump with include_results=True
    dict_data_results = segment.model_dump(include_results=True)
    assert dict_data_results["speaker_id"] == "S1"
    assert dict_data_results["text"] == "Hello world"
    assert "results" in dict_data_results
    assert "fragments" not in dict_data_results
    assert len(dict_data_results["results"]) == 2


@pytest.mark.asyncio
async def test_presets():
    """Test VoiceAgentConfigPreset presets."""

    # Create a preset
    low_latency: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY()
    assert low_latency is not None
    assert low_latency.speech_segment_config.emit_sentences is True

    # Overlay #1
    low_latency_one: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY(
        VoiceAgentConfig(max_delay=12.34, enable_diarization=False)
    )
    assert low_latency_one is not None
    assert low_latency_one.max_delay == 12.34
    assert low_latency_one.enable_diarization is False

    # Overlay #2
    low_latency_two: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY(
        VoiceAgentConfig(speech_segment_config=SpeechSegmentConfig(emit_sentences=False))
    )
    assert low_latency_two is not None
    assert low_latency_two.enable_diarization is True
    assert low_latency_two.speech_segment_config.emit_sentences is False

    # Preset names
    presets = VoiceAgentConfigPreset.list_presets()
    assert "low_latency" in presets

    # Get a preset by a name
    low_latency: VoiceAgentConfig = VoiceAgentConfigPreset.get("low_latency")
    assert low_latency is not None

    # Check using incorrect preset name
    with pytest.raises(ValueError):
        VoiceAgentConfigPreset.get("invalid_preset")
