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

# Silero VAD constants
SILERO_SAMPLE_RATE = 16000
SILERO_CHUNK_SIZE = 512  # Silero expects 512 samples at 16kHz (32ms chunks)
SILERO_CONTEXT_SIZE = 64  # Silero uses 64-sample context
MODEL_RESET_STATES_TIME = 5.0  # Reset state every 5 seconds
SILERO_CHUNK_DURATION_MS = (SILERO_CHUNK_SIZE / SILERO_SAMPLE_RATE) * 1000  # 32ms per chunk


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
    Processes audio in 512-sample chunks at 16kHz.

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

    def _init_states(self) -> None:
        """Initialize or reset internal VAD states."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, SILERO_CONTEXT_SIZE), dtype=np.float32)
        self._last_reset_time = time.time()

    def _maybe_reset_states(self) -> None:
        """Reset ONNX model states periodically to prevent drift.

        Note: Does NOT reset prediction window or speech state tracking.
        """
        if (time.time() - self._last_reset_time) >= MODEL_RESET_STATES_TIME:
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
            self._context = np.zeros((1, SILERO_CONTEXT_SIZE), dtype=np.float32)
            self._last_reset_time = time.time()

    def process_chunk(self, chunk_f32: np.ndarray) -> float:
        """Process a single 512-sample chunk and return speech probability.

        Args:
            chunk_f32: Float32 numpy array of exactly 512 samples.

        Returns:
            Speech probability (0.0-1.0).

        Raises:
            ValueError: If chunk is not exactly 512 samples.
        """
        # Ensure shape (1, 512)
        x = np.reshape(chunk_f32, (1, -1))
        if x.shape[1] != SILERO_CHUNK_SIZE:
            raise ValueError(f"Expected {SILERO_CHUNK_SIZE} samples, got {x.shape[1]}")

        # Concatenate with context (previous 64 samples)
        if self._context is not None:
            x = np.concatenate((self._context, x), axis=1)

        # Run ONNX inference
        ort_inputs = {
            "input": x.astype(np.float32),
            "state": self._state,
            "sr": np.array(SILERO_SAMPLE_RATE, dtype=np.int64),
        }
        out, self._state = self.session.run(None, ort_inputs)

        # Update context (keep last 64 samples)
        self._context = x[:, -SILERO_CONTEXT_SIZE:]

        # Maybe reset states periodically
        self._maybe_reset_states()

        # Return probability (out shape is (1, 1))
        return float(out[0][0])

    def _validate_input(self, sample_rate: int) -> bool:
        """
        Ensures the VAD is ready and the incoming audio format
        matches the model's requirements.

        Args:
            sample_rate: Sample rate of the incoming audio.

        Returns:
            True if the VAD is ready and the incoming sample rate matches the model's requirements.
        """
        if not self._is_initialized:
            logger.error("SileroVAD is not initialized")
            return False

        if sample_rate != SILERO_SAMPLE_RATE:
            logger.error(f"Sample rate must be {SILERO_SAMPLE_RATE}Hz, got {sample_rate}Hz")
            return False

        return True

    def _get_audio_chunks(self, sample_width: int):
        """
        A generator that yields complete 512-sample chunks from the buffer.
        Incomplete data remains in the buffer for the next call.

        Args:
            sample_width: Sample width of the incoming audio.

        Yields:
            Complete 512-sample chunks from the buffer.
        """
        # Calculate bytes needed for a full model window
        bytes_per_chunk = SILERO_CHUNK_SIZE * sample_width

        while len(self._audio_buffer) >= bytes_per_chunk:
            # Extract the chunk from the front of the buffer
            chunk = self._audio_buffer[:bytes_per_chunk]
            self._audio_buffer = self._audio_buffer[bytes_per_chunk:]

            yield chunk

    def _prepare_chunk(self, chunk_bytes: bytes, sample_width: int) -> np.ndarray:
        """
        Translates raw PCM bytes into a normalised float32 array in the range [-1, 1],
        compatible with the Silero VAD model.

        Args:
            chunk_bytes: Audio bytes to be processed.
            sample_width: Sample width of the incoming audio.

        Returns:
            Normalised float32 array in the range [-1, 1].
        """
        if sample_width == 2:
            dtype = np.int16
            divisor = 32768.0
        elif sample_width == 1:
            dtype = np.int8
            divisor = 128.0
        else:
            raise ValueError(f"Unsupported sample_width {sample_width}")

        # Decode and normalize the chunk data
        int_array = np.frombuffer(chunk_bytes, dtype=dtype)
        float32_array: np.ndarray = int_array.astype(np.float32) / divisor

        return float32_array

    def _evaluate_activity_change(self) -> None:
        """
        Analyzes the prediction window of probabilities to determine if the user has started
        or stopped speaking. If the state has changed, emit a VADStatusMessage.

        Returns:
            None
        """
        if len(self._prediction_window) == 0:
            return

        # Calculate weighted average (most recent predictions have higher weight)
        probs = list(self._prediction_window)
        weights = np.arange(1, len(probs) + 1, dtype=np.float32)
        weighted_avg = np.average(probs, weights=weights)

        # Determine speech state from weighted average
        is_speech = bool(weighted_avg >= self._threshold)

        # Check if state changed
        state_changed = self._last_is_speech != is_speech

        if not state_changed:
            # No change, exit early
            return

        # Trigger callback function for state change
        if self._on_state_change:
            self._trigger_on_state_change(is_speech, weighted_avg)

        # Update state
        self._last_is_speech = is_speech

    def _trigger_on_state_change(self, is_speech: bool, probability: float) -> None:
        """
        Constructs the result object and executes the on_state_change callback
        function.

        Args:
            is_speech: True if speech is detected, False otherwise.
            probability: Speech probability (0.0-1.0).
        """
        # Calculate how many milliseconds of audio the window represents
        duration_ms = len(self._prediction_window) * SILERO_CHUNK_DURATION_MS

        # Determine if speech has ended
        speech_ended = self._last_is_speech and not is_speech

        # Create VAD result
        result = SileroVADResult(
            is_speech=is_speech,
            probability=round(float(probability), 3),
            transition_duration_ms=duration_ms,
            speech_ended=speech_ended,
        )

        # Trigger callback with result
        self._on_state_change(result)

    async def process_audio(self, audio_bytes: bytes, sample_rate: int = 16000, sample_width: int = 2) -> None:
        """Process incoming audio bytes and invoke callback on state changes.

        This method buffers incomplete chunks and processes all complete 512-sample chunks.
        The callback is invoked only once at the end if the VAD state changed during processing.

        Args:
            audio_bytes: Raw audio bytes (int16 PCM).
            sample_rate: Sample rate of the audio (must be 16000).
            sample_width: Sample width in bytes (2 for int16).
        """
        if not self._validate_input(sample_rate):
            return

        # Add new bytes to the buffer
        self._audio_buffer += audio_bytes

        # Process all complete chunks in the buffer
        for chunk in self._get_audio_chunks(sample_width):
            audio_f32 = self._prepare_chunk(chunk, sample_width)

            try:
                probability = self.process_chunk(audio_f32)
                self._prediction_window.append(probability)
            except Exception as e:
                logger.error(f"Error processing VAD chunk: {e}")
                continue

        # Check if VAD state has changed
        self._evaluate_activity_change()

    def reset(self) -> None:
        """Reset the VAD state and clear audio buffer."""
        if self._is_initialized:
            self._init_states()
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
