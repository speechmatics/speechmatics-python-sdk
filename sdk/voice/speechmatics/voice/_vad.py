#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import logging
import os
import time
import urllib.request
from collections import deque
from typing import Any
from typing import Callable
from typing import Optional
from urllib.parse import urlparse

import numpy as np

from speechmatics.voice._models import BaseModel

ort: Any
logger = logging.getLogger(__name__)

try:
    import onnxruntime as _ort

    ort = _ort
except ModuleNotFoundError:
    ort = None


# Silero VAD model
SILERO_MODEL_URL = os.getenv(
    "SILERO_MODEL_URL", "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
SILERO_MODEL_PATH = os.getenv("SILERO_MODEL_PATH", ".models/silero_vad.onnx")

# Hint for when dependencies are not available
SILERO_INSTALL_HINT = "Silero VAD unavailable. Install `speechmatics-voice[smart]` to enable VAD."

# Silero VAD supported sample rates (see https://github.com/snakers4/silero-vad)
SILERO_SUPPORTED_SAMPLE_RATES = [8000, 16000]

# Chunk and context sizes differ by sample rate.
# Both result in ~32ms chunks: 512/16000 = 256/8000 = 0.032s
SILERO_CHUNK_SIZES = {16000: 512, 8000: 256}
SILERO_CONTEXT_SIZES = {16000: 64, 8000: 32}

MODEL_RESET_STATES_TIME = 5.0  # Reset state every 5 seconds
SILERO_CHUNK_DURATION_MS = 32.0  # Both sample rates produce 32ms chunks


class SileroVADResult(BaseModel):
    """VAD result from Silero.

    Attributes:
        is_speech: True if speech detected, False if silence
        probability: Probability of speech (0.0-1.0)
        transition_duration_ms: Duration of consecutive silence in milliseconds (used for transition threshold)
        speech_ended: True if silence duration exceeded the threshold
        metadata: Additional metadata about the VAD result
        error: Error message if an error occurred
    """

    is_speech: bool = False
    probability: float = 0.0
    transition_duration_ms: float = 0.0
    speech_ended: bool = False
    metadata: Optional[dict] = None
    error: Optional[str] = None


class SileroVAD:
    """Silero Voice Activity Detector.

    Uses Silero's opensource VAD model for detecting speech vs silence.
    Supports 8kHz (256-sample chunks) and 16kHz (512-sample chunks).

    Further information at https://github.com/snakers4/silero-vad
    """

    def __init__(
        self,
        auto_init: bool = True,
        threshold: float = 0.5,
        silence_duration: float = 0.1,
        on_state_change: Optional[Callable[[SileroVADResult], None]] = None,
    ):
        """Create the new SileroVAD.

        Args:
            auto_init: Whether to automatically initialise the detector.
            threshold: Probability threshold for speech detection (0.0-1.0).
            silence_duration: Duration of consecutive silence (in ms) before considering speech ended.
            on_state_change: Optional callback invoked when VAD state changes (speech <-> silence).
        """

        self._is_initialized: bool = False
        self._threshold: float = threshold
        self._on_state_change: Optional[Callable[[SileroVADResult], None]] = on_state_change

        # ONNX session state
        self._state: Optional[np.ndarray] = None
        self._context: Optional[np.ndarray] = None
        self._last_reset_time: float = 0.0

        # Audio buffering
        self._audio_buffer: bytes = b""

        # Rolling window for predictions (100ms window = ~3-4 chunks at 32ms each)
        window_chunks = int((silence_duration * 1000) / SILERO_CHUNK_DURATION_MS) + 1
        self._prediction_window: deque[float] = deque(maxlen=window_chunks)

        # State tracking
        self._last_is_speech: bool = False  # Track previous state for change detection (default: not speaking)

        if auto_init:
            self.setup()

    @staticmethod
    def dependencies_available() -> bool:
        """Return whether optional Silero dependencies are installed."""
        return ort is not None

    def setup(self) -> None:
        """Setup the detector.

        Initialises the ONNX model and internal states.
        """

        # Show warning if dependencies are not available
        if not self.dependencies_available():
            logger.warning(SILERO_INSTALL_HINT)
            return

        try:
            # Check / download the model
            self.download_model()

            # Check the model downloaded
            if not self.model_exists():
                logger.warning("Silero VAD model not found. Please download the model first.")
                return

            # Build the session
            self.session = self.build_session(SILERO_MODEL_PATH)

            # Initialize states
            self._init_states()

            # Set initialized
            self._is_initialized = True

        except Exception as e:
            logger.error(f"Failed to setup SileroVAD: {e}")

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
        so.inter_op_num_threads = 1
        so.intra_op_num_threads = 1

        # Return the new session
        return ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"], sess_options=so)

    def _init_states(self, sample_rate: int = 16000) -> None:
        """Initialize or reset internal VAD states.

        Args:
            sample_rate: Audio sample rate, used to determine context size.
        """
        context_size = SILERO_CONTEXT_SIZES.get(sample_rate, 64)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, context_size), dtype=np.float32)
        self._last_sr: int = sample_rate
        self._last_reset_time = time.time()

    def _maybe_reset_states(self, sample_rate: int) -> None:
        """Reset ONNX model states periodically to prevent drift.

        Also resets if the sample rate changes between calls.

        Note: Does NOT reset prediction window or speech state tracking.
        """
        # Reset if sample rate changed (context size depends on it)
        sr_changed = hasattr(self, "_last_sr") and self._last_sr != sample_rate
        time_expired = (time.time() - self._last_reset_time) >= MODEL_RESET_STATES_TIME

        if sr_changed or time_expired:
            self._init_states(sample_rate)

    def process_chunk(self, chunk_f32: np.ndarray, sample_rate: int = 16000) -> float:
        """Process a single audio chunk and return speech probability.

        Chunk size depends on sample rate: 512 samples at 16kHz, 256 at 8kHz.

        Args:
            chunk_f32: Float32 numpy array of audio samples.
            sample_rate: Sample rate of the audio (8000 or 16000).

        Returns:
            Speech probability (0.0-1.0).

        Raises:
            ValueError: If chunk size doesn't match expected size for sample rate.
        """
        # Expected sizes depend on sample rate (512 @ 16kHz, 256 @ 8kHz)
        expected_chunk_size = SILERO_CHUNK_SIZES.get(sample_rate, 512)
        context_size = SILERO_CONTEXT_SIZES.get(sample_rate, 64)

        x = np.reshape(chunk_f32, (1, -1))
        if x.shape[1] != expected_chunk_size:
            raise ValueError(f"Expected {expected_chunk_size} samples for {sample_rate}Hz, got {x.shape[1]}")

        # Concatenate with context (previous N samples, where N depends on sample rate)
        if self._context is not None:
            x = np.concatenate((self._context, x), axis=1)

        # Run ONNX inference — pass actual sample rate so the model uses correct internal params
        ort_inputs = {
            "input": x.astype(np.float32),
            "state": self._state,
            "sr": np.array(sample_rate, dtype=np.int64),
        }
        out, self._state = self.session.run(None, ort_inputs)

        # Update context (keep last N samples for next chunk)
        self._context = x[:, -context_size:]

        # Maybe reset states periodically
        self._maybe_reset_states(sample_rate)

        # Return probability (out shape is (1, 1))
        return float(out[0][0])

    async def process_audio(self, audio_bytes: bytes, sample_rate: int = 16000, sample_width: int = 2) -> None:
        """Process incoming audio bytes and invoke callback on state changes.

        This method buffers incomplete chunks and processes all complete chunks.
        Chunk size depends on sample rate: 512 samples at 16kHz, 256 at 8kHz.
        The callback is invoked only once at the end if the VAD state changed during processing.

        Args:
            audio_bytes: Raw audio bytes (int16 PCM).
            sample_rate: Sample rate of the audio (8000 or 16000).
            sample_width: Sample width in bytes (2 for int16).
        """

        if not self._is_initialized:
            logger.error("SileroVAD is not initialized")
            return

        # Silero VAD only supports 8kHz and 16kHz natively
        if sample_rate not in SILERO_SUPPORTED_SAMPLE_RATES:
            logger.error(f"Sample rate must be one of {SILERO_SUPPORTED_SAMPLE_RATES}Hz, got {sample_rate}Hz")
            return

        # Add new bytes to buffer
        self._audio_buffer += audio_bytes

        # Chunk size depends on sample rate (512 @ 16kHz, 256 @ 8kHz)
        chunk_samples = SILERO_CHUNK_SIZES[sample_rate]
        bytes_per_chunk = chunk_samples * sample_width

        # Process all complete chunks in buffer
        while len(self._audio_buffer) >= bytes_per_chunk:
            # Extract one chunk
            chunk_bytes = self._audio_buffer[:bytes_per_chunk]
            self._audio_buffer = self._audio_buffer[bytes_per_chunk:]

            # Convert bytes to int16 array
            dtype = np.int16 if sample_width == 2 else np.int8
            int16_array: np.ndarray = np.frombuffer(chunk_bytes, dtype=dtype).astype(np.int16)

            # Convert int16 to float32 in range [-1, 1]
            float32_array: np.ndarray = int16_array.astype(np.float32) / 32768.0

            try:
                # Process the chunk with the correct sample rate
                probability = self.process_chunk(float32_array, sample_rate=sample_rate)
                self._prediction_window.append(probability)

            except Exception as e:
                logger.error(f"Error processing VAD chunk: {e}")

        # After processing all chunks, calculate weighted average from window
        if len(self._prediction_window) > 0:
            # Calculate weighted average (most recent predictions have higher weight)
            weights = np.arange(1, len(self._prediction_window) + 1, dtype=np.float32)
            weighted_avg = np.average(list(self._prediction_window), weights=weights)

            # Determine speech state from weighted average
            is_speech = bool(weighted_avg >= self._threshold)

            # Check if state changed
            state_changed = self._last_is_speech != is_speech

            # Emit callback if state changed
            if state_changed and self._on_state_change:
                # Calculate transition duration (window duration)
                transition_duration = len(self._prediction_window) * SILERO_CHUNK_DURATION_MS

                # Determine if speech ended
                speech_ended = self._last_is_speech and not is_speech

                # VAD result
                result = SileroVADResult(
                    is_speech=is_speech,
                    probability=round(float(weighted_avg), 3),
                    transition_duration_ms=transition_duration,
                    speech_ended=speech_ended,
                )

                # Trigger callback
                self._on_state_change(result)

            # Update state after emitting
            self._last_is_speech = is_speech

    @property
    def is_speech_likely(self) -> bool:
        """Quick check if the most recent raw prediction suggests speech.

        Unlike _last_is_speech which uses a smoothed rolling average (slower to
        react), this checks the latest chunk prediction directly — giving faster
        speech-onset detection at the cost of more false positives.
        """
        if not self._prediction_window:
            return self._last_is_speech
        return float(self._prediction_window[-1]) >= self._threshold

    def reset(self, sample_rate: int = 16000) -> None:
        """Reset the VAD state and clear audio buffer.

        Args:
            sample_rate: Sample rate to reinitialise context size for.
        """
        if self._is_initialized:
            self._init_states(sample_rate)
            self._audio_buffer = b""
            self._prediction_window.clear()
            self._last_is_speech = False

    @staticmethod
    def download_model() -> None:
        """Download the ONNX model.

        This will check if the model has been downloaded and is available in the
        location specified by the SILERO_MODEL_PATH environment variable.

        If not, it will download the model from GitHub.
        """

        # Check if model file exists
        if SileroVAD.model_exists():
            return

        # Check the URL for valid schemes
        parsed_url = urlparse(SILERO_MODEL_URL)
        if parsed_url.scheme not in ("http", "https"):
            logger.error(f"Invalid URL scheme: {parsed_url.scheme}")
            return

        # Report to the user
        logger.warning("Silero VAD model not found. Downloading from GitHub...")

        # Create the directory
        os.makedirs(os.path.dirname(SILERO_MODEL_PATH), exist_ok=True)

        # Download
        urllib.request.urlretrieve(SILERO_MODEL_URL, SILERO_MODEL_PATH)  # nosec B310

    @staticmethod
    def model_exists() -> bool:
        """Check the model has been downloaded.

        Returns:
            True if the model file exists, False otherwise.
        """
        return os.path.exists(SILERO_MODEL_PATH)
