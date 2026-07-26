from __future__ import annotations

import asyncio
import math
from typing import Any
from typing import BinaryIO
from typing import Optional

from ._audio_sources import FileSource
from ._auth import AuthBase
from ._base_client import _BaseClient
from ._exceptions import AudioError
from ._exceptions import TimeoutError
from ._exceptions import TranscriptionError
from ._logging import get_logger
from ._models import AudioEventsConfig
from ._models import AudioFormat
from ._models import ClientMessageType
from ._models import ConnectionConfig
from ._models import ServerMessageType
from ._models import TranscriptionConfig
from ._models import TranslationConfig

_UNSET = object()

# ForceEndOfUtterance latency-compensation grid.
#
# The engine decodes audio in fixed chunks and only resolves a forced EOU once
# the chunk covering the FEOU timestamp is complete, so FEOU->EndOfUtterance
# latency follows a sawtooth in the timestamp phase. Injecting silence up to the
# next chunk boundary (plus a margin) before sending the FEOU gives the engine
# the covering audio immediately and roughly halves the latency.
#
# Decode-chunk boundaries fall at FEOU_CHUNK_OFFSET + n * FEOU_CHUNK_PERIOD. The
# values are empirical and may vary by engine version/endpoint; if the grid
# differs only these constants change, not the algorithm. FEOU_MARGIN is the
# head-room past the covering boundary (plateau 0.10-0.20s, 0.15 recommended).
FEOU_CHUNK_PERIOD = 0.360
FEOU_CHUNK_OFFSET = 0.290
FEOU_MARGIN = 0.150

# Server messages that carry audio-stream timestamps (start_time/end_time) somewhere
# in their payload and so must be mapped back to real audio time when FEOU latency
# compensation has injected silence (see AsyncClient._prepare_incoming_message).
# High-frequency / timestamp-free messages (AudioAdded, RecognitionStarted, Info,
# Warning, Error, EndOfTranscript, ...) are deliberately excluded.
_TIMESTAMPED_SERVER_MESSAGES = frozenset(
    {
        ServerMessageType.ADD_TRANSCRIPT,
        ServerMessageType.ADD_PARTIAL_TRANSCRIPT,
        ServerMessageType.ADD_TRANSLATION,
        ServerMessageType.ADD_PARTIAL_TRANSLATION,
        ServerMessageType.END_OF_UTTERANCE,
        ServerMessageType.AUDIO_EVENT_STARTED,
        ServerMessageType.AUDIO_EVENT_ENDED,
        ServerMessageType.SPEAKERS_RESULT,
    }
)

# Payload keys that hold an audio-stream position in seconds.
_TIMESTAMP_KEYS = ("start_time", "end_time")


class AsyncClient(_BaseClient):
    """
    Asynchronous client for Speechmatics real-time audio transcription.

    This client provides a async interface to the Speechmatics RT API,
    supporting real-time audio streaming, event-driven transcript handling, and
    comprehensive error management.

    Args:
        auth: Authentication instance. If not provided, uses StaticKeyAuth
                with api_key parameter or SPEECHMATICS_API_KEY environment variable.
        api_key: Speechmatics API key used if auth not provided.
        url: WebSocket endpoint URL. If not provided, uses SPEECHMATICS_RT_URL
                environment variable or defaults to EU endpoint.
        conn_config: Websocket connection configuration.

    Raises:
        ConfigurationError: If required configuration is missing or invalid.

    Examples:
        Basic usage with event handlers:
            >>> async with AsyncClient(api_key="your-key") as client:
            ...     @client.on(ServerMessageType.ADD_TRANSCRIPT)
            ...     def handle_transcript(message):
            ...         result = TranscriptResult.from_message(message)
            ...         print(f"Final: {result.transcript}")
            ...
            ...     with open("audio.wav", "rb") as audio:
            ...         await client.transcribe(audio)

        With JWT authentication:
            >>> from speechmatics.rt import JWTAuth
            >>> auth = JWTAuth("your-api-key", ttl=300)
            >>> async with AsyncClient(auth=auth) as client:
            ...     # Use client with custom settings
            ...     pass

        Manual resource management:
            >>> client = AsyncClient(api_key="your-key")
            >>> try:
            ...     await client.transcribe(audio_stream)
            ... finally:
            ...     await client.close()
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self._logger = get_logger("speechmatics.rt.async_client")

        (
            self._session,
            self._recognition_started_evt,
            self._session_done_evt,
        ) = self._init_session_info()

        transport = self._create_transport_from_config(
            auth=auth,
            api_key=api_key,
            url=url,
            conn_config=conn_config,
            request_id=self._session.request_id,
        )
        super().__init__(transport)

        self.on(ServerMessageType.RECOGNITION_STARTED, self._on_recognition_started)
        self.on(ServerMessageType.END_OF_TRANSCRIPT, self._on_eot)
        self.on(ServerMessageType.ERROR, self._on_error)
        self.on(ServerMessageType.WARNING, self._on_warning)
        self.on(ServerMessageType.AUDIO_ADDED, self._on_audio_added)

        # Audio format is set when start_session is called with an explicit format.
        # Deliberately None until then to avoid silently using incorrect defaults.
        self._audio_format: Optional[AudioFormat] = None

        # ForceEndOfUtterance latency-compensation state.
        # Silence injected ahead of real time to align a forced EOU with the engine's
        # decode grid lengthens the server-side audio timeline, so returned timestamps
        # run ahead of real audio time by the cumulative injected amount. We track the
        # running total and an ordered list of (server_position, cumulative_injected)
        # checkpoints so timestamps can be mapped back via adjust_timestamp.
        self._injected_silence_seconds: float = 0.0
        self._injected_silence_checkpoints: list[tuple[float, float]] = []

        self._logger.debug("AsyncClient initialized (request_id=%s)", self._session.request_id)

    async def start_session(
        self,
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
    ) -> None:
        """
        This method establishes a WebSocket connection, and configures the transcription session.

        Args:
            transcription_config: Configuration for transcription behavior such as
                                language, partial transcripts, and advanced features.
                                Uses default if not provided.
            audio_format: Audio format specification including encoding, sample rate,
                          and chunk size. Uses default (PCM 16-bit LE, 16kHz) if not provided.
            translation_config: Optional translation configuration for real-time
                              translation output.
            audio_events_config: Optional configuration for audio event detection.
            ws_headers: Additional headers to include in the WebSocket handshake.

        Raises:
            ConnectionError: If the WebSocket connection fails.
            TranscriptionError: If the server reports an error during setup.
            TimeoutError: If the connection or setup times out.

        Examples:
            Basic streaming:
                >>> async with AsyncClient() as client:
                ...     await client.start_session()
                ...     await client.send_audio(frame)
        """

        # Reset per-session FEOU latency-compensation state so a reused client
        # does not carry injected-silence bookkeeping across sessions.
        self._injected_silence_seconds = 0.0
        self._injected_silence_checkpoints = []

        # _start_recognition_session resolves defaults (e.g. AudioFormat() if None),
        # so we capture the resolved format to keep _audio_format in sync.
        _, self._audio_format = await self._start_recognition_session(
            transcription_config=transcription_config,
            audio_format=audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
            ws_headers=ws_headers,
        )

    async def stop_session(self) -> None:
        """
        This method closes the WebSocket connection and ends the transcription session.

        Raises:
            ConnectionError: If the WebSocket connection fails.
            TranscriptionError: If the server reports an error during teardown.
            TimeoutError: If the connection or teardown times out.

        Examples:
            Basic streaming:
                >>> async with AsyncClient() as client:
                ...     await client.start_session()
                ...     await client.send_audio(frame)
                ...     await client.stop_session()
        """
        await self._send_eos(self._seq_no)
        await self._session_done_evt.wait()  # Wait for end of transcript event to indicate we can stop listening
        await self.close()

    async def force_end_of_utterance(
        self,
        *,
        timestamp: Optional[float] | object = _UNSET,
        compensate_latency: bool = False,
        chunk_period: float = FEOU_CHUNK_PERIOD,
        chunk_offset: float = FEOU_CHUNK_OFFSET,
        margin: float = FEOU_MARGIN,
    ) -> None:
        """
        This method sends a ForceEndOfUtterance message to the server to signal
        the end of an utterance. Forcing end of utterance will cause the final
        transcript to be sent to the client early.

        Takes an optional timestamp parameter to specify a marker for the engine
        to use for timing of the end of the utterance. If not provided, the timestamp
        will be calculated based on the cumulative audio sent to the server. If the provided
        timestamp is None, the ForceEndOfUtterance message will not include a timestamp.

        When compensate_latency is True, silence is injected immediately (ahead of
        real time) up to the next decode-chunk boundary past the marker plus a margin,
        before the FEOU is sent. This gives the engine the audio covering the marker
        straight away and roughly halves FEOU->EndOfUtterance latency. The FEOU
        timestamp itself is left at the real speech-end marker (it is not moved to the
        boundary). The injected silence lengthens the server-side audio timeline, so
        subsequent returned timestamps must be mapped back with adjust_timestamp.

        Args:
            timestamp: Optional speech-end time in seconds, expressed in real audio time
                (the audio you streamed, excluding any injected silence). It is shifted
                onto the server timeline by the silence injected so far, so it lines up
                with what the engine sees. If omitted, the current audio position is used.
            compensate_latency: Inject silence to align the marker with the engine's
                decode grid before sending the FEOU. Ignored when the timestamp is
                omitted (explicit None).
            chunk_period: Engine decode-chunk period in seconds (grid spacing).
            chunk_offset: Decode-grid phase; boundaries fall at chunk_offset + n * chunk_period.
            margin: Head-room in seconds injected past the covering chunk boundary.

        Raises:
            ConnectionError: If the WebSocket connection fails.
            TranscriptionError: If the server reports an error during teardown.
            TimeoutError: If the connection or teardown times out.
            ValueError: If the audio format does not have an encoding set.

        Examples:
            Basic streaming:
                >>> async with AsyncClient() as client:
                ...     await client.start_session()
                ...     await client.send_audio(frame)
                ...     await client.force_end_of_utterance()
        """

        message: dict[str, Any] = {"message": ClientMessageType.FORCE_END_OF_UTTERANCE}

        # Resolve the marker as a position on the server audio-stream timeline.
        marker: Optional[float]
        if timestamp is _UNSET:
            # Default: the current audio position. audio_seconds_sent already includes any
            # silence injected by earlier compensated FEOUs, so it is already server time.
            marker = self.audio_seconds_sent
        elif timestamp is not None:
            # Explicit value is a real-audio time; shift it onto the (possibly lengthened)
            # server timeline by adding the silence injected so far. No-op until silence
            # has been injected, so uncompensated usage is unaffected.
            marker = float(timestamp) + self._injected_silence_seconds  # type: ignore[arg-type]
        else:
            # if timestamp is None: omit entirely
            marker = None

        # Inject the aligning silence before the FEOU. The marker is unchanged.
        if compensate_latency and marker is not None:
            await self._inject_feou_silence(
                marker,
                chunk_period=chunk_period,
                chunk_offset=chunk_offset,
                margin=margin,
            )

        if marker is not None:
            message["timestamp"] = marker

        await self.send_message(message)

    async def _inject_feou_silence(
        self,
        marker: float,
        *,
        chunk_period: float,
        chunk_offset: float,
        margin: float,
    ) -> None:
        """
        Inject silence up to the next decode-chunk boundary past a FEOU marker.

        Sends a single block of PCM silence (all zero samples) through the same
        outbound audio path as real audio, so the engine has the audio covering the
        marker in hand and can resolve the forced EOU without waiting real-time for
        the inter-utterance gap. The silence is sent in one message, not paced.

        The injected silence extends the server-side audio timeline; the running total
        and a (server_position, cumulative_injected) checkpoint are recorded so returned
        timestamps can be mapped back to real audio time via adjust_timestamp.

        Args:
            marker: Speech-end position in seconds on the audio-stream timeline.
            chunk_period: Engine decode-chunk period in seconds.
            chunk_offset: Decode-grid phase; boundaries at chunk_offset + n * chunk_period.
            margin: Head-room in seconds injected past the covering chunk boundary.

        Raises:
            ValueError: If the audio format is unset or has no encoding.
        """
        if self._audio_format is None:
            raise ValueError("Cannot compensate FEOU latency before start_session sets an audio format")

        sample_rate = self._audio_format.sample_rate
        bytes_per_sample = self._audio_format.bytes_per_sample

        # Next decode-chunk boundary at or after the marker (grid: offset + n * period).
        boundary = chunk_offset + chunk_period * math.ceil((marker - chunk_offset) / chunk_period)
        if boundary < marker:  # guard against float rounding leaving the boundary behind
            boundary += chunk_period

        pad_seconds = (boundary - marker) + margin
        sample_count = round(pad_seconds * sample_rate)
        if sample_count <= 0:
            return

        # int16/float32/mulaw zeros -> a run of zero bytes of the sample width.
        await self._send_audio_bytes(bytes(sample_count * bytes_per_sample))

        self._injected_silence_seconds += sample_count / sample_rate
        self._injected_silence_checkpoints.append((self.audio_seconds_sent, self._injected_silence_seconds))

    @property
    def injected_silence_seconds(self) -> float:
        """Cumulative silence injected for FEOU latency compensation, in seconds."""
        return self._injected_silence_seconds

    def adjust_timestamp(self, timestamp: float) -> float:
        """
        Map a server-timeline timestamp back to real audio time.

        ForceEndOfUtterance latency compensation injects silence ahead of real time,
        which lengthens the server-side audio timeline. As a result the start_time and
        end_time on AddTranscript, AddPartialTranscript and EndOfUtterance messages run
        ahead of real audio time by the amount of silence injected up to that position.
        This subtracts that offset so the value lines up with the real audio the caller
        streamed.

        If no silence has been injected (compensation disabled or not yet triggered) the
        timestamp is returned unchanged.

        Args:
            timestamp: A timestamp in seconds on the server audio timeline.

        Returns:
            The corresponding real audio time in seconds.
        """
        injected = 0.0
        # Checkpoints are appended in increasing server_position order.
        for server_position, cumulative in self._injected_silence_checkpoints:
            if server_position <= timestamp:
                injected = cumulative
            else:
                break
        return timestamp - injected

    def _prepare_incoming_message(self, msg: dict[str, Any]) -> None:
        """
        Map server-timeline timestamps on an incoming message back to real audio time.

        When FEOU latency compensation has injected silence, the start_time/end_time
        fields on transcript, translation, audio-event and end-of-utterance messages
        run ahead of real audio time. This rewrites them in place (via adjust_timestamp)
        before the message is emitted, so every listener sees real audio time without
        needing to correct the values itself. It is a no-op until silence has been
        injected.

        Each timestamp is adjusted independently by its own audio-stream position, so a
        single payload whose results span an injection point is handled correctly:
        values before the injected silence keep the earlier offset, values after it get
        the later (larger) offset.
        """
        # Nothing to correct until compensation has injected silence.
        if not self._injected_silence_checkpoints:
            return

        if msg.get("message") not in _TIMESTAMPED_SERVER_MESSAGES:
            return

        self._adjust_timestamps_in_place(msg)

    def _adjust_timestamps_in_place(self, node: Any) -> None:
        """
        Recursively map every audio-stream start_time/end_time within a payload back to
        real audio time.

        Walks nested dicts/lists so timestamps are corrected wherever they appear
        (metadata, per-result timings, audio-event fields, ...) without hard-coding each
        message's structure. Only numeric values are touched.
        """
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _TIMESTAMP_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool):
                    node[key] = self.adjust_timestamp(value)
                else:
                    self._adjust_timestamps_in_place(value)
        elif isinstance(node, list):
            for item in node:
                self._adjust_timestamps_in_place(item)

    @property
    def audio_seconds_sent(self) -> float:
        """Number of audio seconds sent to the server.

        Raises:
            ValueError: If called before start_session has set the audio format,
                or if the audio format does not have an encoding set.
        """
        # _audio_format is only set once start_session receives an explicit AudioFormat.
        # Failing here prevents silently computing with wrong defaults (e.g. 44100Hz).
        if self._audio_format is None:
            raise ValueError("audio_seconds_sent is not available before start_session is called with an audio format")
        return self._audio_bytes_sent / (self._audio_format.sample_rate * self._audio_format.bytes_per_sample)

    async def transcribe(
        self,
        source: BinaryIO,
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Transcribe a single audio stream in real-time.

        This method establishes a WebSocket connection, configures the transcription
        session, streams the audio data, and processes the results through registered
        event handlers. The method returns when the transcription is complete or
        an error occurs.

        Args:
            source: Audio data source with a read() method. Can be a file
                        object, BytesIO, or any object supporting the binary
                        read interface.
            transcription_config: Configuration for transcription behavior such as
                                language, partial transcripts, and advanced features.
                                Uses default if not provided.
            audio_format: Audio format specification including encoding, sample rate,
                          and chunk size. Uses default (PCM 16-bit LE, 44.1kHz) if
                          not provided.
            ws_headers: Additional headers to include in the WebSocket handshake.
            timeout: Maximum time in seconds to wait for transcription completion.
                    Default None.

        Raises:
            AudioError: If source is invalid or cannot be read.
            TimeoutError: If transcription exceeds the specified timeout.
            TranscriptionError: If the server reports an error during transcription.
            ConnectionError: If the WebSocket connection fails.

        Examples:
            Basic transcription:
            >>> with open("speech.wav", "rb") as audio:
            ...     await client.transcribe(audio)

            With custom configuration:
            >>> config = TranscriptionConfig(
            ...     language="en",
            ...     enable_partials=True,
            ...     max_delay=1.0
            ... )
            >>> audio_fmt = AudioFormat(
            ...     encoding=AudioEncoding.PCM_S16LE,
            ...     sample_rate=16000
            ... )
            >>> with open("speech.raw", "rb") as audio:
            ...     await client.transcribe(
            ...         audio,
            ...         transcription_config=config,
            ...         audio_format=audio_fmt,
            ...     )
        """
        if not source:
            raise AudioError("Audio input source cannot be empty")

        transcription_config, audio_format = await self._start_recognition_session(
            transcription_config=transcription_config,
            audio_format=audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
            ws_headers=ws_headers,
        )

        try:
            await asyncio.wait_for(
                self._audio_producer(source, audio_format.chunk_size),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Transcription session timed out") from exc

    async def _audio_producer(self, source: BinaryIO, chunk_size: int) -> None:
        """
        Continuously read from source and send data to the server.

        This method reads audio data in chunks and sends it as binary WebSocket
        frames. Automatically sends an EndOfStream message when the stream is exhausted.

        Args:
            source: File-like object to read audio from
            chunk_size: Chunk size for audio data
        """
        src = FileSource(source, chunk_size=chunk_size)

        try:
            async for frame in src:
                if self._session_done_evt.is_set():
                    break

                try:
                    await self.send_audio(frame)
                except Exception as e:
                    self._logger.error("Failed to send audio frame: %s", e)
                    self._session_done_evt.set()
                    break

            await self.stop_session()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._logger.error("Audio producer error: %s", e)
            self._session_done_evt.set()

    async def _send_eos(self, seq_no: int) -> None:
        """Send EndOfStream message to server."""
        if not self._eos_sent and not self._session_done_evt.is_set():
            try:
                await self.send_message({"message": ClientMessageType.END_OF_STREAM, "last_seq_no": seq_no})
                self._eos_sent = True
            except Exception as e:
                self._logger.error("Failed to send EndOfStream message: %s", e)

    async def _wait_recognition_started(self, timeout: float = 5.0) -> None:
        """Wait for RecognitionStarted message from server."""
        await asyncio.wait_for(self._recognition_started_evt.wait(), timeout)

    def _on_recognition_started(self, msg: dict[str, Any]) -> None:
        """Handle RecognitionStarted message from server."""
        self._session.session_id = msg.get("id")
        self._recognition_started_evt.set()
        self._logger.debug("Recognition started (session_id=%s)", self._session.session_id)

    def _on_eot(self, msg: dict[str, Any]) -> None:
        """Handle EndOfTranscript message from server."""
        self._logger.debug("Received EndOfTranscript message")
        self._session_done_evt.set()

    def _on_error(self, msg: dict[str, Any]) -> None:
        """Handle Error message from server."""
        error = msg.get("reason", "unknown")
        self._logger.error("Server error: %s", error)
        self._session_done_evt.set()
        raise TranscriptionError(error)

    def _on_audio_added(self, msg: dict[str, Any]) -> None:
        """Handle AudioAdded message from server."""
        self._seq_no = msg.get("seq_no", 0)

    def _on_warning(self, msg: dict[str, Any]) -> None:
        """Handle Warning message from server."""
        self._logger.warning("Server warning: %s", msg.get("reason", "unknown"))

    async def close(self) -> None:
        """
        Close the client and clean up resources.
        WARNING: this closes the client without waiting for remaining messages to be processed.
        It is recommended to use stop_session() instead.

        Ensures the session is marked as complete and delegates to the base
        class for full cleanup including WebSocket connection termination.
        """
        self._session_done_evt.set()
        await super().close()
