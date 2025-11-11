import pytest

from speechmatics.voice import VoiceAgentConfig
from speechmatics.voice._models import OperatingPoint
from speechmatics.voice._models import SpeechSegmentConfig
from speechmatics.voice._presets import VoiceAgentConfigPreset


@pytest.mark.asyncio
async def test_presets():
    """Test VoiceAgentConfigPreset presets."""

    # Create a preset
    preset: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY()
    assert preset is not None
    assert preset.speech_segment_config.emit_sentences is True

    # Overlay #1
    preset: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY(
        VoiceAgentConfig(max_delay=12.34, enable_diarization=False)
    )
    assert preset is not None
    assert preset.max_delay == 12.34
    assert preset.enable_diarization is False

    # Overlay #2
    preset: VoiceAgentConfig = VoiceAgentConfigPreset.LOW_LATENCY(
        VoiceAgentConfig(speech_segment_config=SpeechSegmentConfig(emit_sentences=False))
    )
    assert preset is not None
    assert preset.enable_diarization is True
    assert preset.speech_segment_config.emit_sentences is False

    # Preset names
    presets = VoiceAgentConfigPreset.list_presets()
    assert "low_latency" in presets

    # Get a preset by a name
    preset: VoiceAgentConfig = VoiceAgentConfigPreset.load("low_latency")
    assert preset is not None


@pytest.mark.asyncio
async def test_json_presets():
    """Test VoiceAgentConfigPreset JSON presets."""

    # With a JSON string overlay
    preset: VoiceAgentConfig = VoiceAgentConfigPreset.load("low_latency", '{"operating_point": "enhanced"}')
    assert preset is not None
    assert preset.operating_point == OperatingPoint.ENHANCED

    # Check using incorrect preset name
    with pytest.raises(ValueError):
        VoiceAgentConfigPreset.load("invalid_preset")

    # Check with invalid overlay
    with pytest.raises(ValueError):
        VoiceAgentConfigPreset.load("low_latency", '{"invalid": "value"}')
