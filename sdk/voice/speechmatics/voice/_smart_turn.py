#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import datetime
import logging
import os
import ssl
import urllib.request
from typing import Any
from typing import Optional
from urllib.parse import urlparse

import numpy as np

from speechmatics.voice._models import BaseModel

ort: Any
WhisperFeatureExtractor: Any
logger = logging.getLogger(__name__)

try:
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
    import certifi
    import onnxruntime as _ort
    from transformers import WhisperFeatureExtractor as _WhisperFeatureExtractor

    ort = _ort
    WhisperFeatureExtractor = _WhisperFeatureExtractor

    def _create_ssl_context(*args: Any, **kwargs: Any) -> ssl.SSLContext:
        """Create SSL context with certifi certificates."""
        if "cafile" not in kwargs:
            kwargs["cafile"] = certifi.where()
        return ssl.create_default_context(*args, **kwargs)

    ssl._create_default_https_context = _create_ssl_context

except ModuleNotFoundError:
    WhisperFeatureExtractor = None
    ort = None


# Base model from HuggingFace
SMART_TURN_MODEL_URL = os.getenv(
    "SMART_TURN_HF_URL", "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/smart-turn-v3.1-cpu.onnx"
)
SMART_TURN_MODEL_LOCAL_PATH = os.getenv("SMART_TURN_MODEL_PATH", ".models/smart-turn-v3.1-cpu.onnx")

# Hint for when dependencies are not available
SMART_TURN_INSTALL_HINT = "SMART_TURN mode unavailable. Install `speechmatics-voice[smart]` to enable SMART_TURN mode."


class SmartTurnPredictionResult(BaseModel):
    """Prediction result from the smart turn detector.

    Attributes:
        prediction: True for complete, False for incomplete
        probability: Probability of completion (sigmoid output)
        processing_time: Time taken to process the audio (in seconds)
        error: Error message if an error occurred
    """

    prediction: bool = False
    probability: float = 0.0
    processing_time: Optional[float] = None
    error: Optional[str] = None


class SmartTurnDetector:
    """Smart Turn Detector.

    Uses Pipecat's opensource acoustic model for determining if an audio sample
    is predicted to be complete or incomplete.

    Further information at https://github.com/pipecat-ai/smart-turn
    """

    def __init__(self, auto_init: bool = True, threshold: float = 0.8):
        """Create the new SmartTurnDetector.

        Args:
            auto_init: Whether to automatically initialise the detector.
            threshold: Probability threshold for turn completion (0.0-1.0).
        """

        # Has initialized
        self._is_initialized: bool = False

        # Threshold
        self._threshold: float = threshold

        # If auto_init is True, setup the detector
        if auto_init:
            self.setup()

    @staticmethod
    def dependencies_available() -> bool:
        """Return whether optional Smart Turn dependencies are installed."""
        return ort is not None and WhisperFeatureExtractor is not None

    def setup(self) -> None:
        """Setup the detector.

        Initialises the ONNX model and feature extractor.
        """

        # Show warning if dependencies are not available
        if not self.dependencies_available():
            logger.warning(SMART_TURN_INSTALL_HINT)
            return

        try:
            # Check / download the model
            self.download_model()

            # Check the model downloaded
            if not self.model_exists():
                logger.warning("Smart Turn model not found. Please download the model first.")
                return

            # Build the session
            self.session = self.build_session(SMART_TURN_MODEL_LOCAL_PATH)

            # Load the feature extractor
            self.feature_extractor = WhisperFeatureExtractor(chunk_length=8)

            # Set initialized
            self._is_initialized = True

        except Exception as e:
            logger.error(f"Failed to setup SmartTurnDetector: {e}")

    def build_session(self, onnx_path: str) -> ort.InferenceSession:
        """Build the ONNX session and load resources.

        Args:
            onnx_path: Path to the ONNX model.

        Returns:
            ONNX inference session.
        """

        # Show warning if dependencies are not available
        if ort is None:
            raise RuntimeError("onnxruntime is not available")

        # Build the session
        so = ort.SessionOptions()
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Return the new session
        return ort.InferenceSession(onnx_path, sess_options=so)

    async def predict(
        self, audio_array: bytes, language: str, sample_rate: int = 16000, sample_width: int = 2
    ) -> SmartTurnPredictionResult:
        """Predict whether an audio segment is complete (turn ended) or incomplete.

        Args:
            audio_array: Numpy array containing audio samples at 16kHz. The function
                will convert the audio into float32 and truncate to 8 seconds (keeping the end)
                or pad to 8 seconds.
            language: Language of the audio.
            sample_rate: Sample rate of the audio.
            sample_width: Sample width of the audio.

        Returns:
            Prediction result containing completion status and probability.
        """

        # Check if initialized
        if not self._is_initialized:
            return SmartTurnPredictionResult(error="SmartTurnDetector is not initialized")

        # Check a valid language
        if not self.valid_language(language):
            logger.warning(f"Invalid language: {language}. Results may be unreliable.")

        # Record start time
        start_time = datetime.datetime.now()

        # Convert into numpy array
        dtype = np.int16 if sample_width == 2 else np.int8
        int16_array: np.ndarray = np.frombuffer(audio_array, dtype=dtype).astype(np.int16)

        # Truncate to last 8 seconds if needed (keep the tail/end of audio)
        max_samples = 8 * sample_rate
        if len(int16_array) > max_samples:
            int16_array = int16_array[-max_samples:]

        # Convert int16 to float32 in range [-1, 1] (same as reference implementation)
        float32_array: np.ndarray = int16_array.astype(np.float32) / 32768.0

        # Process audio using Whisper's feature extractor
        inputs = self.feature_extractor(
            float32_array,
            sampling_rate=sample_rate,
            return_tensors="np",
            padding="max_length",
            max_length=max_samples,
            truncation=True,
            do_normalize=True,
        )

        # Extract features and ensure correct shape for ONNX
        input_features = inputs.input_features.squeeze(0).astype(np.float32)
        input_features = np.expand_dims(input_features, axis=0)

        # Run ONNX inference
        outputs = self.session.run(None, {"input_features": input_features})

        # Extract probability (ONNX model returns sigmoid probabilities)
        probability = outputs[0][0].item()

        # Make prediction (True for Complete, False for Incomplete)
        prediction = probability >= self._threshold

        # Record end time
        end_time = datetime.datetime.now()

        # Return the result
        return SmartTurnPredictionResult(
            prediction=prediction,
            probability=round(probability, 3),
            processing_time=round(float((end_time - start_time).total_seconds()), 3),
        )

    @staticmethod
    def truncate_audio_to_last_n_seconds(
        audio_array: np.ndarray, n_seconds: float = 8.0, sample_rate: int = 16000
    ) -> np.ndarray:
        """Truncate audio to last n seconds or pad with zeros to meet n seconds.

        Args:
            audio_array: Numpy array containing audio samples at 16kHz.
            n_seconds: Number of seconds to truncate to.
            sample_rate: Sample rate of the audio.

        Returns:
            Numpy array truncated to last n seconds or padded with zeros.
        """

        # Calculate the max samples we should have
        max_samples = int(n_seconds * sample_rate)

        # Truncate if longer
        if len(audio_array) > max_samples:
            return audio_array[-max_samples:]

        # Pad if shorter
        elif len(audio_array) < max_samples:
            padding = max_samples - len(audio_array)
            return np.pad(audio_array, (padding, 0), mode="constant", constant_values=0)

        # Otherwise return the array
        return audio_array

    @staticmethod
    def download_model() -> None:
        """Download the ONNX model.

        This will check if the model has been downloaded and is available in the
        location specified by the SMART_TURN_MODEL_PATH environment variable.

        If not, it will download the model from HuggingFace.
        """

        # Check if model file exists
        if SmartTurnDetector.model_exists():
            return

        # Check the URL for valid schemes
        parsed_url = urlparse(SMART_TURN_MODEL_URL)
        if parsed_url.scheme not in ("http", "https"):
            logger.error(f"Invalid URL scheme: {parsed_url.scheme}")
            return

        # Report to the user
        logger.warning("Smart Turn model not found. Downloading from HuggingFace...")

        # Create the directory
        os.makedirs(os.path.dirname(SMART_TURN_MODEL_LOCAL_PATH), exist_ok=True)

        # Download
        urllib.request.urlretrieve(SMART_TURN_MODEL_URL, SMART_TURN_MODEL_LOCAL_PATH)  # nosec B310

    @staticmethod
    def model_exists() -> bool:
        """Check the model has been downloaded.

        Returns:
            True if the model file exists, False otherwise.
        """
        return os.path.exists(SMART_TURN_MODEL_LOCAL_PATH)

    @staticmethod
    def valid_language(language: str) -> bool:
        """Check if the language is valid.

        Args:
            language: Language code to validate.

        Returns:
            True if the language is supported, False otherwise.
        """
        return language in [
            "ar",
            "bn",
            "zh",
            "da",
            "nl",
            "de",
            "en",
            "fi",
            "fr",
            "hi",
            "id",
            "it",
            "ja",
            "ko",
            "mr",
            "no",
            "pl",
            "pt",
            "ru",
            "es",
            "tr",
            "uk",
            "vi",
        ]
