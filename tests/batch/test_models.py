from dataclasses import asdict
from typing import Optional

from speechmatics.batch._models import JobConfig
from speechmatics.batch._models import RecognitionResult
from speechmatics.batch._models import Transcript
from speechmatics.batch._models import TranscriptFilteringConfig
from speechmatics.batch._models import TranscriptionConfig


def _transcript_payload(results: list[dict], word_delimiter: str = " ") -> dict:
    return {
        "format": "2.9",
        "job": {
            "id": "job-id",
            "created_at": "2026-06-12T00:00:00Z",
            "data_name": "audio.wav",
        },
        "metadata": {
            "created_at": "2026-06-12T00:00:00Z",
            "type": "transcription",
            "language_pack_info": {"word_delimiter": word_delimiter},
        },
        "results": results,
    }


def _recognition_result(
    result_type: str,
    content: str,
    attaches_to: Optional[str] = None,
    is_eos: Optional[bool] = None,
) -> dict:
    result = {
        "type": result_type,
        "start_time": 1.0,
        "end_time": 1.0,
        "alternatives": [{"content": content, "confidence": 1.0, "language": "en"}],
    }
    if attaches_to is not None:
        result["attaches_to"] = attaches_to
    if is_eos is not None:
        result["is_eos"] = is_eos
    return result


class TestTranscriptFilteringConfigToDict:
    def test_remove_disfluencies_true_serializes_correctly(self):
        config = TranscriptionConfig(transcript_filtering_config=TranscriptFilteringConfig(remove_disfluencies=True))
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {"remove_disfluencies": True}

    def test_remove_disfluencies_false_included_in_output(self):
        config = TranscriptionConfig(transcript_filtering_config=TranscriptFilteringConfig(remove_disfluencies=False))
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {"remove_disfluencies": False}

    def test_none_excluded_from_output(self):
        config = TranscriptionConfig()
        result = config.to_dict()
        assert "transcript_filtering_config" not in result

    def test_replacements_serialized(self):
        replacements = [{"from": "um", "to": ""}, {"from": "uh", "to": ""}]
        config = TranscriptionConfig(transcript_filtering_config=TranscriptFilteringConfig(replacements=replacements))
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {
            "remove_disfluencies": False,
            "replacements": replacements,
        }

    def test_replacements_absent_when_none(self):
        config = TranscriptionConfig(transcript_filtering_config=TranscriptFilteringConfig(remove_disfluencies=True))
        result = config.to_dict()
        assert "replacements" not in result["transcript_filtering_config"]

    def test_replacements_and_remove_disfluencies_together(self):
        replacements = [{"from": "gonna", "to": "going to"}]
        config = TranscriptionConfig(
            transcript_filtering_config=TranscriptFilteringConfig(remove_disfluencies=True, replacements=replacements)
        )
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {
            "remove_disfluencies": True,
            "replacements": replacements,
        }


class TestTranscriptFilteringConfigFromDict:
    def test_dict_form_deserializes_to_config_object(self):
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": {"remove_disfluencies": True},
            },
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        tfc = job_config.transcription_config.transcript_filtering_config
        assert isinstance(tfc, TranscriptFilteringConfig)
        assert tfc.remove_disfluencies is True

    def test_absent_field_is_none(self):
        data = {
            "type": "transcription",
            "transcription_config": {"language": "en"},
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        assert job_config.transcription_config.transcript_filtering_config is None

    def test_dict_with_replacements_deserializes(self):
        replacements = [{"from": "um", "to": ""}, {"from": "uh", "to": ""}]
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": {"replacements": replacements},
            },
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        tfc = job_config.transcription_config.transcript_filtering_config
        assert isinstance(tfc, TranscriptFilteringConfig)
        assert tfc.replacements == replacements
        assert tfc.remove_disfluencies is False

    def test_dict_with_replacements_and_remove_disfluencies_deserializes(self):
        replacements = [{"from": "gonna", "to": "going to"}]
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": {
                    "remove_disfluencies": True,
                    "replacements": replacements,
                },
            },
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        tfc = job_config.transcription_config.transcript_filtering_config
        assert isinstance(tfc, TranscriptFilteringConfig)
        assert tfc.remove_disfluencies is True
        assert tfc.replacements == replacements


class TestOutputConfigFromDict:
    def test_output_config_deserialized(self):
        data = {
            "type": "transcription",
            "output_config": {"generate_lattice": True},
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.output_config is not None
        assert job_config.output_config.generate_lattice is True

    def test_absent_output_config_is_none(self):
        data = {"type": "transcription"}
        job_config = JobConfig.from_dict(data)
        assert job_config.output_config is None


class TestRecognitionResultFromDict:
    def test_preserves_punctuation_metadata(self):
        result = RecognitionResult.from_dict(
            _recognition_result("punctuation", ".", attaches_to="previous", is_eos=True)
        )

        assert result.attaches_to == "previous"
        assert result.is_eos is True

    def test_transcript_payload_preserves_punctuation_metadata_in_asdict(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("word", "Hello"),
                    _recognition_result("punctuation", ".", attaches_to="previous", is_eos=True),
                ]
            )
        )

        assert transcript.results[1].attaches_to == "previous"
        assert asdict(transcript)["results"][1]["attaches_to"] == "previous"
        assert asdict(transcript)["results"][1]["is_eos"] is True


class TestTranscriptText:
    def test_word_only_transcript_uses_word_delimiter(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("word", "Hello"),
                    _recognition_result("word", "world"),
                ]
            )
        )

        assert transcript.transcript_text == "Hello world"

    def test_punctuation_attached_to_previous(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("word", "Hello"),
                    _recognition_result("punctuation", ",", attaches_to="previous"),
                    _recognition_result("word", "world"),
                    _recognition_result("punctuation", ".", attaches_to="previous"),
                ]
            )
        )

        assert transcript.transcript_text == "Hello, world."

    def test_punctuation_attached_to_next(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("punctuation", "¿", attaches_to="next"),
                    _recognition_result("word", "Hola"),
                    _recognition_result("punctuation", "?", attaches_to="previous"),
                ]
            )
        )

        assert transcript.transcript_text == "¿Hola?"

    def test_punctuation_attached_to_neither_side(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("word", "hello"),
                    _recognition_result("punctuation", "-", attaches_to="none"),
                    _recognition_result("word", "world"),
                ]
            )
        )

        assert transcript.transcript_text == "hello - world"

    def test_punctuation_attached_to_both_sides(self):
        transcript = Transcript.from_dict(
            _transcript_payload(
                [
                    _recognition_result("word", "and"),
                    _recognition_result("punctuation", "/", attaches_to="both"),
                    _recognition_result("word", "or"),
                ]
            )
        )

        assert transcript.transcript_text == "and/or"
