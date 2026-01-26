#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import asyncio
import datetime
import os
import re
import time
from collections.abc import Awaitable
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

from speechmatics.rt import AsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import AuthBase
from speechmatics.rt import ConversationConfig
from speechmatics.rt import ServerMessageType
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import SpeakerIdentifier
from speechmatics.rt import TranscriptionConfig
from speechmatics.rt._exceptions import TransportError

from . import __version__
from ._audio import AudioBuffer
from ._logging import get_logger
from ._models import AgentServerMessageType
from ._models import AnnotationFlags
from ._models import AnnotationResult
from ._models import BaseMessage
from ._models import ClientSessionInfo
from ._models import EndOfUtteranceMode
from ._models import ErrorMessage
from ._models import LanguagePackInfo
from ._models import MessageTimeMetadata
from ._models import SegmentMessage
from ._models import SegmentMessageSegment
from ._models import SegmentMessageSegmentFragment
from ._models import SessionMetricsMessage
from ._models import SessionSpeaker
from ._models import SpeakerFocusConfig
from ._models import SpeakerFocusMode
from ._models import SpeakerMetricsMessage
from ._models import SpeakerSegment
from ._models import SpeakerSegmentView
from ._models import SpeakerStatusMessage
from ._models import SpeechFragment
from ._models import TranscriptionUpdatePreset
from ._models import TurnPredictionMessage
from ._models import TurnPredictionMetadata
from ._models import TurnStartEndResetMessage
from ._models import VADStatusMessage
from ._models import VoiceAgentConfig
from ._presets import VoiceAgentConfigPreset
from ._smart_turn import SMART_TURN_INSTALL_HINT
from ._smart_turn import SmartTurnDetector
from ._smart_turn import SmartTurnPredictionResult
from ._turn import TurnTaskProcessor
from ._utils import FragmentUtils
from ._vad import SILERO_INSTALL_HINT
from ._vad import SileroVAD
from ._vad import SileroVADResult


class VoiceAgentClient(AsyncClient):
    """Voice Agent client.

    This class extends the AsyncClient class from the Speechmatics Real-Time SDK
    and provides additional functionality for processing partial and final
    transcription from the STT engine into accumulated transcriptions with
    flags to indicate changes between messages, etc.

    If no config or preset is provided, the client will default to the EXTERNAL
    preset.
    """

    # ============================================================================
    # INITIALISATION & CONFIGURATION
    # ============================================================================

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        app: Optional[str] = None,
        config: Optional[VoiceAgentConfig] = None,
        preset: Optional[str] = None,
    ):
        """Initialize the Voice Agent client.

        Args:
            auth: Authentication instance. If not provided, uses StaticKeyAuth
                with api_key parameter or SPEECHMATICS_API_KEY environment variable.
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: REST API endpoint URL. If None, uses SPEECHMATICS_RT_URL env var
                 or defaults to production endpoint.
            app: Optional application name to use in the endpoint URL.
            config: Optional voice agent configuration.
            preset: Optional voice agent preset.

        Examples:
            Recommended - using context manager:
                >>> from speechmatics.voice import VoiceAgentClient, VoiceAgentConfig
                >>> config = VoiceAgentConfig(language="en")
                >>> async with VoiceAgentClient(api_key="your_api_key", config=config) as client:
                ...     # Client automatically connects and disconnects
                ...     await client.send_audio(audio_data)

            Using a preset (named):
                >>> from speechmatics.voice import VoiceAgentClient
                >>> client = VoiceAgentClient(
                ...     api_key="your_api_key",
                ...     url="wss://custom.endpoint.com/v2",
                ...     preset="adaptive"
                ... )

            Using a preset (utility class):
                >>> from speechmatics.voice import VoiceAgentClient, VoiceAgentConfigPreset
                >>> config=VoiceAgentConfigPreset.ADAPTIVE()
                >>> client = VoiceAgentClient(
                ...     api_key="your_api_key",
                ...     url="wss://custom.endpoint.com/v2",
                ...     config=config
                ... )

            Manual connection management:
                >>> client = VoiceAgentClient(api_key="your_api_key", config=config)
                >>> await client.connect()
                >>> # ... use client ...
                >>> await client.disconnect()

            Using environment variables:
                >>> import os
                >>> os.environ["SPEECHMATICS_API_KEY"] = "your_api_key"
                >>> async with VoiceAgentClient(config=VoiceAgentConfig(language="en")) as client:
                ...     await client.send_audio(audio_data)

            With custom endpoint:
                >>> client = VoiceAgentClient(
                ...     api_key="your_api_key",
                ...     url="wss://custom.endpoint.com/v2",
                ...     config=VoiceAgentConfig(language="en")
                ... )
        """

        # Default URL
        if not url:
            url = os.getenv("SPEECHMATICS_RT_URL") or "wss://eu2.rt.speechmatics.com/v2"

        # Initialize the client
        super().__init__(auth=auth, api_key=api_key, url=self._get_endpoint_url(url, app))

        # Logger
        self._logger = get_logger(__name__)

        # -------------------------------------
        # Client Configuration
        # -------------------------------------

        # Default to EXTERNAL if no config or preset string provided
        if config is None and preset is None:
            config = VoiceAgentConfigPreset.EXTERNAL()

        # Check for preset
        elif preset is not None:
            preset_config = VoiceAgentConfigPreset.load(preset)
            config = VoiceAgentConfigPreset._merge_configs(preset_config, config)

        # Process the config
        self._config, self._transcription_config, self._audio_format = self._prepare_config(config)

        # Connection status
        self._is_connected: bool = False
        self._is_ready_for_audio: bool = False
        self._closing_session: bool = False

        # Session info (updated on session created)
        self._client_session: ClientSessionInfo = ClientSessionInfo(
            config=self._config,
            session_id="NOT_SET",
            base_time=datetime.datetime.now(datetime.timezone.utc),
            language_pack_info=LanguagePackInfo.from_dict({}),
        )

        # -------------------------------------
        # Transcription Change Filter
        # -------------------------------------

        # Change filter to emit segments
        self._change_filter: list[AnnotationFlags] = [
            AnnotationFlags.NEW,
            AnnotationFlags.UPDATED_FINALS,
        ]

        # Full text has changed
        if self._config.transcription_update_preset == TranscriptionUpdatePreset.COMPLETE:
            self._change_filter.append(AnnotationFlags.UPDATED_FULL)
        # Full text and timing have changed
        elif self._config.transcription_update_preset == TranscriptionUpdatePreset.COMPLETE_PLUS_TIMING:
            self._change_filter.append(AnnotationFlags.UPDATED_FULL)
            self._change_filter.append(AnnotationFlags.UPDATED_WORD_TIMINGS)
        # Word content only has changed
        elif self._config.transcription_update_preset == TranscriptionUpdatePreset.WORDS:
            self._change_filter.append(AnnotationFlags.UPDATED_STRIPPED)
        # Word content and timing have changed
        elif self._config.transcription_update_preset == TranscriptionUpdatePreset.WORDS_PLUS_TIMING:
            self._change_filter.append(AnnotationFlags.UPDATED_STRIPPED)
            self._change_filter.append(AnnotationFlags.UPDATED_WORD_TIMINGS)
        # Timing only has changed
        elif self._config.transcription_update_preset == TranscriptionUpdatePreset.TIMING:
            self._change_filter.append(AnnotationFlags.UPDATED_WORD_TIMINGS)

        # STT message received queue
        self._stt_message_queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()
        self._stt_queue_task: Optional[asyncio.Task] = None

        # -------------------------------------
        # Session Timing
        # -------------------------------------

        self._total_time: float = 0
        self._total_bytes: int = 0
        self._last_ttfb: float = 0

        # -------------------------------------
        # Segment Tracking
        # -------------------------------------

        self._trim_before_time: float = 0
        self._fragment_idx: int = 0
        self._last_fragment_end_time: float = 0
        self._speech_fragments: list[SpeechFragment] = []
        self._speech_fragments_lock: asyncio.Lock = asyncio.Lock()
        self._current_view: Optional[SpeakerSegmentView] = None
        self._previous_view: Optional[SpeakerSegmentView] = None

        # -------------------------------------
        # VAD
        # -------------------------------------

        # Handlers
        self._uses_silero_vad: bool = False
        self._silero_detector: Optional[SileroVAD] = None

        # Silero VAD detector
        if self._config.vad_config and self._config.vad_config.enabled:
            if not SileroVAD.dependencies_available():
                self._logger.warning(SILERO_INSTALL_HINT)
            else:
                silero_detector = SileroVAD(
                    silence_duration=self._config.vad_config.silence_duration,
                    threshold=self._config.vad_config.threshold,
                    auto_init=True,
                    on_state_change=self._handle_silero_vad_result,
                )
                if silero_detector.model_exists():
                    self._silero_detector = silero_detector
                    self._uses_silero_vad = True
            if not self._uses_silero_vad:
                self._logger.warning("Silero model not available and VAD will be disabled.")

        # -------------------------------------
        # EOU / EOT
        # -------------------------------------

        # Handlers
        self._uses_smart_turn: bool = False
        self._smart_turn_detector: Optional[SmartTurnDetector] = None

        # Current turn
        self._turn_start_time: Optional[float] = None
        self._turn_active: bool = False

        # Smart turn cutoff time - filters late transcripts during finalization
        self._smart_turn_pending_cutoff: Optional[float] = None

        # Start turn detector if SMART_TURN requested
        if self._config.smart_turn_config and self._config.smart_turn_config.enabled:
            if not SmartTurnDetector.dependencies_available():
                self._logger.warning(SMART_TURN_INSTALL_HINT)
            else:
                smart_turn_detector = SmartTurnDetector(
                    auto_init=True, threshold=self._config.smart_turn_config.smart_turn_threshold
                )
                if smart_turn_detector.model_exists():
                    self._smart_turn_detector = smart_turn_detector
                    self._uses_smart_turn = True
            if not self._uses_smart_turn:
                self._logger.warning("Smart Turn model not available. Falling back to ADAPTIVE.")
                self._config.end_of_utterance_mode = EndOfUtteranceMode.ADAPTIVE

        # -------------------------------------
        # Turn / End of Utterance Handling
        # -------------------------------------

        # EOU mode
        self._eou_mode: EndOfUtteranceMode = self._config.end_of_utterance_mode

        # Handlers
        self._turn_handler: TurnTaskProcessor = TurnTaskProcessor(name="turn_handler", done_callback=self.finalize)
        self._eot_calculation_task: Optional[asyncio.Task] = None

        # Uses fixed EndOfUtterance message from STT
        self._uses_fixed_eou: bool = (
            self._eou_mode == EndOfUtteranceMode.FIXED
            and not self._silero_detector
            and not self._config.end_of_turn_config.use_forced_eou
        )

        # Uses ForceEndOfUtterance message
        self._uses_forced_eou: bool = not self._uses_fixed_eou
        self._forced_eou_active: bool = False
        self._last_forced_eou_latency: float = 0.0

        # Emit EOT prediction (uses _uses_forced_eou)
        self._uses_eot_prediction: bool = self._eou_mode not in [
            EndOfUtteranceMode.FIXED,
            EndOfUtteranceMode.EXTERNAL,
        ]

        # -------------------------------------
        # Diarization / Speakers
        # -------------------------------------

        self._session_speakers: dict[str, SessionSpeaker] = {}
        self._is_speaking: bool = False
        self._current_speaker: Optional[str] = None
        self._last_valid_partial_word_count: int = 0
        self._dz_enabled: bool = self._config.enable_diarization
        self._dz_config = self._config.speaker_config
        self._last_speak_start_time: Optional[float] = None
        self._last_speak_end_time: Optional[float] = None
        self._last_speak_end_latency: float = 0

        # -------------------------------------
        # Metrics
        # -------------------------------------

        self._metrics_emitter_interval: float = 5.0
        self._metrics_emitter_task: Optional[asyncio.Task] = None

        # -------------------------------------
        # Audio
        # -------------------------------------

        # Audio sampling info
        self._audio_sample_rate: int = self._audio_format.sample_rate
        self._audio_sample_width: int = {
            AudioEncoding.PCM_F32LE: 4,
            AudioEncoding.PCM_S16LE: 2,
        }.get(self._audio_format.encoding, 1)

        # Default audio buffer
        if not self._config.audio_buffer_length and (self._uses_smart_turn or self._uses_silero_vad):
            self._config.audio_buffer_length = 15.0

        # Audio buffer
        if self._config.audio_buffer_length > 0:
            self._audio_buffer: AudioBuffer = AudioBuffer(
                sample_rate=self._audio_format.sample_rate,
                frame_size=self._audio_format.chunk_size,
                sample_width=self._audio_sample_width,
                total_seconds=self._config.audio_buffer_length,
            )

        # Register handlers
        self._register_event_handlers()

    def _prepare_config(
        self, config: Optional[VoiceAgentConfig] = None
    ) -> tuple[VoiceAgentConfig, TranscriptionConfig, AudioFormat]:
        """Create a formatted STT transcription and audio config.

        Creates a transcription config object based on the service parameters. Aligns
        with the Speechmatics RT API transcription config.

        Args:
            config: Optional VoiceAgentConfig object to process.

        Returns:
            A tuple of (VoiceAgentConfig, TranscriptionConfig, AudioFormat).
        """

        # Default config
        if config is None:
            config = VoiceAgentConfig()

        # Transcription config
        transcription_config = TranscriptionConfig(
            language=config.language,
            domain=config.domain,
            output_locale=config.output_locale,
            operating_point=config.operating_point,
            diarization="speaker" if config.enable_diarization else None,
            enable_partials=True,
            enable_entities=config.enable_entities,
            max_delay=config.max_delay,
            max_delay_mode=config.max_delay_mode.value,
            audio_filtering_config={
                "volume_threshold": 0.0,
            },
        )

        # Merge in overrides
        if config.advanced_engine_control:
            for key, value in config.advanced_engine_control.items():
                setattr(transcription_config, key, value)

        # Additional vocab
        if config.additional_vocab:
            transcription_config.additional_vocab = [
                {
                    "content": e.content,
                    **({"sounds_like": e.sounds_like} if e.sounds_like else {}),
                }
                for e in config.additional_vocab
            ]

        # Diarization
        if config.enable_diarization:
            # List of known speakers
            dz_speakers: list[SpeakerIdentifier] = []
            if config.known_speakers:
                dz_speakers.extend(
                    [
                        SpeakerIdentifier(label=s.label, speaker_identifiers=s.speaker_identifiers)
                        for s in config.known_speakers
                    ]
                )

            # Diarization config
            transcription_config.speaker_diarization_config = SpeakerDiarizationConfig(
                speaker_sensitivity=config.speaker_sensitivity,
                prefer_current_speaker=config.prefer_current_speaker,
                max_speakers=config.max_speakers,
                speakers=dz_speakers or None,
            )

        # Fixed end of Utterance
        if bool(
            config.end_of_utterance_mode == EndOfUtteranceMode.FIXED and not config.end_of_turn_config.use_forced_eou
        ):
            transcription_config.conversation_config = ConversationConfig(
                end_of_utterance_silence_trigger=config.end_of_utterance_silence_trigger,
            )

        # Punctuation overrides
        if config.punctuation_overrides is not None:
            transcription_config.punctuation_overrides = config.punctuation_overrides

        # Configure the audio
        audio_format = AudioFormat(
            encoding=config.audio_encoding,
            sample_rate=config.sample_rate,
            chunk_size=config.chunk_size,
        )

        # Return the config objects
        return config, transcription_config, audio_format

    # ============================================================================
    # LIFECYCLE METHODS
    # ============================================================================

    async def connect(self) -> None:
        """Connect to the Speechmatics API.

        Establishes WebSocket connection and starts the transcription session.
        This must be called before sending audio.

        Raises:
            Exception: If connection fails.

        Examples:
            Manual connection:
                >>> client = VoiceAgentClient(api_key="your_api_key", config=config)
                >>> await client.connect()

            With event handlers:
                >>> @client.on("AddSegment")
                ... async def on_segment(message):
                ...     segments = message["segments"]
                ...     print(f"Received {len(segments)} segments")
                >>>
                >>> await client.connect()

            Using context manager (recommended):
                >>> async with VoiceAgentClient(api_key="key", config=config) as client:
                ...     # Client is automatically connected here
                ...     await client.send_audio(audio_data)
                ... # Automatically disconnected and cleaned up
        """

        # Check if we are already connected
        if self._is_connected:
            self._emit_message(
                ErrorMessage(
                    reason="Already connected",
                )
            )
            return

        # Update the closing session flag
        self._closing_session = False

        # Start the processor task
        self._stt_queue_task = asyncio.create_task(self._run_stt_queue())

        # Connect to API
        try:
            await self.start_session(
                transcription_config=self._transcription_config,
                audio_format=self._audio_format,
            )
            self._is_connected = True
            self._start_metrics_task()
        except Exception as e:
            self._logger.error(f"Exception: {e}")
            raise

    async def __aenter__(self) -> VoiceAgentClient:
        """Enter async context manager.

        Automatically connects to the Speechmatics API when entering the context.

        Returns:
            The connected VoiceAgentClient instance.

        Examples:
            >>> async with VoiceAgentClient(api_key="key", config=config) as client:
            ...     # Client is already connected here
            ...     await client.send_audio(audio_data)
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager.

        Automatically disconnects and cleans up resources when exiting the context.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect from the Speechmatics API.

        Closes the WebSocket connection and cleans up resources.

        Examples:
            Manual disconnect:
                >>> await client.connect()
                >>> # ... send audio ...
                >>> await client.disconnect()

            Using context manager (automatic):
                >>> async with VoiceAgentClient(api_key="key", config=config) as client:
                ...     # No need to call disconnect() - handled automatically
                ...     await client.send_audio(audio_data)
        """

        # Check if we are already connected
        if not self._is_connected:
            return

        # Update the closing session flag
        self._closing_session = True

        # Emit final segments
        await self._emit_segments(finalize=True, is_eou=True)

        # Emit final metrics
        self._emit_speaker_metrics()
        self._emit_metrics()

        # Stop audio and metrics tasks
        self._is_ready_for_audio = False
        self._stop_metrics_task()

        # end session
        try:
            await asyncio.wait_for(self.stop_session(), timeout=5.0)
        except Exception as e:
            self._logger.error(f"Error closing session: {e}")
        finally:
            self._is_connected = False

        # Stop end of turn-related tasks
        self._turn_handler.cancel_tasks()

        # Stop the STT queue task
        if self._stt_queue_task:
            self._stt_queue_task.cancel()
            try:
                await self._stt_queue_task
            except asyncio.CancelledError:
                pass
            self._stt_queue_task = None

    # ============================================================================
    # PUBLIC API METHODS
    # ============================================================================

    async def send_audio(self, payload: bytes) -> None:
        """Send an audio frame through the WebSocket.

        Args:
            payload: Audio data as bytes.

        Examples:
            Sending audio from a file:
                >>> import wave
                >>> with wave.open("audio.wav", "rb") as wav_file:
                ...     while True:
                ...         audio_chunk = wav_file.readframes(320)
                ...         if not audio_chunk:
                ...             break
                ...         await client.send_audio(audio_chunk)

            Sending audio from microphone:
                >>> import pyaudio
                >>> p = pyaudio.PyAudio()
                >>> stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True)
                >>> while True:
                ...     audio_data = stream.read(320)
                ...     await client.send_audio(audio_data)

            With async generator:
                >>> async for audio_chunk in audio_stream():
                ...     await client.send_audio(audio_chunk)
        """
        # Skip if not ready for audio
        if not self._is_ready_for_audio:
            return

        # Send to the AsyncClient
        try:
            await super().send_audio(payload)
        except TransportError as e:
            self._logger.warning(f"Error sending audio: {e}")
            self._emit_message(
                ErrorMessage(
                    reason="Transport error - connection being closed",
                )
            )
            await self.disconnect()
            return

        # Process with Silero VAD
        if self._silero_detector:
            asyncio.create_task(self._silero_detector.process_audio(payload))

        # Add to audio buffer (use put_bytes to handle variable chunk sizes)
        if self._config.audio_buffer_length > 0:
            await self._audio_buffer.put_bytes(payload)

        # Calculate the time (in seconds) for the payload
        if self._audio_format is not None:
            self._total_bytes += len(payload)
            self._total_time += len(payload) / self._audio_sample_rate / self._audio_sample_width

    def update_diarization_config(self, config: SpeakerFocusConfig) -> None:
        """Update the diarization configuration.

        You can update the speakers that needs to be focussed on or ignored during
        a session. The new config will overwrite the existing configuration and become
        active immediately.

        Args:
            config: The new diarization configuration.

        Examples:
            Focus on specific speakers:
                >>> from speechmatics.voice import SpeakerFocusConfig, SpeakerFocusMode
                >>> config = SpeakerFocusConfig(
                ...     focus_speakers=["speaker_1", "speaker_2"],
                ...     focus_mode=SpeakerFocusMode.RETAIN
                ... )
                >>> client.update_diarization_config(config)

            Ignore specific speakers:
                >>> config = SpeakerFocusConfig(
                ...     ignore_speakers=["speaker_3"],
                ...     focus_mode=SpeakerFocusMode.IGNORE
                ... )
                >>> client.update_diarization_config(config)

            Dynamic speaker management:
                >>> # Start with all speakers
                >>> await client.connect()
                >>> # Later, focus on main speaker
                >>> client.update_diarization_config(
                ...     SpeakerFocusConfig(focus_speakers=["main_speaker"])
                ... )
        """

        # Only allow updates if diarization is enabled
        if not self._config.enable_diarization:
            raise ValueError("Diarization is not enabled")

        # Update the diarization config
        self._dz_config = config

    # ============================================================================
    # PUBLIC UTTERANCE / TURN MANAGEMENT
    # ============================================================================

    def finalize(self, end_of_turn: bool = False) -> None:
        """Finalize segments.

        This function will emit segments in the buffer without any further checks
        on the contents of the segments.

        Args:
            end_of_turn: Whether to emit an end of turn message.
        """

        # Clear smart turn cutoff
        self._smart_turn_pending_cutoff = None

        # Current turn
        _turn_id = self._turn_handler.handler_id

        # Emit the finalize or use EndOfTurn on demand preview
        async def emit() -> None:
            """Wait for EndOfUtterance if needed, then emit segments."""

            # Forced end of utterance message (only when no speaker is detected)
            if self._config.end_of_turn_config.use_forced_eou:
                await self._await_forced_eou()

            # Check if the turn has changed
            if self._turn_handler.handler_id != _turn_id:
                return

            # Emit the segments
            self._stt_message_queue.put_nowait(lambda: self._emit_segments(finalize=True, is_eou=True))

        # Call async task (only if not already waiting for forced EOU)
        if not (self._config.end_of_turn_config.use_forced_eou and self._forced_eou_active):
            asyncio.create_task(emit())

    # ============================================================================
    # EVENT REGISTRATION & HANDLERS
    # ============================================================================

    def _register_event_handlers(self) -> None:
        """Register event handlers.

        Specific event handlers that we need to deal with. All other events
        from the STT API will be available to clients to use themselves.
        """

        # Recognition started event
        @self.once(ServerMessageType.RECOGNITION_STARTED)  # type: ignore[misc]
        def _evt_on_recognition_started(message: dict[str, Any]) -> None:
            self._is_ready_for_audio = True
            self._client_session = ClientSessionInfo(
                config=self._config,
                session_id=message.get("id", "UNKNOWN"),
                base_time=datetime.datetime.now(datetime.timezone.utc),
                language_pack_info=LanguagePackInfo.from_dict(message.get("language_pack_info", {})),
            )

        # Partial transcript event
        @self.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)  # type: ignore[misc]
        def _evt_on_partial_transcript(message: dict[str, Any]) -> None:
            if self._closing_session:
                return
            self._stt_message_queue.put_nowait(lambda: self._handle_transcript(message, is_final=False))

        # Final transcript event
        @self.on(ServerMessageType.ADD_TRANSCRIPT)  # type: ignore[misc]
        def _evt_on_final_transcript(message: dict[str, Any]) -> None:
            if self._closing_session:
                return
            self._stt_message_queue.put_nowait(lambda: self._handle_transcript(message, is_final=True))

        # End of Utterance (FIXED mode only)
        if self._uses_fixed_eou:

            @self.on(ServerMessageType.END_OF_UTTERANCE)  # type: ignore[misc]
            def _evt_on_end_of_utterance(message: dict[str, Any]) -> None:
                if self._closing_session:
                    return

                async def _trigger_end_of_turn() -> None:
                    self.finalize()

                self._stt_message_queue.put_nowait(_trigger_end_of_turn)

    def _emit_message(self, message: BaseMessage) -> None:
        """Emit a message to the client.

        This takes a BaseMessage class and emits it as a dictionary to the
        client.

        Args:
            message: The BaseMessage class message to emit.
        """

        # Forward to the emit() method
        self.emit(message.message, message.to_dict())

    def _emit_diagnostic_message(self, message: Union[str, dict[str, Any]]) -> None:
        """Emit a diagnostic message to the client."""
        if isinstance(message, str):
            message = {"msg": message}
        self.emit(AgentServerMessageType.DIAGNOSTICS, {"message": AgentServerMessageType.DIAGNOSTICS.value, **message})

    # ============================================================================
    # QUEUE PROCESSING
    # ============================================================================

    def _start_stt_queue(self) -> None:
        """Start the STT message queue."""
        self._stt_queue_task = asyncio.create_task(self._run_stt_queue())

    async def _run_stt_queue(self) -> None:
        """Run the STT message queue."""
        while True:
            try:
                callback = await self._stt_message_queue.get()

                if asyncio.iscoroutine(callback):
                    await callback
                elif asyncio.iscoroutinefunction(callback):
                    await callback()
                elif callable(callback):
                    result = callback()
                    if asyncio.iscoroutine(result):
                        await result

            except asyncio.CancelledError:
                self._logger.debug("STT queue task cancelled")
                return
            except RuntimeError:
                self._logger.debug("STT queue event loop closed")
                return
            except Exception:
                self._logger.warning("Exception in STT message queue", exc_info=True)

    def _stop_stt_queue(self) -> None:
        """Stop the STT message queue."""
        if self._stt_queue_task:
            self._stt_queue_task.cancel()

    # ============================================================================
    # METRICS
    # ============================================================================

    def _start_metrics_task(self) -> None:
        """Start the metrics task."""

        # Task to send metrics
        async def emit_metrics() -> None:
            # Tracker
            last_emission_time = self._total_time

            # Emit metrics
            while True:
                # Calculate when the next emission should occur
                next_emission_time = (
                    last_emission_time // self._metrics_emitter_interval + 1
                ) * self._metrics_emitter_interval

                # Check if there are any listeners for AgentServerMessageType.METRICS
                if not self.listeners(AgentServerMessageType.SESSION_METRICS):
                    await asyncio.sleep(self._metrics_emitter_interval)
                    last_emission_time = self._total_time
                    continue

                # Wait until we've actually reached that time
                while self._total_time < next_emission_time:
                    time_to_wait = next_emission_time - self._total_time
                    await asyncio.sleep(min(0.25, time_to_wait))

                # Update tracker
                last_emission_time = self._total_time

                # Emit metrics
                self._emit_metrics()

        # Trigger the task
        self._metrics_emitter_task = asyncio.create_task(emit_metrics())

    def _emit_metrics(self) -> None:
        """Emit metrics."""
        self._emit_message(
            SessionMetricsMessage(
                total_time=round(self._total_time, 1),
                total_time_str=time.strftime("%H:%M:%S", time.gmtime(self._total_time)),
                total_bytes=self._total_bytes,
                processing_time=round(self._last_ttfb, 3),
            )
        )

    def _stop_metrics_task(self) -> None:
        """Stop the metrics task."""
        if self._metrics_emitter_task:
            self._metrics_emitter_task.cancel()
            self._metrics_emitter_task = None

    def _calculate_ttfb(self, end_time: float) -> None:
        """Calculate the time to first text.

        The TTFB is calculated by taking the end time of the payload from the STT
        engine and then calculating the difference between the total time of bytes
        sent to the engine from the client.

        Args:
            end_time: The end time of the payload from the STT engine.
        """

        # Calculate the time difference (convert to ms)
        ttfb = self._total_time - end_time

        # Skip if zero or less
        if ttfb <= 0:
            return

        # Save TTFB and end time
        self._last_ttfb = ttfb

    def _calculate_speaker_metrics(
        self, partial_segments: list[SpeakerSegment], final_segments: list[SpeakerSegment]
    ) -> None:
        """Calculate the speaker metrics.

        Used to track the number of words per speaker. Only valid speakers are
        considered. Ignored speakers will be excluded. Total is past finals +
        new partials. The number _may_ go down if partials are removed or
        re-attribute to a different speaker.

        Args:
            partial_segments: The partial segments to calculate the speaker metrics for.
            final_segments: The final segments to calculate the speaker metrics for.
        """

        # Skip if not enabled
        if not self.listeners(AgentServerMessageType.SPEAKER_METRICS):
            return

        changes_detected = False

        # Process finalized words
        for seg in final_segments:
            for frag in seg.fragments:
                if frag.type_ == "word" and frag.speaker is not None:
                    # Initialize speaker if not exists
                    if frag.speaker not in self._session_speakers:
                        self._session_speakers[frag.speaker] = SessionSpeaker(speaker_id=frag.speaker)

                    speaker = self._session_speakers[frag.speaker]

                    # Update final word count
                    speaker.final_word_count += 1
                    speaker.last_heard = frag.end_time

                    # Update volume
                    if frag.volume is not None:
                        speaker.update_volume(frag.volume)

                    changes_detected = True

        # Reset word count to final count for all speakers before reprocessing partials
        for speaker in self._session_speakers.values():
            speaker.word_count = speaker.final_word_count

        # Process partial words (adds to the base final count)
        for seg in partial_segments:
            for frag in seg.fragments:
                if frag.type_ == "word" and frag.speaker is not None:
                    # Initialize speaker if not exists
                    if frag.speaker not in self._session_speakers:
                        self._session_speakers[frag.speaker] = SessionSpeaker(speaker_id=frag.speaker)
                        # Set baseline for new speaker from partials
                        self._session_speakers[frag.speaker].word_count = 0

                    speaker = self._session_speakers[frag.speaker]

                    # Increment total word count
                    speaker.word_count += 1
                    speaker.last_heard = frag.end_time

                    # Update volume
                    if frag.volume is not None:
                        speaker.update_volume(frag.volume)

                    changes_detected = True

        # Emit metrics if any changes occurred
        if changes_detected:
            self._emit_speaker_metrics()

    def _emit_speaker_metrics(self) -> None:
        """Emit speaker metrics."""
        self._emit_message(
            SpeakerMetricsMessage(
                speakers=list(self._session_speakers.values()),
            ),
        )

    # ============================================================================
    # TRANSCRIPT PROCESSING
    # ============================================================================

    async def _handle_transcript(self, message: dict[str, Any], is_final: bool) -> None:
        """Handle the partial and final transcript events (async).

        As `AddTranscript` messages are _always_ followed by `AddPartialTranscript` messages,
        we can skip processing. Also skip if there are no fragments in the buffer.

        Args:
            message: The new Partial or Final from the STT engine.
            is_final: Whether the data is final or partial.
        """

        # Add the speech fragments
        fragments_available = await self._add_speech_fragments(
            message=message,
            is_final=is_final,
        )

        # Skip if no fragments
        if not fragments_available:
            return

        # Process (only done with AddPartialTranscript, as they always immediately follow AddTranscript
        if not is_final:
            await self._process_speech_fragments(self._change_filter)

    async def _add_speech_fragments(self, message: dict[str, Any], is_final: bool = False) -> bool:
        """Takes a new Partial or Final from the STT engine.

        Accumulates it into the _speech_data list. As new final data is added, all
        partials are removed from the list.

        Note: If a known speaker is `__[A-Z0-9_]{2,}__`, then the words are skipped,
        as this is used to protect against self-interruption by the assistant or to
        block out specific known voices.

        Args:
            message: The new Partial or Final from the STT engine.
            is_final: Whether the data is final or partial.

        Returns:
            True if the speech fragments were updated, False otherwise.
        """

        async with self._speech_fragments_lock:
            # Parsed new speech data from the STT engine
            fragments: list[SpeechFragment] = []

            # Metadata
            metadata = message.get("metadata", {})
            payload_end_time = metadata.get("end_time", 0)

            # Iterate over the results in the payload
            for result in message.get("results", []):
                alt = result.get("alternatives", [{}])[0]
                if alt.get("content", None):
                    # Create the new fragment
                    fragment = SpeechFragment(
                        idx=self._next_fragment_id(),
                        start_time=result.get("start_time", 0),
                        end_time=result.get("end_time", 0),
                        language=alt.get("language", "en"),
                        direction=alt.get("direction", "ltr"),
                        type_=result.get("type", "word"),
                        is_eos=result.get("is_eos", False),
                        is_disfluency="disfluency" in alt.get("tags", []),
                        is_punctuation=result.get("type", "") == "punctuation",
                        is_final=is_final,
                        attaches_to=result.get("attaches_to", ""),
                        content=alt.get("content", ""),
                        speaker=alt.get("speaker", "UU"),
                        confidence=alt.get("confidence", 1.0),
                        volume=result.get("volume", None),
                        result={"final": is_final, **result},
                    )

                    # Check fragment is after trim time
                    if fragment.start_time < self._trim_before_time:
                        continue

                    # Speaker filtering
                    if fragment.speaker:
                        # Drop `__XX__` speakers
                        if re.match(r"^__[A-Z0-9_]{2,}__$", fragment.speaker):
                            continue

                        # Drop speakers not focussed on
                        if (
                            self._dz_config.focus_mode == SpeakerFocusMode.IGNORE
                            and self._dz_config.focus_speakers
                            and fragment.speaker not in self._dz_config.focus_speakers
                        ):
                            continue

                        # Drop ignored speakers
                        if self._dz_config.ignore_speakers and fragment.speaker in self._dz_config.ignore_speakers:
                            continue

                    # Add the fragment
                    fragments.append(fragment)

                    # Track the last fragment end time
                    self._last_fragment_end_time = max(self._last_fragment_end_time, fragment.end_time)

            # Evaluate for VAD (only done on partials)
            await self._vad_evaluation(fragments, is_final=is_final)

            # Fragments to retain
            retained_fragments = [
                frag for frag in self._speech_fragments if frag.is_final and frag.start_time >= self._trim_before_time
            ]

            # Re-structure the speech fragments
            self._speech_fragments = retained_fragments.copy()
            self._speech_fragments.extend(fragments)
            self._speech_fragments.sort(key=lambda x: x.idx)

            # Remove fragment at head that is for previous
            if (
                self._speech_fragments
                and self._speech_fragments[0].is_punctuation
                and self._speech_fragments[0].attaches_to == "previous"
            ):
                self._speech_fragments.pop(0)

            # Update TTFB (only if there are listeners)
            if not is_final:
                self._calculate_ttfb(end_time=payload_end_time)

            # Fragments available
            return len(self._speech_fragments) > 0

    # ============================================================================
    # SEGMENT PROCESSING & EMISSION
    # ============================================================================

    def _update_current_view(self) -> None:
        """Load the current view of the speech fragments."""
        self._current_view = SpeakerSegmentView(
            session=self._client_session,
            fragments=self._speech_fragments.copy(),
            focus_speakers=self._dz_config.focus_speakers,
        )

    async def _process_speech_fragments(self, change_filter: Optional[list[AnnotationFlags]] = None) -> None:
        """Process the speech fragments.

        Compares the current speech fragments against the last set of speech fragments.
        When segments are emitted, they are then removed from the buffer of fragments
        so the next comparison is based on the remaining + new fragments.

        Args:
            change_filter: Optional list of annotation flags to filter changes.
        """

        # Lock the speech fragments
        async with self._speech_fragments_lock:
            """Creates a new view of the fragments and compares against the last view."""

            # Create a view of the current segments
            self._update_current_view()

            # Check view exists
            if not self._current_view:
                return

            # Check we have at least one segment
            if self._current_view.segment_count == 0 or self._current_view.last_active_segment_index == -1:
                return

            # Create a view of segments to emit
            last_segment = self._current_view.segments[self._current_view.last_active_segment_index]

            # Trim the view
            self._current_view.trim(start_time=self._current_view.start_time, end_time=last_segment.end_time)

            # Compare previous view to this view
            if self._previous_view:
                changes = FragmentUtils.compare_views(self._client_session, self._previous_view, self._current_view)
            else:
                changes = AnnotationResult.from_flags(AnnotationFlags.NEW)

            # Update the previous view
            self._previous_view = self._current_view

        # Catch no changes
        if change_filter and not changes.any(*change_filter):
            return

        # Skip re-evaluation if transcripts are older than smart turn cutoff
        if self._smart_turn_pending_cutoff is not None and self._current_view:
            latest_end_time = max(
                (f.end_time for f in self._current_view.fragments if f.end_time is not None), default=0.0
            )

            # If all fragments end before or at the cutoff, skip re-evaluation
            if latest_end_time <= self._smart_turn_pending_cutoff:
                return

        # Turn prediction
        if self._uses_eot_prediction and self._uses_forced_eou and not self._forced_eou_active:

            async def fn() -> None:
                ttl = await self._calculate_finalize_delay()
                if ttl is not None:
                    self._turn_handler.update_timer(ttl)

            self._run_background_eot_calculation(fn, "speech_fragments")

        # Check for gaps
        # TODO - implement gap-filling
        # FragmentUtils.find_segment_pauses(self._client_session, self._current_view)

        # Emit the segments
        await self._emit_segments()

    async def _emit_segments(self, finalize: bool = False, is_eou: bool = False) -> None:
        """Emit segments to listeners.

        This function will emit segments in the view without any further checks
        on the contents of the segments. Any segments that end with a final / EOS
        will be emitted as finals and removed from the fragment buffer.

        Args:
            finalize: Whether to finalize all segments.
            is_eou: Whether the segments are being emitted after an end of utterance.
        """

        # Only process if we have segments in the buffer
        if self._current_view and self._current_view.segment_count == 0:
            if finalize:
                await self._emit_end_of_turn()
            return

        # Lock the speech fragments
        async with self._speech_fragments_lock:
            # Segments to emit
            final_segments: list[SpeakerSegment] = []
            partial_segments: list[SpeakerSegment] = []

            # Keep until end of turn (`ON_END_OF_TURN`)
            if not finalize and not self._config.speech_segment_config.emit_sentences:
                partial_segments = self._current_view.segments if self._current_view else []

            # Force finalize
            elif finalize:
                final_segments = self._current_view.segments if self._current_view else []

            # Split between finals and interim segments (`ON_FINALIZED_SENTENCE`)
            else:
                final_segments = [
                    s
                    for s in (self._current_view.segments if self._current_view else [])
                    if s.annotation.has(AnnotationFlags.ENDS_WITH_FINAL, AnnotationFlags.ENDS_WITH_EOS)
                ]
                partial_segments = [
                    s for s in (self._current_view.segments if self._current_view else []) if s not in final_segments
                ]

            # Remove partial segments that have no final fragments
            if not self._config.include_partials:
                partial_segments = [s for s in partial_segments if s.annotation.has(AnnotationFlags.HAS_FINAL)]

            # Emit finals first
            if final_segments:
                """Final segments are checked for end of sentence."""

                # Metadata for final segments uses actual start/end times of the segments being emitted
                final_metadata = MessageTimeMetadata(
                    start_time=final_segments[0].start_time,
                    end_time=final_segments[-1].end_time,
                    processing_time=round(self._last_ttfb, 3),
                )

                # Ensure final segment ends with EOS
                if self._config.speech_segment_config.add_trailing_eos:
                    last_segment = final_segments[-1]
                    last_fragment = last_segment.fragments[-1]
                    if not last_fragment.is_eos:
                        # Add new fragment
                        last_segment.fragments.append(
                            SpeechFragment(
                                idx=self._next_fragment_id(),
                                start_time=last_fragment.end_time,
                                end_time=last_fragment.end_time,
                                content=".",
                                attaches_to="previous",
                                is_eos=True,
                            )
                        )
                        # Update text
                        FragmentUtils.update_segment_text(
                            session=self._client_session,
                            segment=last_segment,
                        )

                # Mark the final segments as end of utterance
                if is_eou:
                    final_segments[-1].is_eou = True

                # Emit segments
                self._emit_message(
                    SegmentMessage(
                        message=AgentServerMessageType.ADD_SEGMENT,
                        segments=[
                            SegmentMessageSegment(
                                speaker_id=s.speaker_id,
                                is_active=s.is_active,
                                timestamp=s.timestamp,
                                language=s.language,
                                text=s.text,
                                annotation=s.annotation,
                                is_eou=s.is_eou,
                                fragments=(
                                    [SegmentMessageSegmentFragment(**f.__dict__) for f in s.fragments]
                                    if self._config.include_results
                                    else None
                                ),
                                metadata=MessageTimeMetadata(start_time=s.start_time, end_time=s.end_time),
                            )
                            for s in final_segments
                        ],
                        metadata=final_metadata,
                    ),
                )
                self._trim_before_time = final_segments[-1].end_time
                self._speech_fragments = [f for f in self._speech_fragments if f.start_time >= self._trim_before_time]

            # Emit interim segments (suppress when forced EOU is active)
            if partial_segments and not self._forced_eou_active:
                """Partial segments are emitted as is."""

                # Metadata for partial segments uses actual start/end times of the segments being emitted
                partial_metadata = MessageTimeMetadata(
                    start_time=partial_segments[0].start_time,
                    end_time=partial_segments[-1].end_time,
                    processing_time=round(self._last_ttfb, 3),
                )

                # Emit segments
                self._emit_message(
                    SegmentMessage(
                        message=AgentServerMessageType.ADD_PARTIAL_SEGMENT,
                        segments=[
                            SegmentMessageSegment(
                                speaker_id=s.speaker_id,
                                is_active=s.is_active,
                                timestamp=s.timestamp,
                                language=s.language,
                                text=s.text,
                                annotation=s.annotation,
                                fragments=(
                                    [SegmentMessageSegmentFragment(**f.__dict__) for f in s.fragments]
                                    if self._config.include_results
                                    else None
                                ),
                                metadata=MessageTimeMetadata(start_time=s.start_time, end_time=s.end_time),
                            )
                            for s in partial_segments
                        ],
                        metadata=partial_metadata,
                    ),
                )

            # Update the current view
            self._update_current_view()

            # Reset the turn start time
            if not self._turn_start_time and self._current_view:
                self._turn_start_time = self._current_view.start_time

            # Send updated speaker metrics
            self._calculate_speaker_metrics(partial_segments, final_segments)

        # Emit end of turn
        if finalize:
            await self._emit_end_of_turn()

    async def _emit_start_of_turn(self, event_time: float) -> None:
        """Emit the start of turn message."""

        # Flag as turn active
        self._turn_active = True

        # Emit
        self._emit_message(
            TurnStartEndResetMessage(
                message=AgentServerMessageType.START_OF_TURN,
                turn_id=self._turn_handler.handler_id,
                metadata=MessageTimeMetadata(
                    start_time=event_time,
                ),
            ),
        )

    async def _emit_end_of_turn(self) -> None:
        """Emit the end of turn message."""

        # Check if we have a previous view
        if not self._previous_view or not self._turn_active:
            return

        # Flag as turn active
        self._turn_active = False

        # Metadata (for LAST view)
        metadata = MessageTimeMetadata(start_time=self._turn_start_time, end_time=self._previous_view.end_time)

        # Emit
        self._emit_message(
            TurnStartEndResetMessage(
                message=AgentServerMessageType.END_OF_TURN,
                turn_id=self._turn_handler.handler_id,
                metadata=metadata,
            ),
        )

        # Stop the EOT handler
        self._turn_handler.complete_handler()

        # Reset the previous view
        self._previous_view = None
        self._turn_start_time = None

    # ============================================================================
    # TURN DETECTION & FINALIZATION
    # ============================================================================

    def _run_background_eot_calculation(self, fn: Callable, source: Optional[str] = None) -> None:
        """Run the calculation async."""

        # Existing task takes precedence
        if self._eot_calculation_task and not self._eot_calculation_task.done():
            return

        # Create new task
        self._eot_calculation_task = asyncio.create_task(fn())

    async def _calculate_fixed_finalize_delay(self) -> Optional[float]:
        """Will return the end of utterance delay as a default."""

        # Delay defined in config
        delay = self._config.end_of_utterance_silence_trigger

        # Adjust to compensate for known latencies
        delay = delay - self._last_forced_eou_latency - self._last_speak_end_latency

        # Emit prediction message
        self._emit_message(
            TurnPredictionMessage(
                turn_id=self._turn_handler.handler_id,
                metadata=TurnPredictionMetadata(
                    ttl=delay,
                    reasons=["fixed_eou"],
                ),
            ),
        )

        # Return the delay
        return delay

    async def _calculate_finalize_delay(
        self,
        annotation: Optional[AnnotationResult] = None,
    ) -> Optional[float]:
        """Calculate the delay before finalizing / end of turn.

        Process the most recent segment and view to determine how long to delay before finalizing
        the segments to the client. Checks for disfluencies, speech speed, end of sentence markers,
        and smart turn predictions to calculate appropriate delay.

        Args:
            annotations: The annotations to include for evaluation.

        Returns:
            Optional[float]: The delay before finalizing / end of turn.
        """

        # Get the current view or previous view with active segments
        view = (
            self._current_view
            if self._current_view and self._current_view.last_active_segment_index > -1
            else self._previous_view
        )

        # Skip if view doesn't exist
        if not view:
            return None

        # If FIXED EOU mode, use the fixed EOU delay
        if self._eou_mode == EndOfUtteranceMode.FIXED:
            return await self._calculate_fixed_finalize_delay()

        # Get last active segment
        last_active_segment_index = view.last_active_segment_index
        last_active_segment = view.segments[last_active_segment_index] if last_active_segment_index > -1 else None

        # Track penalty multipliers and reasons
        reasons: list[tuple[float, str]] = []
        annotation = annotation or AnnotationResult()

        # VAD enabled
        if self._silero_detector:
            annotation.add(AnnotationFlags.VAD_ACTIVE)
        else:
            annotation.add(AnnotationFlags.VAD_INACTIVE)

        # Smart Turn enabled
        if self._smart_turn_detector:
            annotation.add(AnnotationFlags.SMART_TURN_ACTIVE)
        else:
            annotation.add(AnnotationFlags.SMART_TURN_INACTIVE)

        # Result to validate against
        if last_active_segment:
            annotation.add(*[AnnotationFlags(flag) for flag in last_active_segment.annotation])

        # Apply penalties based on last active segment annotations
        if len(annotation) > 0:
            for p in self._config.end_of_turn_config.penalties:
                description = "__".join(p.annotation)
                has_annotation = annotation.has(*p.annotation)
                if (not p.is_not and has_annotation) or (p.is_not and not has_annotation):
                    reason = f"not__{description}" if p.is_not else description
                    reasons.append((p.penalty, reason))

        # Calculate final multiplier (compound multiplication)
        multiplier = self._config.end_of_turn_config.base_multiplier
        for penalty, _ in reasons:
            multiplier *= penalty

        # Calculate delay with minimum of 25ms
        delay = round(self._config.end_of_utterance_silence_trigger * multiplier, 3)

        # Trim off the most recent forced EOU delay if we're in forced EOU mode
        if self._uses_forced_eou:
            delay -= self._last_forced_eou_latency

        # Clamp to max delay and adjust for TTFB
        clamped_delay = min(delay, self._config.end_of_utterance_max_delay)
        finalize_delay = max(clamped_delay - self._last_ttfb, self._config.end_of_turn_config.min_end_of_turn_delay)

        # Emit prediction message
        self._emit_message(
            TurnPredictionMessage(
                turn_id=self._turn_handler.handler_id,
                metadata=TurnPredictionMetadata(
                    ttl=round(finalize_delay, 2),
                    reasons=[reason for _, reason in reasons],
                ),
            ),
        )

        # Return the calculated delay
        return finalize_delay

    async def _eot_prediction(
        self,
        end_time: Optional[float] = None,
        speaker: Optional[str] = None,
        annotation: Optional[AnnotationResult] = None,
    ) -> float:
        """Handle end of turn prediction."""

        # Initialize the annotation
        annotation = annotation or AnnotationResult()

        # Wait for Smart Turn result
        if self._smart_turn_detector and end_time is not None:
            result = await self._smart_turn_prediction(end_time, self._config.language, speaker=speaker)
            if result.prediction:
                annotation.add(AnnotationFlags.SMART_TURN_TRUE)
            else:
                annotation.add(AnnotationFlags.SMART_TURN_FALSE)

        # Create a new task to evaluate the finalize delay
        delay = await self._calculate_finalize_delay(annotation=annotation)

        # Return the result
        return max(delay or 0, self._config.end_of_turn_config.min_end_of_turn_delay)

    async def _smart_turn_prediction(
        self, end_time: float, language: str, start_time: float = 0.0, speaker: Optional[str] = None
    ) -> SmartTurnPredictionResult:
        """Predict when to emit the end of turn.

        This will give an acoustic prediction of when the turn has completed using
        the ONNX model to look for vocal intonation and hints.

        Args:
            end_time: The end time of the last active segment.
            language: The language of the audio.

        Returns:
            bool: Whether the turn has completed.
        """

        # Check we have smart turn enabled
        if not self._smart_turn_detector or not self._config.smart_turn_config:
            return SmartTurnPredictionResult(error="Smart turn is not enabled")

        # Calculate the times
        start_time = max(start_time, end_time - self._config.smart_turn_config.max_audio_length)
        total_time = self._total_time

        # Find the start / end times for the current speaker for this turn ...
        if self._current_view:
            """Extract the audio for this speaker only."""

            # Filter segments that match the current speaker
            speaker_segments: list[SpeakerSegment] = [
                seg for seg in self._current_view.segments if seg.speaker_id == speaker
            ]

            # Get the LAST segment
            if speaker_segments:
                start_time = speaker_segments[-1].start_time

        # Get audio slice (add small margin of 100ms to the end of the audio)
        segment_audio = await self._audio_buffer.get_frames(start_time=start_time, end_time=end_time)

        # Evaluate
        prediction = await self._smart_turn_detector.predict(
            segment_audio,
            language=language,
            sample_rate=self._audio_sample_rate,
            sample_width=self._audio_sample_width,
        )

        # Metadata
        metadata = {
            "start_time": round(start_time, 3),
            "end_time": round(end_time, 3),
            "language": language,
            "speaker_id": speaker,
            "total_time": round(total_time, 3),
        }

        # Emit smart turn info
        self.emit(
            AgentServerMessageType.SMART_TURN_RESULT,
            {
                "message": AgentServerMessageType.SMART_TURN_RESULT.value,
                "prediction": prediction.to_dict(),
                "metadata": metadata,
            },
        )

        # Return the prediction
        return prediction

    async def _await_forced_eou(self, timeout: float = 1.0) -> None:
        """Await the forced end of utterance."""

        # Received EOU
        eou_received: asyncio.Event = asyncio.Event()

        # Add listener
        self.once(AgentServerMessageType.END_OF_UTTERANCE, lambda message: eou_received.set())

        # Trigger EOU message
        self._emit_diagnostic_message("ForceEndOfUtterance sent - waiting for EndOfUtterance")

        # Wait for EOU
        try:
            # Track the start time
            start_time = time.time()
            self._forced_eou_active = True

            # Send the force EOU and wait for the response
            await self.force_end_of_utterance()
            await asyncio.wait_for(eou_received.wait(), timeout=timeout)

            # Record the latency
            self._last_forced_eou_latency = time.time() - start_time
            self._emit_diagnostic_message(f"EndOfUtterance received after {self._last_forced_eou_latency:.3f}s")

        except asyncio.TimeoutError:
            pass
        finally:
            self._forced_eou_active = False

    # ============================================================================
    # VAD (VOICE ACTIVITY DETECTION) / SPEAKER DETECTION
    # ============================================================================

    async def _vad_evaluation(self, fragments: list[SpeechFragment], is_final: bool) -> None:
        """Emit a VAD event.

        This will emit `SPEAKER_STARTED` and `SPEAKER_ENDED` events to the client and is
        based on valid transcription for active speakers. Ignored or speakers not in
        focus will not be considered an active participant.

        Args:
            fragments: The list of fragments to use for evaluation.
            is_final: Whether the fragments are final.
        """

        # Filter fragments for valid speakers, if required
        if self._dz_enabled and self._dz_config.focus_speakers:
            fragments = [f for f in fragments if f.speaker in self._dz_config.focus_speakers]

        # Find partial and final words
        words = [f for f in fragments if f.type_ == "word"]

        # Check if we have any new words
        has_words = len(words) > 0

        # Handle finals
        if is_final:
            """Check for finals without partials.

            When a forced end of utterance is used, the transcription may skip partials
            and go straight to finals. In this case, we need to check if we had any partials
            last time and if not, we need to assume we have a new speaker.
            """

            # Check if transcript went straight to finals (typical with forced end of utterance)
            if not self._is_speaking and has_words and self._last_valid_partial_word_count == 0:
                # Track the current speaker
                self._current_speaker = words[0].speaker
                self._is_speaking = True

                # Emit speaker started event
                await self._handle_speaker_started(self._current_speaker, words[0].start_time)

            # No further processing needed
            return

        # Track partial count
        self._last_valid_partial_word_count = len(words)

        # Current states
        current_is_speaking = self._is_speaking
        current_speaker = self._current_speaker

        # Establish the speaker from latest partials
        latest_speaker = words[-1].speaker if has_words else current_speaker

        # Determine if the speaker has changed (and we have a speaker)
        speaker_changed = latest_speaker != current_speaker and current_speaker is not None

        # Start / end times (earliest and latest)
        speaker_start_time = words[0].start_time if has_words else None
        speaker_end_time = self._last_fragment_end_time

        # If diarization is enabled, indicate speaker switching
        if self._dz_enabled and latest_speaker is not None:
            """When enabled, we send a speech events if the speaker has changed.

            This will emit a SPEAKER_ENDED for the previous speaker and a SPEAKER_STARTED
            for the new speaker.

            For any client that wishes to show _which_ speaker is speaking, this will
            emit events to indicate when speakers switch.
            """

            # Check if speaker is different to the current speaker
            if current_is_speaking and speaker_changed:
                self._emit_message(
                    SpeakerStatusMessage(
                        message=AgentServerMessageType.SPEAKER_ENDED,
                        speaker_id=current_speaker,
                        is_active=False,
                        time=speaker_end_time,
                    ),
                )
                self._emit_message(
                    SpeakerStatusMessage(
                        message=AgentServerMessageType.SPEAKER_STARTED,
                        speaker_id=latest_speaker,
                        is_active=True,
                        time=speaker_end_time,
                    ),
                )
                self._last_speak_start_time = speaker_end_time

        # Update current speaker
        self._current_speaker = latest_speaker

        # No further processing if we have no new fragments and we are not speaking
        if has_words == current_is_speaking:
            return

        # Update speaking state
        self._is_speaking = not current_is_speaking

        # Event time
        event_time = speaker_start_time if self._is_speaking else speaker_end_time

        # Skip if no event time
        if event_time is None:
            return

        # Speaker events
        if self._is_speaking:
            await self._handle_speaker_started(latest_speaker, event_time)
        else:
            await self._handle_speaker_stopped(latest_speaker, speaker_end_time)

    def _handle_silero_vad_result(self, result: SileroVADResult) -> None:
        """Handle VAD state change events.

        Args:
            result: VAD result containing state change information.
        """

        # Time of event
        event_time = self._total_time

        # Create the message
        message = VADStatusMessage(
            is_speech=result.is_speech,
            probability=result.probability,
            transition_duration_ms=result.transition_duration_ms,
            metadata=MessageTimeMetadata(
                start_time=round(max(0, event_time - 8), 4),
                end_time=round(event_time, 4),
            ),
        )

        # Emit VAD status message
        self._emit_message(message)

        # Create the annotation
        annotation = AnnotationResult()

        # VAD annotation
        if result.speech_ended:
            annotation.add(AnnotationFlags.VAD_STOPPED)
        else:
            annotation.add(AnnotationFlags.VAD_STARTED)

        # If speech has ended, we need to predict the end of turn
        if result.speech_ended and self._uses_eot_prediction:
            """VAD-based end of turn prediction."""

            # Set cutoff to prevent late transcripts from cancelling finalization
            self._smart_turn_pending_cutoff = event_time

            async def fn() -> None:
                ttl = await self._eot_prediction(
                    end_time=event_time, speaker=self._current_speaker, annotation=annotation
                )
                self._turn_handler.update_timer(ttl)

            self._run_background_eot_calculation(fn, "silero_vad")

    async def _handle_speaker_started(self, speaker: Optional[str], event_time: float) -> None:
        """Reset timers when a new speaker starts speaking after silence."""

        # Clear smart turn cutoff for new speech
        self._smart_turn_pending_cutoff = None

        # Update last speak start time
        self._last_speak_start_time = event_time

        # Emit start of turn (not when using EXTERNAL)
        if self._is_speaking and not self._turn_active:
            await self._emit_start_of_turn(event_time)

        # Update the turn handler
        if self._uses_forced_eou:
            self._turn_handler.reset()

        # Emit the event
        self._emit_message(
            SpeakerStatusMessage(
                message=AgentServerMessageType.SPEAKER_STARTED,
                speaker_id=speaker,
                is_active=True,
                time=event_time,
            ),
        )

        # Reset the handlers
        self._turn_handler.reset()

    async def _handle_speaker_stopped(self, speaker: Optional[str], event_time: float) -> None:
        """Reset the current speaker and do smart turn detection (if enabled)."""

        # Update last speak end time
        self._last_speak_end_time = event_time
        self._last_speak_end_latency = self._total_time - event_time

        # Turn prediction
        if self._uses_eot_prediction and not self._forced_eou_active:

            async def fn() -> None:
                ttl = await self._eot_prediction(event_time, speaker)
                self._turn_handler.update_timer(ttl)

            self._run_background_eot_calculation(fn, "speaker_stopped")

        # Emit the event
        self._emit_message(
            SpeakerStatusMessage(
                message=AgentServerMessageType.SPEAKER_ENDED,
                speaker_id=speaker,
                is_active=False,
                time=event_time,
            ),
        )

        # Reset current speaker
        self._current_speaker = None

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _next_fragment_id(self) -> int:
        """Return the next fragment ID."""
        self._fragment_idx += 10
        return self._fragment_idx

    def _get_endpoint_url(self, url: str, app: Optional[str] = None) -> str:
        """Format the endpoint URL with the SDK and app versions.

        Args:
            url: The base URL for the endpoint.
            app: The application name to use in the endpoint URL.

        Returns:
            str: The formatted endpoint URL.
        """

        # Parse the URL to extract existing query parameters
        parsed = urlparse(url)

        # Extract existing params into a dict of lists, keeping params without values
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Use the provided app name, or fallback to existing value, or use the default string
        existing_app = params.get("sm-app", [None])[0]
        app_name = app or existing_app or f"voice-sdk/{__version__}"
        params["sm-app"] = [app_name]
        params["sm-voice-sdk"] = [__version__]

        # Re-encode the query string and reconstruct
        updated_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=updated_query))
