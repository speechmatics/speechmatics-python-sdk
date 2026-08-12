import pytest

from speechmatics.agent_stt import Model
from speechmatics.agent_stt import TranscriptionConfig
from speechmatics.agent_stt import VADConfig
from speechmatics.agent_stt import VADMode


def test_server_vad_is_the_default():
    assert TranscriptionConfig().to_dict()["vad_config"] == {"enabled": True}


def test_client_vad_disables_service_vad():
    config = TranscriptionConfig(vad_mode=VADMode.CLIENT)
    assert config.to_dict()["vad_config"] == {"enabled": False}


def test_vad_mode_is_not_sent():
    assert "vad_mode" not in TranscriptionConfig().to_dict()


def test_vad_tuning_passed_through():
    config = TranscriptionConfig(vad_config=VADConfig(window=0.3, onset_threshold=0.6, offset_threshold=0.4))
    assert config.to_dict()["vad_config"] == {
        "window": 0.3,
        "onset_threshold": 0.6,
        "offset_threshold": 0.4,
        "enabled": True,
    }


def test_model_unset_by_default():
    """The service profile pins the model, so the SDK must not send one unasked."""
    assert "model" not in TranscriptionConfig().to_dict()


def test_model_sent_when_given():
    assert TranscriptionConfig(model=Model.ENHANCED).to_dict()["model"] == Model.ENHANCED


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
        TranscriptionConfig(model=Model.ENHANCED, operating_point="enhanced")


def test_operating_point_deprecated():
    with pytest.warns(DeprecationWarning):
        TranscriptionConfig(operating_point="enhanced")
