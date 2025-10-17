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
from urllib.parse import urlencode

from speechmatics.rt import AsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import ConversationConfig
from speechmatics.rt import ServerMessageType
from speechmatics.rt import SpeakerDiarizationConfig
from speechmatics.rt import SpeakerIdentifier
from speechmatics.rt import TranscriptionConfig

from . import __version__
from ._audio import AudioBuffer
from ._logging import get_logger
from ._models import AgentClientMessageType
from ._models import AgentServerMessageType
from ._models import AnnotationFlags
from ._models import AnnotationResult
from ._models import ClientSessionInfo
from ._models import EndOfUtteranceMode
from ._models import LanguagePackInfo
from ._models import SessionSpeaker
from ._models import SpeakerFocusConfig
from ._models import SpeakerFocusMode
from ._models import SpeakerSegmentView
from ._models import SpeakerVADStatus
from ._models import SpeechFragment
from ._models import SpeechSegmentEmitMode
from ._models import TranscriptionUpdatePreset
from ._models import VoiceAgentConfig
from ._smart_turn import SMART_TURN_INSTALL_HINT
from ._smart_turn import SmartTurnDetector
from ._smart_turn import SmartTurnPredictionResult
from ._turn import TurnTaskProcessor
from ._utils import FragmentUtils

DEBUG_MORE = os.getenv("SPEECHMATICS_DEBUG_MORE", "0").lower() in ["1", "true"]


if DEBUG_MORE:
    import json


class VoiceAgentClient(AsyncClient):
    """Voice Agent client.

    This class extends the AsyncClient class from the Speechmatics Real-Time SDK
    and provides additional functionality for processing partial and final
    transcription from the STT engine into accumulated transcriptions with
    flags to indicate changes between messages, etc.
    """

    # ============================================================================
    # INITIALISATION & CONFIGURATION
    # ============================================================================

    def __init__(
        self,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        app: Optional[str] = None,
        config: Optional[VoiceAgentConfig] = None,
    ):
        """Initialize the Voice Agent client.

        Args:
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: REST API endpoint URL. If None, uses SPEECHMATICS_RT_URL env var
                 or defaults to production endpoint.
            app: Optional application name to use in the endpoint URL.
            config: Optional voice agent configuration.

        Examples:
            Recommended - using context manager:
                >>> from speechmatics.voice import VoiceAgentClient, VoiceAgentConfig
                >>> config = VoiceAgentConfig(language="en")
                >>> async with VoiceAgentClient(api_key="your_api_key", config=config) as client:
                ...     # Client automatically connects and disconnects
                ...     await client.send_audio(audio_data)

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
        super().__init__(api_key=api_key, url=self._get_endpoint_url(url, app))

        # Logger
        self._logger = get_logger(__name__)

        # Process the config
        self._config, self._transcription_config, self._audio_format = self._prepare_config(config)

        # Connection status
        self._is_connected: bool = False
        self._is_ready_for_audio: bool = False

        # Session info (updated on session created)
        self._client_session: ClientSessionInfo = ClientSessionInfo(
            config=self._config,
            session_id="NOT_SET",
            base_time=datetime.datetime.now(datetime.timezone.utc),
            language_pack_info=LanguagePackInfo.model_validate({}),
        )

        # Change filter to emit segments
        self._change_filter: list[AnnotationFlags] = [AnnotationFlags.NEW]
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

        # Timing info
        self._total_time: float = 0
        self._total_bytes: int = 0

        # TTFB metrics
        self._last_ttfb_time: Optional[float] = None
        self._last_ttfb: float = 0

        # Time to disregard speech fragments before
        self._trim_before_time: float = 0

        # Current utterance speech data
        self._fragment_idx: int = 0
        self._speech_fragments: list[SpeechFragment] = []
        self._speech_fragments_lock: asyncio.Lock = asyncio.Lock()
        self._current_view: Optional[SpeakerSegmentView] = None
        self._previous_view: Optional[SpeakerSegmentView] = None
        self._turn_start_time: Optional[float] = None

        # Speaking states
        self._session_speakers: dict[str, SessionSpeaker] = {}
        self._is_speaking: bool = False
        self._current_speaker: Optional[str] = None
        self._last_fragment_end_time: float = 0

        # Turn detection
        self._end_of_turn_handler: TurnTaskProcessor = TurnTaskProcessor(
            name="eot_handler", done_callback=self.finalize
        )
        self._turn_detector: Optional[SmartTurnDetector] = None

        # Start turn detector if SMART_TURN requested
        if self._config.end_of_utterance_mode == EndOfUtteranceMode.SMART_TURN:
            eou_mode_ok: bool = False
            if not SmartTurnDetector.dependencies_available():
                self._logger.warning(SMART_TURN_INSTALL_HINT)
            else:
                detector = SmartTurnDetector(
                    auto_init=True,
                    threshold=self._config.smart_turn_config.smart_turn_threshold,
                )
                if detector.model_exists():
                    self._turn_detector = detector
                    self._config.smart_turn_config.audio_buffer_length = 10.0
                    eou_mode_ok = True
            if not eou_mode_ok:
                self._logger.warning("Smart Turn model not available. Falling back to ADAPTIVE.")
                self._config.end_of_utterance_mode = EndOfUtteranceMode.ADAPTIVE

        # Diarization / speaker focus
        self._end_of_utterance_mode: EndOfUtteranceMode = self._config.end_of_utterance_mode
        self._end_of_utterance_delay: float = self._config.end_of_utterance_silence_trigger
        self._dz_enabled: bool = self._config.enable_diarization
        self._dz_config = self._config.speaker_config

        # Metrics emitter task
        self._metrics_emitter_interval: float = 10.0
        self._metrics_emitter_task: Optional[asyncio.Task] = None

        # Audio sampling info
        self._audio_sample_rate: int = self._audio_format.sample_rate
        self._audio_sample_width: int = {
            AudioEncoding.PCM_F32LE: 4,
            AudioEncoding.PCM_S16LE: 2,
        }.get(self._audio_format.encoding, 1)

        # Audio buffer
        if self._config.smart_turn_config.audio_buffer_length > 0:
            self._audio_buffer: AudioBuffer = AudioBuffer(
                sample_rate=self._audio_format.sample_rate,
                frame_size=self._audio_format.chunk_size,
                total_seconds=self._config.smart_turn_config.audio_buffer_length,
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
            max_delay=config.max_delay,
        )

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

        # End of Utterance (for fixed)
        if config.end_of_utterance_silence_trigger and config.end_of_utterance_mode == EndOfUtteranceMode.FIXED:
            transcription_config.conversation_config = ConversationConfig(
                end_of_utterance_silence_trigger=config.end_of_utterance_silence_trigger,
            )

        # Punctuation overrides
        if config.punctuation_overrides:
            transcription_config.punctuation_overrides = config.punctuation_overrides

        # Configure the audio
        audio_format = AudioFormat(
            encoding=config.audio_encoding,
            sample_rate=config.sample_rate,
            chunk_size=320,
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
            self.emit(
                AgentServerMessageType.ERROR,
                {"message": AgentServerMessageType.ERROR.value, "reason": "Already connected"},
            )
            return

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

        # Stop audio and metrics tasks
        self._is_ready_for_audio = False
        self._stop_metrics_task()

        # end session
        try:
            await self.stop_session()
        except Exception as e:
            self._logger.error(f"Error closing session: {e}")
        finally:
            self._is_connected = False

        # Stop end of turn-related tasks
        self._end_of_turn_handler.cancel_tasks()

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
        await super().send_audio(payload)

        # Add to audio buffer (use put_bytes to handle variable chunk sizes)
        if self._config.smart_turn_config.audio_buffer_length > 0:
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
        self._dz_config = config

    def finalize(self, ttl: Optional[float] = None) -> None:
        """Finalize segments.

        This function will emit segments in the buffer without any further checks
        on the contents of the segments. If the ttl is set to zero, then finalization
        will be forced through without yielding for any remaining STT messages.

        Args:
            ttl: Optional delay before finalizing partial segments.

        Examples:
            Immediate finalization:
                >>> # Force finalization of current segments
                >>> client.finalize(ttl=0)

            Delayed finalization:
                >>> # Wait 0.5 seconds before finalizing
                >>> client.finalize(ttl=0.5)
        """

        # Emit the finalize or use EndOfTurn on demand preview
        async def emit() -> None:
            if ttl is not None and ttl > 0:
                await asyncio.sleep(ttl)
            if self._config.enable_preview_features:
                await self.send_message({"message": AgentClientMessageType.FINALIZE_TURN})
            else:
                await self._emit_segments(finalize=True, end_of_turn=True)

        # Add to queue
        self._stt_message_queue.put_nowait(emit)

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
            if DEBUG_MORE:
                self._logger.debug(json.dumps(message))
            self._is_ready_for_audio = True
            self._client_session = ClientSessionInfo(
                config=self._config,
                session_id=message.get("id", "UNKNOWN"),
                base_time=datetime.datetime.now(datetime.timezone.utc),
                language_pack_info=LanguagePackInfo.model_validate(message.get("language_pack_info", {})),
            )

        # Partial transcript event
        @self.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)  # type: ignore[misc]
        def _evt_on_partial_transcript(message: dict[str, Any]) -> None:
            if DEBUG_MORE:
                self._logger.debug(json.dumps(message))

            async def _handle() -> None:
                await self._handle_transcript(message, is_final=False)

            self._stt_message_queue.put_nowait(_handle)

        # Final transcript event
        @self.on(ServerMessageType.ADD_TRANSCRIPT)  # type: ignore[misc]
        def _evt_on_final_transcript(message: dict[str, Any]) -> None:
            if DEBUG_MORE:
                self._logger.debug(json.dumps(message))

            async def _handle() -> None:
                await self._handle_transcript(message, is_final=True)

            self._stt_message_queue.put_nowait(_handle)

        # End of utterance event
        @self.on(ServerMessageType.END_OF_UTTERANCE)  # type: ignore[misc]
        def _evt_on_end_of_utterance(message: dict[str, Any]) -> None:
            if DEBUG_MORE:
                self._logger.debug(json.dumps(message))

            async def _handle() -> None:
                await self._emit_segments(finalize=True, end_of_turn=True)

            self._stt_message_queue.put_nowait(_handle)

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
            while True:
                # Interval between emitting metrics
                await asyncio.sleep(self._metrics_emitter_interval)

                # Check if there are any listeners for AgentServerMessageType.METRICS
                if not self.listeners(AgentServerMessageType.METRICS):
                    break

                # Calculations
                time_s = round(self._total_time, 3)

                # Emit metrics
                self.emit(
                    AgentServerMessageType.METRICS,
                    {
                        "message": AgentServerMessageType.METRICS.value,
                        "total_time": time_s,
                        "total_time_str": time.strftime("%H:%M:%S", time.gmtime(time_s)),
                        "total_bytes": self._total_bytes,
                        "last_ttfb": self._last_ttfb,
                    },
                )

        # Trigger the task
        self._metrics_emitter_task = asyncio.create_task(emit_metrics())

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
        # Skip if no fragments are words
        if len(self._speech_fragments) == 0 or all(f.type_ != "word" for f in self._speech_fragments):
            return

        # Get start of the first fragment
        fragments_start_time = self._speech_fragments[0].start_time

        # Skip if no partial word or if we have already calculated the TTFB for this word
        if self._last_ttfb_time and fragments_start_time <= self._last_ttfb_time:
            return

        # Calculate the time difference (convert to ms)
        ttfb = (self._total_time - end_time) * 1000.0

        # Skip if zero or less
        if ttfb <= 0:
            return

        # Save TTFB and end time
        self._last_ttfb = ttfb
        self._last_ttfb_time = end_time

        # Emit the TTFB
        self.emit(
            AgentServerMessageType.TTFB_METRICS,
            {
                "message": AgentServerMessageType.TTFB_METRICS.value,
                "ttfb": self._last_ttfb,
            },
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

        # Process (only done with non-finals)
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
            payload_start_time = metadata.get("start_time", 0)
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
                        speaker=alt.get("speaker", None),
                        confidence=alt.get("confidence", 1.0),
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

            # Evaluate for VAD (only done on partials)
            if not is_final:
                self._vad_evaluation(fragments)

            # Debug the fragments
            if DEBUG_MORE:
                debug_payload = {
                    "final": is_final,
                    "start_time": payload_start_time,
                    "end_time": payload_end_time,
                    "keeping": [f.content for f in retained_fragments],
                    "adding": [f.content for f in fragments],
                    "transcript": metadata.get("transcript", ""),
                    "full": [[f.content, f.start_time, f.end_time, f.is_final] for f in self._speech_fragments],
                }
                self._logger.debug(json.dumps(debug_payload))

            # Update TTFB
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

        # Emit the segments
        await self._emit_segments()

    async def _emit_segments(self, finalize: bool = False, end_of_turn: bool = False) -> None:
        """Emit segments to listeners.

        This function will emit segments in the view without any further checks
        on the contents of the segments. Any segments that end with a final / EOS
        will be emitted as finals and removed from the fragment buffer.

        Args:
            finalize: Whether to finalize all segments.
            end_of_turn: Whether to emit an end of turn event.
        """

        # Lock the speech fragments
        if self._current_view and self._current_view.segment_count > 0:
            async with self._speech_fragments_lock:
                # Force finalize
                if finalize:
                    final_segments = self._current_view.segments
                    interim_segments = []

                # Split between finals and interim segments (`ON_FINALIZED_SENTENCE` or `ON_SPEAKER_ENDED`)
                elif self._config.speech_segment_config.emit_mode in [
                    SpeechSegmentEmitMode.ON_FINALIZED_SENTENCE,
                    SpeechSegmentEmitMode.ON_SPEAKER_ENDED,
                ]:
                    final_segments = [
                        s
                        for s in self._current_view.segments
                        if s.annotation.has(AnnotationFlags.ENDS_WITH_FINAL, AnnotationFlags.ENDS_WITH_EOS)
                    ]
                    interim_segments = [s for s in self._current_view.segments if s not in final_segments]

                # Keep until end of turn (`ON_END_OF_TURN`)
                else:
                    final_segments = []
                    interim_segments = self._current_view.segments

                # Emit finals first
                if final_segments:
                    """Final segments are checked for end of sentence."""

                    # Metadata for final segments uses actual start/end times of the segments being emitted
                    final_metadata = {
                        "start_time": final_segments[0].start_time,
                        "end_time": final_segments[-1].end_time,
                    }

                    # Ensure final segment ends with EOS
                    if self._config.speech_segment_config.add_trailing_eos:
                        last_segment = final_segments[-1]
                        if not last_segment.fragments[-1].is_eos:
                            last_segment.fragments.append(SpeechFragment(content=".", is_eos=True))

                    # Emit segments
                    self.emit(
                        AgentServerMessageType.ADD_SEGMENT,
                        {
                            "message": AgentServerMessageType.ADD_SEGMENT.value,
                            "segments": [s.model_dump(self._config.include_results) for s in final_segments],
                            "metadata": final_metadata,
                        },
                    )
                    self._trim_before_time = final_segments[-1].end_time
                    self._speech_fragments = [
                        f for f in self._speech_fragments if f.start_time >= self._trim_before_time
                    ]

                # Emit interim segments
                if interim_segments:
                    """Partial segments are emitted as is."""

                    # Metadata for partial segments uses actual start/end times of the segments being emitted
                    partial_metadata = {
                        "start_time": interim_segments[0].start_time,
                        "end_time": interim_segments[-1].end_time,
                    }

                    # Emit segments
                    self.emit(
                        AgentServerMessageType.ADD_PARTIAL_SEGMENT,
                        {
                            "message": AgentServerMessageType.ADD_PARTIAL_SEGMENT.value,
                            "segments": [s.model_dump(self._config.include_results) for s in interim_segments],
                            "metadata": partial_metadata,
                        },
                    )

                # Update the current view
                self._update_current_view()

                # Reset the turn start time
                if not self._turn_start_time:
                    self._turn_start_time = self._current_view.start_time

                # Send updated speaker metrics
                if self._dz_enabled and self.listeners(AgentServerMessageType.SPEAKER_METRICS):
                    """Update the metrics of the speakers in the sesseion."""

                    # Finalized words
                    final_words = [
                        f
                        for seg in final_segments
                        for f in seg.fragments
                        if f.type_ == "word" and f.speaker is not None
                    ]

                    # Only process if we have words
                    if final_words:
                        # Update the metrics of the speakers in the session
                        for frag in final_words:
                            # Check we have a speaker
                            if frag.speaker is None:
                                continue

                            # Create new speaker
                            if frag.speaker not in self._session_speakers:
                                self._session_speakers[frag.speaker] = SessionSpeaker(speaker_id=frag.speaker)

                            # Update metrics
                            self._session_speakers[frag.speaker].word_count += 1
                            self._session_speakers[frag.speaker].last_heard = frag.end_time

                        # Emit
                        self.emit(
                            AgentServerMessageType.SPEAKER_METRICS,
                            {
                                "message": AgentServerMessageType.SPEAKER_METRICS.value,
                                "speakers": [s.model_dump() for s in self._session_speakers.values()],
                            },
                        )

        # Emit END_OF_TURN
        if end_of_turn and self._previous_view:
            # Metadata (for LAST view)
            metadata = {"start_time": self._turn_start_time, "end_time": self._previous_view.end_time}

            # Emit
            self.emit(
                AgentServerMessageType.END_OF_TURN,
                {
                    "message": AgentServerMessageType.END_OF_TURN.value,
                    "turn_id": self._end_of_turn_handler.turn_id,
                    "metadata": metadata,
                },
            )

            # Reset the previous view
            self._previous_view = None
            self._turn_start_time = None

    # ============================================================================
    # TURN DETECTION & FINALIZATION
    # ============================================================================

    async def _calculate_finalize_delay(
        self,
        smart_turn_prediction: Optional[SmartTurnPredictionResult] = None,
    ) -> Optional[float]:
        """Calculate the delay before finalizing / end of turn.

        Process the most recent segment and view to determine how long to delay before finalizing
        the segments to the client.

        Args:
            view: The speaker fragment to evaluate.
            view_changes: The annotation result to use for evaluation.
            filter_flags: The annotation flags to use for evaluation.
            smart_turn_prediction: The smart turn prediction result to use for evaluation.

        Returns:
            Optional[float]: The delay before finalizing / end of turn.
        """

        # Get the current view -or- previous view
        view = self._current_view or self._previous_view

        # Exit if none
        if not view:
            return None

        # Last active segment
        last_active_segment_index = view.last_active_segment_index
        last_active_segment = view.segments[last_active_segment_index] if last_active_segment_index > -1 else None

        # Calculations
        clamped_delay: float = self._config.end_of_utterance_max_delay
        finalize_delay: Optional[float] = None
        time_slip: Optional[float] = None

        # Reasons for the calculation
        reasons: list[tuple[float, str]] = []

        # Add multiplier
        def add_multipler_reason(multiplier: float, reason: str) -> None:
            reasons.append((multiplier, reason))

        # If the last segment is for an active speaker
        if last_active_segment:
            """Check the contents of the last segment."

            Check for:
                - has any disfluencies
                - ends with a disfluency
                - speed of speech
                - ends with finalizes end of sentence
            """

            # Very speaking
            if last_active_segment.annotation.has(AnnotationFlags.VERY_SLOW_SPEAKER):
                add_multipler_reason(3.0, "very_slow_speaker")

            # Slow speaking
            if last_active_segment.annotation.has(AnnotationFlags.SLOW_SPEAKER):
                add_multipler_reason(2.0, "slow_speaker")

            # Disfluencies
            if last_active_segment.annotation.has(AnnotationFlags.ENDS_WITH_DISFLUENCY):
                add_multipler_reason(2.5, "ends_with_disfluency")
            elif last_active_segment.annotation.has(AnnotationFlags.HAS_DISFLUENCY):
                add_multipler_reason(0.25, "has_disfluency")

            # Ends with an end of sentence
            if last_active_segment.annotation.has(AnnotationFlags.ENDS_WITH_EOS, AnnotationFlags.ENDS_WITH_FINAL):
                add_multipler_reason(-0.3, "ends_with_eos_and_final")

            # Does NOT end with end of sentence
            if not last_active_segment.annotation.has(AnnotationFlags.ENDS_WITH_EOS):
                add_multipler_reason(1.0, "does_not_end_with_eos")

        # If no segments
        else:
            add_multipler_reason(0, "no_segments")

        # Smart turn prediction
        if smart_turn_prediction:
            if smart_turn_prediction.prediction:
                add_multipler_reason(-1.0, "smart_turn_true")
            else:
                add_multipler_reason(2.5, "smart_turn_false")

        # Calculate multiplier
        multiplier = 1.0 + sum(m for m, _ in reasons)

        # Minimum delay (50ms as a minimum)
        delay = round(max(self._end_of_utterance_delay, 0.05) * multiplier, 2)

        # Clamp to max delay
        clamped_delay = min(delay, self._config.end_of_utterance_max_delay)

        # Establish the real-world time
        time_slip = max(self._total_time - self._last_fragment_end_time, 0)

        # Adjust time and make sure no less than 25ms
        finalize_delay = max(clamped_delay - time_slip, 0.025)

        # Emit prediction
        if self.listeners(AgentServerMessageType.END_OF_TURN_PREDICTION):
            self.emit(
                AgentServerMessageType.END_OF_TURN_PREDICTION,
                {
                    "message": AgentServerMessageType.END_OF_TURN_PREDICTION.value,
                    "turn_id": self._end_of_turn_handler.turn_id,
                    "metadata": {
                        "ttl": round(finalize_delay, 2),
                        "time_slip": round(time_slip, 2),
                        "reasons": [_reason for _, _reason in reasons],
                    },
                },
            )

        # Return the time
        return finalize_delay

    async def _predict_smart_turn(self, end_time: float, language: str) -> SmartTurnPredictionResult:
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
        if not self._turn_detector:
            return SmartTurnPredictionResult(error="Smart turn is not enabled")

        # Get audio slice (add small margin of 100ms to the end of the audio)
        segment_audio = await self._audio_buffer.get_frames(
            start_time=end_time - self._config.smart_turn_config.audio_buffer_length,
            end_time=end_time + self._config.smart_turn_config.slice_margin,
        )

        # Evaluate
        prediction = await self._turn_detector.predict(
            segment_audio,
            language=language,
            sample_rate=self._audio_sample_rate,
            sample_width=self._audio_sample_width,
        )

        # Return the prediction
        return prediction

    # ============================================================================
    # VAD (VOICE ACTIVITY DETECTION)
    # ============================================================================

    def _vad_evaluation(self, fragments: list[SpeechFragment]) -> None:
        """Emit a VAD event.

        This will emit `SPEAKER_STARTED` and `SPEAKER_ENDED` events to the client and is
        based on valid transcription for active speakers. Ignored or speakers not in
        focus will not be considered an active participant.

        This should only run on partial / non-final words.

        Args:
            fragments: The list of fragments to use for evaluation.
        """

        # Find the valid list of partial words
        if self._dz_enabled and self._dz_config.focus_speakers:
            partial_words = [
                frag
                for frag in fragments
                if frag.speaker in self._dz_config.focus_speakers and frag.type_ == "word" and not frag.is_final
            ]
        else:
            partial_words = [frag for frag in fragments if frag.type_ == "word" and not frag.is_final]

        # Evaluate if any valid partial words exist
        has_valid_partial = len(partial_words) > 0

        # Current states
        current_is_speaking = self._is_speaking
        current_speaker = self._current_speaker

        # Establish the speaker from latest partials
        latest_speaker = partial_words[-1].speaker if has_valid_partial else current_speaker

        # Determine if the speaker has changed (and we have a speaker)
        speaker_changed = latest_speaker != current_speaker and current_speaker is not None

        # Start / end times (earliest and latest)
        speaker_start_time = partial_words[0].start_time if has_valid_partial else None
        speaker_end_time = self._last_fragment_end_time

        # If diarization is enabled, indicate speaker switching
        if self._dz_enabled and latest_speaker is not None:
            """When enabled, we send a speech events if the speaker has changed.

            This
            will emit a SPEAKER_ENDED for the previous speaker and a SPEAKER_STARTED
            for the new speaker.

            For any client that wishes to show _which_ speaker is speaking, this will
            emit events to indicate when speakers switch.
            """

            # Check if speaker is different to the current speaker
            if current_is_speaking and speaker_changed:
                self.emit(
                    AgentServerMessageType.SPEAKER_ENDED,
                    {
                        "message": AgentServerMessageType.SPEAKER_ENDED.value,
                        "status": SpeakerVADStatus(
                            speaker_id=current_speaker, is_active=False, time=speaker_end_time
                        ).model_dump(),
                    },
                )
                self.emit(
                    AgentServerMessageType.SPEAKER_STARTED,
                    {
                        "message": AgentServerMessageType.SPEAKER_STARTED.value,
                        "status": SpeakerVADStatus(
                            speaker_id=latest_speaker, is_active=True, time=speaker_end_time
                        ).model_dump(),
                    },
                )

        # No further processing if we have no new fragments and we are not speaking
        if has_valid_partial == current_is_speaking:
            return

        # Update current speaker + speaking states
        self._current_speaker = latest_speaker
        self._is_speaking = not current_is_speaking

        # Event time
        event_time = speaker_start_time if self._is_speaking else speaker_end_time

        # Emit start of turn
        if (
            not self._end_of_turn_handler.turn_active
            and self._is_speaking
            and self._end_of_utterance_mode
            in [
                EndOfUtteranceMode.ADAPTIVE,
                EndOfUtteranceMode.SMART_TURN,
            ]
        ):
            self._end_of_turn_handler.start_turn()
            self.emit(
                AgentServerMessageType.START_OF_TURN,
                {
                    "message": AgentServerMessageType.START_OF_TURN.value,
                    "turn_id": self._end_of_turn_handler.turn_id,
                    "metadata": {
                        "start_time": event_time,
                    },
                },
            )

        # Determine start or end of speaking
        if self._is_speaking:
            msg = AgentServerMessageType.SPEAKER_STARTED
        else:
            msg = AgentServerMessageType.SPEAKER_ENDED

        # Emit the event
        self.emit(
            msg,
            {
                "message": msg.value,
                "status": SpeakerVADStatus(
                    speaker_id=latest_speaker, is_active=self._is_speaking, time=event_time
                ).model_dump(),
            },
        )

        # Speaking has stopped
        if not self._is_speaking:
            """Reset the current speaker and do smart turn detection (if enabled)."""

            # Reset current speaker
            self._current_speaker = None

            # For ADAPTIVE and SMART_TURN only
            if self._end_of_utterance_mode in [EndOfUtteranceMode.ADAPTIVE, EndOfUtteranceMode.SMART_TURN]:
                """When ADAPTIVE or SMART_TURN, we need to do EOT detection / prediction."""

                # Callback
                async def do_eot_detection(end_time: float, language: str) -> None:
                    try:
                        # Wait for Smart Turn result
                        if self._end_of_utterance_mode == EndOfUtteranceMode.SMART_TURN:
                            result = await self._predict_smart_turn(end_time, language)
                        else:
                            result = None

                        # Create a new task to evaluate the finalize delay
                        delay = await self._calculate_finalize_delay(smart_turn_prediction=result)

                        # Set the finalize timer (go now if no delay)
                        self._end_of_turn_handler.update_timer(delay or 0.01)

                    except asyncio.CancelledError:
                        pass

                # Add task
                self._end_of_turn_handler.add_task(
                    asyncio.create_task(do_eot_detection(speaker_end_time, self._config.language)),
                    self._end_of_utterance_mode.value,
                )

        # Speaking has started
        else:
            """When speaking has started, reset speaking-related variables."""

            # Reset the handlers
            self._end_of_turn_handler.reset()

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _next_fragment_id(self) -> int:
        """Return the next fragment ID."""
        self._fragment_idx += 1
        return self._fragment_idx

    def _get_endpoint_url(self, url: str, app: Optional[str] = None) -> str:
        """Format the endpoint URL with the SDK and app versions.

        Args:
            url: The base URL for the endpoint.
            app: The application name to use in the endpoint URL.

        Returns:
        str: The formatted endpoint URL.
        """

        query_params = {}
        query_params["sm-app"] = app or f"voice-sdk/{__version__}"
        query_params["sm-voice-sdk"] = f"{__version__}"
        query = urlencode(query_params)

        return f"{url}?{query}"
