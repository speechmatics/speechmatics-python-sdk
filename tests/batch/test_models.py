from speechmatics.batch._models import JobConfig, TranscriptionConfig


class TestTranscriptFilteringConfigToDict:
    def test_true_serializes_to_remove_disfluencies_dict(self):
        config = TranscriptionConfig(transcript_filtering_config=True)
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {"remove_disfluencies": True}

    def test_false_serializes_to_remove_disfluencies_dict(self):
        config = TranscriptionConfig(transcript_filtering_config=False)
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {"remove_disfluencies": False}

    def test_none_excluded_from_output(self):
        config = TranscriptionConfig()
        result = config.to_dict()
        assert "transcript_filtering_config" not in result


class TestTranscriptFilteringConfigFromDict:
    def test_dict_form_deserializes_to_bool(self):
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": {"remove_disfluencies": True},
            },
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        assert job_config.transcription_config.transcript_filtering_config is True

    def test_bool_form_passes_through(self):
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": True,
            },
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        assert job_config.transcription_config.transcript_filtering_config is True

    def test_absent_field_is_none(self):
        data = {
            "type": "transcription",
            "transcription_config": {"language": "en"},
        }
        job_config = JobConfig.from_dict(data)
        assert job_config.transcription_config is not None
        assert job_config.transcription_config.transcript_filtering_config is None


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
