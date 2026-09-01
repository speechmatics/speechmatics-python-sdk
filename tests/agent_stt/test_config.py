import pytest

from speechmatics.agent_stt import Model
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import TurnDetectionMode


def test_service_vad_is_the_default():
    assert TranscriptionConfig().turn_config() == {"turn_detection_mode": "vad"}


def test_external_mode_selects_external_turn_detection():
    config = TranscriptionConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL)
    assert config.turn_config() == {"turn_detection_mode": "external"}


def test_turn_detection_is_not_in_the_transcription_config():
    """transcription_config is additionalProperties: false, so neither key may appear there."""
    config = TranscriptionConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL).to_dict()
    assert "turn_detection_mode" not in config
    assert "vad_config" not in config


def test_model_defaults_to_linden_1():
    assert TranscriptionConfig().to_dict()["model"] == "linden-1"


def test_model_sent_when_given():
    assert TranscriptionConfig(model=Model.LINDEN_1).to_dict()["model"] == Model.LINDEN_1


def test_model_omitted_when_operating_point_is_used():
    """The deprecated operating_point must not arrive alongside a defaulted model."""
    with pytest.warns(DeprecationWarning):
        config = TranscriptionConfig(operating_point="enhanced")
    assert "model" not in config.to_dict()
    assert config.to_dict()["operating_point"] == "enhanced"


def test_rt_fields_still_work():
    config = TranscriptionConfig(language="es", diarization="speaker", enable_partials=True, max_delay=1.5)
    result = config.to_dict()
    assert result["language"] == "es"
    assert result["diarization"] == "speaker"
    assert result["enable_partials"] is True
    assert result["max_delay"] == 1.5


def test_model_and_operating_point_conflict():
    with pytest.raises(ValueError):
        TranscriptionConfig(model=Model.LINDEN_1, operating_point="enhanced")


def test_operating_point_deprecated():
    with pytest.warns(DeprecationWarning):
        TranscriptionConfig(operating_point="enhanced")
