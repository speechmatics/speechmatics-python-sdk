from speechmatics.rt._models import TranscriptionConfig


class TestLanguageHintsToDict:
    def test_language_hints_serializes_correctly(self):
        config = TranscriptionConfig(language_hints=["en", "fr"])
        result = config.to_dict()
        assert result["language_hints"] == ["en", "fr"]
        assert "language_hints_strict" not in result

    def test_language_hints_strict_true_serializes_correctly(self):
        config = TranscriptionConfig(language_hints=["en"], language_hints_strict=True)
        result = config.to_dict()
        assert result["language_hints"] == ["en"]
        assert result["language_hints_strict"] is True

    def test_language_hints_strict_false_serializes_correctly(self):
        config = TranscriptionConfig(language_hints=["en"], language_hints_strict=False)
        result = config.to_dict()
        assert result["language_hints"] == ["en"]
        assert "language_hints_strict" in result
        assert result["language_hints_strict"] is False

    def test_language_hints_absent_when_none(self):
        config = TranscriptionConfig()
        result = config.to_dict()
        assert "language_hints" not in result
        assert "language_hints_strict" not in result
