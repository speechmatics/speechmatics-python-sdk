from speechmatics.batch._models import JobConfig, TranscriptFilteringConfig, TranscriptionConfig


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

    def test_replacements_serialized(self):
        replacements = [{"from": "um", "to": ""}, {"from": "uh", "to": ""}]
        config = TranscriptionConfig(
            transcript_filtering_config=TranscriptFilteringConfig(replacements=replacements)
        )
        result = config.to_dict()
        assert result["transcript_filtering_config"] == {"replacements": replacements}

    def test_replacements_absent_when_none(self):
        config = TranscriptionConfig(
            transcript_filtering_config=TranscriptFilteringConfig(remove_disfluencies=True)
        )
        result = config.to_dict()
        assert "replacements" not in result["transcript_filtering_config"]

    def test_replacements_and_remove_disfluencies_together(self):
        replacements = [{"from": "gonna", "to": "going to"}]
        config = TranscriptionConfig(
            transcript_filtering_config=TranscriptFilteringConfig(
                remove_disfluencies=True, replacements=replacements
            )
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

    def test_bool_form_normalizes_to_config_object(self):
        data = {
            "type": "transcription",
            "transcription_config": {
                "language": "en",
                "transcript_filtering_config": True,
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
        assert tfc.remove_disfluencies is None

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
