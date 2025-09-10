#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import asyncio
import datetime
import os
import re
import time
from typing import Any
from typing import Optional
from urllib.parse import urlencode

from speechmatics.rt import AsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioFormat
from speechmatics.rt import ConversationConfig
from speechmatics.rt import ServerMessageType
from speechmatics.rt import TranscriptionConfig

from . import __version__
from ._logging import get_logger
from ._models import AgentServerMessageType
from ._models import AnnotationFlags
from ._models import AnnotationResult
from ._models import DiarizationFocusMode
from ._models import DiarizationSpeakerConfig
from ._models import EndOfUtteranceMode
from ._models import SpeakerSegmentView
from ._models import SpeakerVADStatus
from ._models import SpeechFragment
from ._models import VoiceAgentConfig

DEBUG_MORE = os.getenv("SPEECHMATICS_DEBUG_MORE", "0").lower() in ["1", "true"]
PREVIEW_FEATURES = os.getenv("SPEECHMATICS_PREVIEW_FEATURES", "0").lower() in ["1", "true"]


if DEBUG_MORE:
    import json


class VoiceAgentClient(AsyncClient):
    """Voice Agent client.

    This class extends the AsyncClient class from the Speechmatics Real-Time SDK
    and provides additional functionality for processing partial and final
    transcription from the STT engine into accumulated transcriptions with
    flags to indicate changes between messages, etc.
    """

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
        """
        # Default URL
        if not url:
            url = os.getenv("SPEECHMATICS_RT_URL") or "wss://eu2.rt.speechmatics.com/v2"

        # Initialize the client
        super().__init__(api_key=api_key, url=self._get_endpoint_url(url, app))

        # Logger
        self._logger = get_logger(__name__)

        # Process the config
        self._config, self._transcription_config, self._audio_format = self._process_config(config)

        # Connection status
        self._is_connected: bool = False
        self._is_ready_for_audio: bool = False

        # Timing info
        self._start_time: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
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

        # Speaking states
        self._is_speaking: bool = False
        self._current_speaker: Optional[str] = None
        self._last_vad_time: float = 0

        # Diarization / speaker focus
        self._end_of_utterance_mode: EndOfUtteranceMode = self._config.end_of_utterance_mode
        self._end_of_utterance_delay: float = self._config.end_of_utterance_silence_trigger
        self._dz_enabled: bool = self._config.enable_diarization
        self._dz_config = self._config.speaker_config

        # Timers for EndOfUtterance and EndOfTurn
        self._finalize_task: Optional[asyncio.Task] = None
        self._eot_task: Optional[asyncio.Task] = None

        # Segment processor
        self._processor_wait_time: float = 0.005
        self._processor_task: Optional[asyncio.Task] = None

        # Emitter task
        self._finals_emitter_task: Optional[asyncio.Task] = None

        # Metrics emitter task
        self._metrics_emitter_interval: float = 10.0
        self._metrics_emitter_task: Optional[asyncio.Task] = None

        # Audi sampling info
        self._audio_sample_rate: float = self._audio_format.sample_rate * 1.0
        self._audio_sample_width: float = {
            AudioEncoding.PCM_F32LE: 4.0,
            AudioEncoding.PCM_S16LE: 2.0,
        }.get(self._audio_format.encoding, 1.0)

        # Register handlers
        self._register_event_handlers()

    # def on(self, event: ServerMessageType, callback: Optional[Callable] = None) -> Callable:

    def _process_config(
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
                    "sounds_like": e.sounds_like,
                }
                for e in config.additional_vocab
            ]

        # Diarization
        if config.enable_diarization:
            dz_cfg: dict[str, Any] = {}
            if config.speaker_sensitivity is not None:
                dz_cfg["speaker_sensitivity"] = config.speaker_sensitivity
            if config.prefer_current_speaker is not None:
                dz_cfg["prefer_current_speaker"] = config.prefer_current_speaker
            if config.known_speakers:
                dz_cfg["speakers"] = {s.label: s.speaker_identifiers for s in config.known_speakers}
            if config.max_speakers is not None:
                dz_cfg["max_speakers"] = config.max_speakers
            if dz_cfg:
                transcription_config.speaker_diarization_config = dz_cfg

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
        )

        # Return the config objects
        return config, transcription_config, audio_format

    def _register_event_handlers(self) -> None:
        """Register event handlers.

        Specific event handlers that we need to deal with. All other events
        from the STT API will be available to clients to use themselves.
        """

        # Recognition started event
        @self.once(ServerMessageType.RECOGNITION_STARTED)
        def _evt_on_recognition_started(message: dict[str, Any]) -> None:
            self._start_time = datetime.datetime.now(datetime.timezone.utc)
            self._is_ready_for_audio = True

        # Partial transcript event
        @self.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
        def _evt_on_partial_transcript(message: dict[str, Any]) -> None:
            self._handle_transcript(message, is_final=False)

        # Final transcript event
        @self.on(ServerMessageType.ADD_TRANSCRIPT)
        def _evt_on_final_transcript(message: dict[str, Any]) -> None:
            self._handle_transcript(message, is_final=True)

        # End of utterance event
        if self._end_of_utterance_mode == EndOfUtteranceMode.FIXED:

            @self.on(ServerMessageType.END_OF_UTTERANCE)
            def _evt_on_end_of_utterance(message: dict[str, Any]) -> None:
                self._logger.debug("End of utterance")
                # self.finalize_segments()
                # pass

    async def connect(self) -> None:
        """Connect to the Speechmatics API.

        Args:
            transcription_config: Transcription configuration.
            audio_format: Audio format.
        """
        # Check if we are already connected
        if self._is_connected:
            self.emit(
                AgentServerMessageType.ERROR,
                {"reason": "Already connected"},
            )
            return

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

    async def disconnect(self) -> None:
        """Disconnect from the Speechmatics API."""
        # Check if we are already connected
        if not self._is_connected:
            return

        # Disconnect from API
        try:
            await asyncio.wait_for(self.close(), timeout=5.0)
        except asyncio.TimeoutError:
            self._logger.warning(f"{self} Timeout while closing Speechmatics client connection")
            raise
        except Exception as e:
            self._logger.error(f"{self} Error closing Speechmatics client: {e}")
            raise
        finally:
            self._is_connected = False
            self._is_ready_for_audio = False
            self._stop_metrics_task()

    def update_diarization_config(self, config: DiarizationSpeakerConfig) -> None:
        """Update the diarization configuration.

        You can update the speakers that needs to be focussed on or ignored during
        a session. The new config will overwrite the existing configuration and become
        active immediately.

        Args:
            config: The new diarization configuration.
        """
        self._dz_config = config

    async def send_audio(self, payload: bytes) -> None:
        """Send an audio frame through the WebSocket.

        Args:
            payload: The audio frame to send.

        Examples:
            >>> audio_chunk = b""
            >>> await client.send_audio(audio_chunk)
        """
        # Skip if not ready for audio
        if not self._is_ready_for_audio:
            return

        # Send to the AsyncClient
        await super().send_audio(payload)

        # Calculate the time (in seconds) for the payload
        if self._audio_format is not None:
            self._total_bytes += len(payload)
            self._total_time += len(payload) / self._audio_sample_rate / self._audio_sample_width

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

    def _handle_transcript(self, message: dict[str, Any], is_final: bool) -> None:
        """Handle the partial and final transcript events.

        Args:
            message: The new Partial or Final from the STT engine.
            is_final: Whether the data is final or partial.
        """
        # Handle async
        asyncio.create_task(self._handle_transcript_async(message, is_final))

    async def _handle_transcript_async(self, message: dict[str, Any], is_final: bool) -> None:
        """Handle the partial and final transcript events (async).

        Args:
            message: The new Partial or Final from the STT engine.
            is_final: Whether the data is final or partial.
        """

        # Debug
        if DEBUG_MORE:
            self._logger.debug(json.dumps(message))

        # Add the speech fragments
        fragments_available = await self._add_speech_fragments(
            message=message,
            is_final=is_final,
        )

        # Skip if unchanged
        if not fragments_available:
            return

        # Clear any existing timer
        if self._processor_task is not None:
            self._processor_task.cancel()

        # Send transcription frames after delay
        async def process_after_delay(delay: float) -> None:
            await asyncio.sleep(delay)
            await self._process_speech_fragments()
            self._processor_task = None

        # Send frames after delay
        self._processor_task = asyncio.create_task(process_after_delay(self._processor_wait_time))

    def _calculate_ttfb(self, end_time: float) -> None:
        """Calculate the time to first text.

        The TTFB is calculated by taking the end time of the payload from the STT
        engine and then calculating the difference between the total time of bytes
        sent to the engine from the client.

        Args:
            end_time: The end time of the payload from the STT engine.
        """
        # Skip if no fragments are words
        if len(self._speech_fragments) == 0 or all(f._type != "word" for f in self._speech_fragments):
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
                "ttfb": self._last_ttfb,
            },
        )

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
                        idx=self._frag_idx(),
                        start_time=result.get("start_time", 0),
                        end_time=result.get("end_time", 0),
                        language=alt.get("language", "en"),
                        _type=result.get("type", "word"),
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
                            self._dz_config.focus_mode == DiarizationFocusMode.IGNORE
                            and self._dz_config.focus_speakers
                            and fragment.speaker not in self._dz_config.focus_speakers
                        ):
                            continue

                        # Drop ignored speakers
                        if self._dz_config.ignore_speakers and fragment.speaker in self._dz_config.ignore_speakers:
                            continue

                    # Add the fragment
                    fragments.append(fragment)

            # Evaluate for VAD (only done on partials)
            if not is_final:
                self._vad_evaluation(fragments)

            # Fragments to retain
            retained_fragments = [
                frag for frag in self._speech_fragments if frag.is_final and frag.start_time >= self._trim_before_time
            ]

            # Re-structure the speech fragments
            self._speech_fragments = retained_fragments.copy()
            self._speech_fragments.extend(fragments)
            self._speech_fragments.sort(key=lambda x: x.idx)

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

    async def _process_speech_fragments(self) -> None:
        """Process the speech fragments.

        Compares the current speech fragments against the last set of speech fragments.
        When segments are emitted, they are then removed from the buffer of fragments
        so the next comparison is based on the remaining + new fragments.
        """
        async with self._speech_fragments_lock:
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

        # Emit the segments
        asyncio.create_task(self._emit_segments())

        # TODO: process in-built end of utterance - e.g. `_calc_delay_to_end_of_turn`?
        # TODO: process in-built VAD / end of speech

    def _update_current_view(self) -> None:
        """Load the current view of the speech fragments."""
        self._current_view = SpeakerSegmentView(
            fragments=self._speech_fragments.copy(),
            base_time=self._start_time,
            focus_speakers=self._dz_config.focus_speakers,
        )

    def _calc_delay_to_end_of_turn(
        self,
        view: SpeakerSegmentView,
        view_changes: AnnotationResult,
    ) -> tuple[bool, float | None]:
        """Calculate the delay before finalizing segments.

        Process the most recent segment and view to determine how long to delay before emitting
        the segments to the client.

        Args:
            view: The speaker fragment to evaluate.
            view_changes: The annotation result to use for evaluation.

        Returns:
            Tuple of (should_emit, emit_final_delay)
        """
        # Skip if no segments
        if view.segment_count == 0:
            return False, None

        # Emit segments
        emit_final_delay: Optional[float] = None
        should_emit: bool = False

        # Last active segment
        last_active_segment_index = view.last_active_segment_index
        last_active_segment = view.segments[last_active_segment_index] if last_active_segment_index > -1 else None

        # Elapsed time from last segment to now
        # elapsed_time = (
        #     self._total_time - last_active_segment.end_time
        #     if last_active_segment
        #     else view.end_time
        # )

        # If this is NEW or UPDATED_FULL_LCASE
        if view_changes.any(AnnotationFlags.NEW, AnnotationFlags.UPDATED_FULL_LCASE):
            """Process the annotation flags to determine how long before sending a final segment."""

            # Fallback when using FIXED
            if self._end_of_utterance_mode == EndOfUtteranceMode.FIXED:
                emit_final_delay = self._end_of_utterance_delay * 5.0

            # Timer for when ADAPTIVE
            elif self._end_of_utterance_mode == EndOfUtteranceMode.ADAPTIVE and last_active_segment:
                """Check the contents of the last segment."

                Check for:
                 - ends with a disfluency
                """

                # Minimum delay
                delay = max(self._end_of_utterance_delay, 0.5)

                # Delay multiplier
                multiplier = 1.5

                # Very speaking
                if last_active_segment.annotation.has(AnnotationFlags.VERY_SLOW_SPEAKER):
                    multiplier *= 3.0

                # Slow speaking
                if last_active_segment.annotation.has(AnnotationFlags.SLOW_SPEAKER):
                    multiplier *= 1.5

                # Has a disfluency
                if last_active_segment.annotation.has(AnnotationFlags.HAS_DISFLUENCY):
                    multiplier *= 1.5

                # Ends with a disfluency
                if last_active_segment.annotation.has(AnnotationFlags.ENDS_WITH_DISFLUENCY):
                    multiplier *= 4.0

                # Calculate the delay
                emit_final_delay = delay * multiplier

                # TODO - Other checks / end of turn detection

            # Constrain to `end_of_utterance_max_delay`
            if emit_final_delay is not None:
                emit_final_delay = min(emit_final_delay, self._config.end_of_utterance_max_delay)
            else:
                emit_final_delay = self._config.end_of_utterance_max_delay

            # Emit segments
            should_emit = True

        # Remove any elapsed time from the delay
        # if emit_final_delay is not None:
        #     emit_final_delay = max(
        #         emit_final_delay - elapsed_time,
        #         self._end_of_utterance_delay - elapsed_time,
        #         0.001,
        #     )

        # Return the result
        return should_emit, emit_final_delay

    def finalize_segments(self, ttl: Optional[float] = None) -> None:
        """Finalize segments.

        This function will emit segments in the buffer without any further checks
        on the contents of the segments. If the ttl is set to zero, then finalization
        will be forced through without yielding for any remaining STT messages.

        Args:
            ttl: Optional delay before finalizing partial segments (defaults to 0.01 seconds).
        """

        async def emit() -> None:
            if ttl is not None and ttl > 0:
                await asyncio.sleep(ttl)
            if PREVIEW_FEATURES:
                await self.send_message({"message": "Finalize"})
            else:
                await self._emit_segments(finalize=True)

        asyncio.create_task(emit())

    async def _emit_segments(self, finalize: bool = False) -> None:
        """Emit segments to listeners.

        This function will emit segments in the view without any further checks
        on the contents of the segments. Any segments that end with a final / EOS
        will be emitted as finals and removed from the fragment buffer.

        Args:
            finalize: Whether to finalize all segments.
        """

        # Lock the speech fragments
        async with self._speech_fragments_lock:
            # Skip if no view
            if not self._current_view or self._current_view.segment_count == 0:
                return

            # Force finalize
            if finalize:
                final_segments = self._current_view.segments
                interim_segments = []

            # Split between finals and interim segments
            else:
                final_segments = [
                    s
                    for s in self._current_view.segments
                    if s.annotation.has(AnnotationFlags.ENDS_WITH_FINAL, AnnotationFlags.ENDS_WITH_EOS)
                ]
                interim_segments = [s for s in self._current_view.segments if s not in final_segments]

            # Emit finals first
            if final_segments:
                self.emit(
                    AgentServerMessageType.ADD_SEGMENTS,
                    {"segments": final_segments},
                )
                self._trim_before_time = final_segments[-1].end_time
                self._speech_fragments = [f for f in self._speech_fragments if f.start_time >= self._trim_before_time]

            # Emit interim segments
            if interim_segments:
                self.emit(
                    AgentServerMessageType.ADD_INTERIM_SEGMENTS,
                    {"segments": interim_segments},
                )

            # Update the current view
            self._update_current_view()

    def _vad_evaluation(self, fragments: list[SpeechFragment]) -> None:
        """Emit a VAD event.

        This will emit `SPEECH_STARTED` and `SPEECH_ENDED` events to the client and is
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
                if frag.speaker in self._dz_config.focus_speakers and frag._type == "word" and not frag.is_final
            ]
        else:
            partial_words = [frag for frag in fragments if frag._type == "word" and not frag.is_final]

        # Evaluate if any valid partial words exist
        has_valid_partial = len(partial_words) > 0

        # Are we already speaking
        already_speaking = self._is_speaking

        # Speakers
        current_speaker = self._current_speaker
        speaker = partial_words[-1].speaker if has_valid_partial else self._current_speaker
        speaker_changed = speaker != current_speaker and current_speaker is not None

        # If diarization is enabled, indicate speaker switching
        if self._dz_enabled and speaker is not None:
            """When enabled, we send a speech events if the speaker has changed.

            For any client that wishes to show _which_ speaker is speaking, this will
            emit events to indicate when speakers switch.
            """

            # Check if speaker is different to the current speaker
            if already_speaking and speaker_changed:
                self.emit(
                    AgentServerMessageType.SPEAKING_ENDED,
                    {"status": SpeakerVADStatus(speaker_id=current_speaker, is_active=False)},
                )
                self.emit(
                    AgentServerMessageType.SPEAKING_STARTED,
                    {"status": SpeakerVADStatus(speaker_id=speaker, is_active=True)},
                )

        # Update current speaker
        self._current_speaker = speaker

        # No change required
        if has_valid_partial == already_speaking:
            return

        # Set the speaking state
        self._is_speaking = not self._is_speaking

        # Emit the event for latest speaker
        self.emit(
            (AgentServerMessageType.SPEAKING_STARTED if self._is_speaking else AgentServerMessageType.SPEAKING_ENDED),
            {"status": SpeakerVADStatus(speaker_id=speaker, is_active=self._is_speaking)},
        )

        # Reset the current speaker
        if not self._is_speaking:
            self._current_speaker = None

    def _frag_idx(self):
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
