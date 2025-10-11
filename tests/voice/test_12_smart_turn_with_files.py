import os

import pytest
from _utils import load_audio_file
from pydantic import BaseModel

from speechmatics.voice._turn import SmartTurnDetector
from speechmatics.voice._turn import SmartTurnPredictionResult

# Skip for CI testing
pytestmark = pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping smart turn tests in CI")

# Detector
detector = SmartTurnDetector(auto_init=False, threshold=0.75)


class PredictionTest(BaseModel):
    id: str
    path: str
    language: str
    expected: SmartTurnPredictionResult


SAMPLES: list[PredictionTest] = [
    PredictionTest(
        id="01",
        path="./assets/smart_turn/01_false_16KHz.wav",
        language="en",
        expected=SmartTurnPredictionResult(
            prediction=False,
            probability=0.095,
        ),
    ),
    PredictionTest(
        id="02",
        path="./assets/smart_turn/02_false_16KHz.wav",
        language="en",
        expected=SmartTurnPredictionResult(
            prediction=False,
            probability=0.011,
        ),
    ),
    PredictionTest(
        id="03",
        path="./assets/smart_turn/03_true_16KHz.wav",
        language="en",
        expected=SmartTurnPredictionResult(
            prediction=True,
            probability=0.892,
        ),
    ),
]


@pytest.mark.asyncio
async def test_onnx_model():
    """Download ONNX model"""

    # Initialize
    detector.setup()

    # Check exists
    assert detector.model_exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: f"{s.id}:{s.path}")
async def test_prediction(sample: PredictionTest):
    """Test prediction"""

    # Load an audio snippet
    bytes_array = await load_audio_file(sample.path)

    # Run an inference
    result = await detector.predict(bytes_array, language=sample.language, sample_rate=16000, sample_width=2)

    # Processing time < 50ms
    assert result.processing_time < 0.05

    # Check result
    assert result.prediction == sample.expected.prediction

    # Prediction within 5% of expected
    assert (
        result.probability >= sample.expected.probability - 0.05
        and result.probability <= sample.expected.probability + 0.05
    )
