import pytest

from speechmatics.agent_stt import Model
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import TurnDetectionMode


def test_service_vad_is_the_default():
    assert TranscriptionConfig().to_dict()["vad_config"] == {"enabled": True}


def test_external_mode_disables_service_vad():
    config = TranscriptionConfig(turn_detection_mode=TurnDetectionMode.EXTERNAL)
    assert config.to_dict()["vad_config"] == {"enabled": False}


def test_turn_detection_mode_is_not_sent():
    assert "turn_detection_mode" not in TranscriptionConfig().to_dict()


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


def test_emit_sentences_omitted_unless_set():
    assert "emit_sentences" not in TranscriptionConfig().to_dict()
    assert TranscriptionConfig(emit_sentences=True).to_dict()["emit_sentences"] is True
    assert TranscriptionConfig(emit_sentences=False).to_dict()["emit_sentences"] is False


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
