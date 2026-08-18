from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from typing import BinaryIO
from typing import Optional

from speechmatics.rt import AsyncClient as RTAsyncClient
from speechmatics.rt import AudioEncoding
from speechmatics.rt import AudioEventsConfig
from speechmatics.rt import AudioFormat
from speechmatics.rt import AuthBase
from speechmatics.rt import ConnectionConfig
from speechmatics.rt import StaticKeyAuth
from speechmatics.rt import TimeoutError as RTTimeoutError
from speechmatics.rt import TranscriptionConfig as RTTranscriptionConfig
from speechmatics.rt import TranslationConfig
from speechmatics.rt import TransportError

from ._logging import get_logger
from ._models import DEFAULT_CHUNK_SIZE
from ._models import DEFAULT_SAMPLE_RATE
from ._models import TIMED_MESSAGES
from ._models import ClientMessageType
from ._models import LanguagePackInfo
from ._models import Segment
from ._models import ServerMessageType
from ._models import SessionInfo
from ._models import TimedEvent
from ._models import TranscriptionConfig
from ._transcript import Transcript
from ._transport import AgentTransport
from ._url import resolve_url

_UNSET = object()

DISCONNECT_TIMEOUT = 5.0


class AsyncClient(RTAsyncClient):
    """
    Asynchronous client for the Speechmatics Agent STT service.

    Extends the RT client to talk to the Agent STT endpoint (`/agent`), which works in
    segments rather than word groups and reports speech and turn events. The client runs no
    VAD and no turn detection of its own: either the service's VAD closes turns
    (`VADMode.SERVER`) or the application's does, by calling `finalize()` (`VADMode.CLIENT`).

    Args:
        auth: Authentication instance. Defaults to `StaticKeyAuth` built from `api_key` or the
            `SPEECHMATICS_API_KEY` environment variable.
        api_key: Speechmatics API key, used when `auth` is not given.
        url: WebSocket endpoint. Defaults to `SPEECHMATICS_RT_URL`, then the EU endpoint.
            An `/agent` segment is appended if absent.
        profile: Service profile, appended to the endpoint path.
        app: Application name reported to the service as `sm-app`.
        config: Transcription config for the session, normally an
            `agent_stt.TranscriptionConfig`.
        audio_format: Audio format. Defaults to 16 kHz signed 16-bit PCM, which is what the
            service requires.
        conn_config: WebSocket connection configuration.
        record_events: Whether to keep every raw server message in `events`.

    Examples:
        Service VAD, transcript at the end:
            >>> async with AsyncClient(api_key="your-key") as client:
            ...     @client.on(ServerMessageType.ADD_SEGMENT)
            ...     def handle_segment(message):
            ...         print(message["segment"]["transcript"])
            ...     await client.send_audio(frame)
            >>> print(client.transcript)

        Client VAD (Pipecat, LiveKit):
            >>> config = TranscriptionConfig(vad_mode=VADMode.CLIENT)
            >>> client = AsyncClient(api_key="your-key", config=config)
            >>> await client.connect()
            >>> await client.send_audio(frame)
            >>> client.finalize()  # on the application's own end-of-speech signal
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        profile: Optional[str] = None,
        app: Optional[str] = None,
        config: Optional[RTTranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        conn_config: Optional[ConnectionConfig] = None,
        record_events: bool = True,
    ) -> None:
        super().__init__(
            auth,
            api_key=api_key,
            url=resolve_url(url, profile=profile, app=app),
            conn_config=conn_config,
        )

        self._logger = get_logger("speechmatics.agent_stt.client")

        self._config: RTTranscriptionConfig = config or TranscriptionConfig()
        self._audio_format = audio_format or AudioFormat(
            encoding=AudioEncoding.PCM_S16LE,
            sample_rate=DEFAULT_SAMPLE_RATE,
            chunk_size=DEFAULT_CHUNK_SIZE,
        )

        self._session_info = SessionInfo(request_id=self._session.request_id)
        self._transcript = Transcript(record_events=record_events)

        self._is_connected = False
        self._is_ready_for_audio = False
        self._finalize_sent_at: Optional[float] = None
        self._last_finalize_latency = 0.0

        self._register_handlers()

    @classmethod
    def _create_transport_from_config(
        cls,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
        request_id: Optional[str] = None,
    ) -> AgentTransport:
        """Build the Agent STT transport, so the service sees this SDK's identifier."""
        return AgentTransport(
            url or resolve_url(),
            conn_config or ConnectionConfig(),
            auth or StaticKeyAuth(api_key),
            request_id or str(uuid.uuid4()),
        )

    def _register_handlers(self) -> None:
        """Track session state and accumulate segments, leaving all messages for the application."""
        self.on(ServerMessageType.RECOGNITION_STARTED, self._on_session_started)
        self.on(ServerMessageType.ADD_SEGMENT, self._on_segment)
        self.on(ServerMessageType.ADD_PARTIAL_SEGMENT, self._on_segment)
        for message_type in TIMED_MESSAGES:
            self.on(message_type, self._on_timed_event)

    # ==========================================================================
    # Session lifecycle
    # ==========================================================================

    async def connect(self, ws_headers: Optional[dict] = None) -> None:
        """
        Open the session and wait until the service is ready for audio.

        Audio sent before this returns is dropped, so callers do not have to sequence the
        handshake themselves.

        Args:
            ws_headers: Additional WebSocket handshake headers.

        Raises:
            ConnectionError: If the WebSocket connection fails.
            TimeoutError: If the service does not accept the session in time.

        Examples:
            >>> client = AsyncClient(api_key="your-key")
            >>> await client.connect()
        """
        if self._is_connected:
            return

        await self.start_session(
            transcription_config=self._config,
            audio_format=self._audio_format,
            ws_headers=ws_headers,
        )
        self._is_connected = True

    async def disconnect(self) -> None:
        """
        Close the session, flushing whatever the service still holds.

        Examples:
            >>> await client.disconnect()
            >>> print(client.transcript)
        """
        if not self._is_connected:
            await self.close()
            return

        self._is_ready_for_audio = False
        try:
            await asyncio.wait_for(self.stop_session(), timeout=DISCONNECT_TIMEOUT)
        except Exception as e:
            self._logger.warning("Error closing session: %s", e)
            await self.close()
        finally:
            self._is_connected = False

    async def __aenter__(self) -> AsyncClient:
        """Open the session on entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the session on exit."""
        await self.disconnect()

    async def start_session(
        self,
        *,
        transcription_config: Optional[RTTranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
    ) -> None:
        """
        Start the session, defaulting to the config this client was built with.

        Args:
            transcription_config: Transcription config for the session.
            audio_format: Audio format. Must be 16 kHz raw PCM for the Agent STT service.
            translation_config: Optional translation config.
            audio_events_config: Optional audio event detection config.
            ws_headers: Additional WebSocket handshake headers.

        Raises:
            ConnectionError: If the WebSocket connection fails.
            TimeoutError: If the service does not accept the session in time.
        """
        await super().start_session(
            transcription_config=transcription_config or self._config,
            audio_format=audio_format or self._audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
            ws_headers=ws_headers,
        )

    # ==========================================================================
    # Audio and turn control
    # ==========================================================================

    async def send_audio(self, payload: bytes) -> None:
        """
        Send an audio frame.

        Frames sent before the session is ready, or after it has closed, are dropped rather
        than raising, so an audio callback does not have to track session state.

        Args:
            payload: Raw audio bytes in the session's audio format.

        Examples:
            >>> await client.send_audio(frame)
        """
        if not self._is_ready_for_audio:
            return

        try:
            await super().send_audio(payload)
        except TransportError as e:
            self._logger.warning("Error sending audio: %s", e)
            self._is_ready_for_audio = False

    def finalize(self, *, timestamp: Optional[float] | object = _UNSET) -> None:
        """
        Close the current turn now, from a synchronous context.

        Sends ForceEndOfUtterance stamped with the audio timestamp at the moment of the call,
        so the service closes the turn where the application's VAD detected the end of speech
        rather than wherever the send happens to land. The flushed segment arrives as a normal
        AddSegment message.

        Use this when the application brings its own VAD (`VADMode.CLIENT`); with
        `VADMode.SERVER` the service closes turns itself.

        Args:
            timestamp: Audio timestamp in seconds for the end of the utterance. Defaults to
                the amount of audio sent so far. Pass None to send no timestamp.

        Examples:
            >>> client.finalize()
        """
        resolved = self.audio_seconds_sent if timestamp is _UNSET else timestamp
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._logger.warning("finalize() needs a running event loop; use force_end_of_utterance()")
            return
        loop.create_task(self._send_force_end_of_utterance(resolved))

    async def force_end_of_utterance(self, *, timestamp: Optional[float] | object = _UNSET) -> None:
        """
        Close the current turn now, awaiting the send.

        The awaitable form of `finalize()`.

        Args:
            timestamp: Audio timestamp in seconds for the end of the utterance. Defaults to
                the amount of audio sent so far. Pass None to send no timestamp.

        Examples:
            >>> await client.force_end_of_utterance()
        """
        resolved = self.audio_seconds_sent if timestamp is _UNSET else timestamp
        await self._send_force_end_of_utterance(resolved)

    async def _send_force_end_of_utterance(self, timestamp: Optional[float] | object) -> None:
        """Send ForceEndOfUtterance, including the timestamp unless it is None."""
        message: dict[str, Any] = {"message": ClientMessageType.FORCE_END_OF_UTTERANCE}
        if timestamp is not None:
            message["timestamp"] = timestamp

        try:
            await self.send_message(message)
        except TransportError as e:
            self._logger.warning("Error sending %s: %s", ClientMessageType.FORCE_END_OF_UTTERANCE, e)
            return
        self._finalize_sent_at = time.perf_counter()

    async def transcribe(
        self,
        source: BinaryIO,
        *,
        transcription_config: Optional[RTTranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Stream an audio source to the end, then close the session.

        Args:
            source: Audio source with a `read()` method, holding raw PCM in the session's
                audio format.
            transcription_config: Transcription config for the session.
            audio_format: Audio format. Must be 16 kHz raw PCM for the Agent STT service.
            translation_config: Optional translation config.
            audio_events_config: Optional audio event detection config.
            ws_headers: Additional WebSocket handshake headers.
            timeout: Maximum time in seconds to wait for the stream to finish.

        Raises:
            TimeoutError: If streaming exceeds the timeout.
            TranscriptionError: If the service reports an error.

        Examples:
            >>> with open("speech.raw", "rb") as audio:
            ...     await client.transcribe(audio)
            >>> print(client.transcript)
        """
        if transcription_config is not None:
            self._config = transcription_config
        if audio_format is not None:
            self._audio_format = audio_format

        if not self._is_connected:
            await self.start_session(
                transcription_config=self._config,
                audio_format=self._audio_format,
                translation_config=translation_config,
                audio_events_config=audio_events_config,
                ws_headers=ws_headers,
            )
            self._is_connected = True

        try:
            await asyncio.wait_for(
                self._audio_producer(source, self._audio_format.chunk_size),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise RTTimeoutError("Agent STT session timed out") from exc
        finally:
            self._is_connected = False
            self._is_ready_for_audio = False

    # ==========================================================================
    # Session output
    # ==========================================================================

    @property
    def transcript(self) -> str:
        """The final segments received so far, joined by the language's word delimiter."""
        return self._transcript.text()

    @property
    def segments(self) -> list[Segment]:
        """The final segments received so far, in order."""
        return self._transcript.segments

    @property
    def partial_segment(self) -> Optional[Segment]:
        """The segment currently being built, or None when there is nothing in flight."""
        return self._transcript.partial

    @property
    def timeline(self) -> list[TimedEvent]:
        """The speech and turn events received so far, in order."""
        return self._transcript.timeline

    @property
    def events(self) -> list[dict[str, Any]]:
        """Every raw server message received, in order, including unmodelled ones."""
        return self._transcript.events

    @property
    def session_info(self) -> SessionInfo:
        """Session identity and the language pack reported by the service."""
        return self._session_info

    @property
    def is_connected(self) -> bool:
        """Whether the session is open."""
        return self._is_connected

    @property
    def is_ready_for_audio(self) -> bool:
        """Whether the service has accepted the session, so audio will be sent."""
        return self._is_ready_for_audio

    @property
    def last_finalize_latency(self) -> float:
        """Seconds between the last `finalize()` and the segment it flushed."""
        return self._last_finalize_latency

    def transcript_text(self, *, include_partial: bool = False, speaker_labels: bool = False) -> str:
        """
        Render the transcript.

        Args:
            include_partial: Append the segment currently in flight.
            speaker_labels: Prefix each segment with its speaker label, where one is attributed.

        Returns:
            The transcript as text.

        Examples:
            >>> print(client.transcript_text(speaker_labels=True))
        """
        return self._transcript.text(include_partial=include_partial, speaker_labels=speaker_labels)

    def reset_transcript(self) -> None:
        """Drop the accumulated segments, timeline and event log."""
        self._transcript.reset()

    # ==========================================================================
    # Message handling
    # ==========================================================================

    def emit(self, event: Any, message: dict[str, Any]) -> None:
        """Record every server message before dispatching it to the application's handlers."""
        self._transcript.record(message)
        super().emit(event, message)

    def _on_session_started(self, message: dict[str, Any]) -> None:
        """Capture the session id and language pack, and open the audio gate."""
        self._session_info.session_id = message.get("id")
        self._session_info.language_pack_info = LanguagePackInfo.from_dict(message.get("language_pack_info") or {})
        self._transcript.set_delimiter(self._session_info.language_pack_info.word_delimiter)
        self._is_ready_for_audio = True

    def _on_segment(self, message: dict[str, Any]) -> None:
        """Accumulate a final segment, or refresh the live partial."""
        if message.get("message") != ServerMessageType.ADD_SEGMENT:
            self._transcript.add_partial_segment(message)
            return

        self._transcript.add_segment(message)
        if self._finalize_sent_at is not None:
            self._last_finalize_latency = time.perf_counter() - self._finalize_sent_at
            self._finalize_sent_at = None

    def _on_timed_event(self, message: dict[str, Any]) -> None:
        """Append a speech or turn event to the timeline."""
        self._transcript.add_timed_event(message)

    async def close(self) -> None:
        """Close the connection without waiting for outstanding messages."""
        self._is_ready_for_audio = False
        self._is_connected = False
        await super().close()


AgentSTTClient = AsyncClient
