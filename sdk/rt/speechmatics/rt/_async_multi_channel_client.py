from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from typing import BinaryIO
from typing import Optional

from ._auth import AuthBase
from ._base_client import _BaseClient
from ._exceptions import AudioError
from ._exceptions import TimeoutError
from ._exceptions import TranscriptionError
from ._framers import JsonB64Framer
from ._logging import get_logger
from ._models import AudioEventsConfig
from ._models import AudioFormat
from ._models import ClientMessageType
from ._models import ConnectionConfig
from ._models import ServerMessageType
from ._models import TranscriptionConfig
from ._models import TranslationConfig
from ._sources import DictSource


class AsyncMultiChannelClient(_BaseClient):
    """
    Async client for multi-channel real-time audio transcription.

    This client enables simultaneous transcription of multiple audio streams
    over a single WebSocket connection. Each audio stream is identified by a
    channel ID, and the server provides channel-tagged transcription results.

    The client handles multiple audio sources using a round-robin approach to
    ensure fair bandwidth distribution across channels. Audio data is base64-encoded
    and wrapped in JSON messages for transmission.

    Args:
        auth: Authentication instance (StaticKeyAuth or JWTAuth). If not provided,
              will create StaticKeyAuth from api_key parameter.
        api_key: API key for authentication. Ignored if auth is provided.
                Can also be set via SPEECHMATICS_API_KEY environment variable.
        url: WebSocket URL for the RT API. Defaults to EU endpoint.
            Can be overridden via SPEECHMATICS_RT_URL environment variable.
        conn_config: WebSocket connection configuration (timeouts, limits, etc.).
                    Uses sensible defaults if not provided.

    Examples:
        Transcribing stereo audio:
        >>> sources = {
        ...     "left": open("left_channel.wav", "rb"),
        ...     "right": open("right_channel.wav", "rb")
        ... }
        >>> async with AsyncMultiChannelClient(api_key="your-key") as client:
        ...     @client.on(ServerMessageType.ADD_TRANSCRIPT)
        ...     def handle_transcript(msg):
        ...         channel = msg['results'][0]['channel']
        ...         transcript = msg['metadata']['transcript']
        ...         print(f"Channel {channel}: {transcript}")
        ...
        ...     await client.transcribe(sources)
    """

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self._logger = get_logger(__name__)

        self._session, self._rec_started_evt, self._session_done_evt = self._init_session_info()
        self._eos_sent = False

        transport = self._create_transport_from_config(
            auth=auth, api_key=api_key, url=url, conn_config=conn_config, request_id=self._session.request_id
        )

        super().__init__(transport)

        self.on(ServerMessageType.RECOGNITION_STARTED, self._on_recognition_started)
        self.on(ServerMessageType.END_OF_TRANSCRIPT, self._on_eot)
        self.on(ServerMessageType.ERROR, self._on_error)
        self.on(ServerMessageType.WARNING, self._on_warning)

        self._logger.debug(
            "AsyncMultiChannelClient initialized (request_id=%s)",
            self._session.request_id,
        )

    async def transcribe(
        self,
        sources: dict[str, BinaryIO],
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Transcribe multiple audio streams simultaneously in real-time.

        This method establishes a WebSocket connection, configures the transcription
        session for multiple channels, streams audio data from all sources in a
        round-robin fashion, and processes results through registered event handlers.

        Args:
            sources: Dictionary mapping channel IDs to file-like objects containing
                    audio data. Keys are channel identifiers (e.g., "left", "right").
                    Values must be opened in binary mode ('rb').
                    Example: {"left": open("left.wav", "rb"), "right": open("right.wav", "rb")}
            transcription_config: Configuration for transcription behavior such as
                                language, partial transcripts, and advanced features.
                                Uses default if not provided.
            audio_format: Audio format specification including encoding, sample rate,
                        and chunk size. Uses default (PCM 16-bit LE, 44.1kHz) if
                        not provided.
            ws_headers: Additional HTTP headers to include in the WebSocket handshake.
            timeout: Maximum time in seconds to wait for transcription completion.
                    Uses connection default if not provided.
        Raises:
            AudioError: If sources is empty or contains invalid audio streams.
            TimeoutError: If transcription exceeds the specified timeout.
            TranscriptionError: If the server reports an error during transcription.
            ConnectionError: If the WebSocket connection fails.

        Examples:
            Basic multi-channel transcription:
            >>> sources = {
            ...     "left": open("left_channel.wav", "rb"),
            ...     "right": open("right_channel.wav", "rb")
            ... }
            >>> await client.transcribe(sources)

            With custom configuration:
            >>> config = TranscriptionConfig(
            ...     language="es",
            ...     enable_partials=True,
            ...     diarization="speaker"
            ... )
            >>> audio_fmt = AudioFormat(
            ...     encoding=AudioEncoding.PCM_S16LE,
            ...     sample_rate=16000
            ... )
            >>> sources = {
            ...     "mic1": open("mic1.raw", "rb"),
            ...     "mic2": open("mic2.raw", "rb"),
            ...     "mic3": open("mic3.raw", "rb")
            ... }
            >>> await client.transcribe(
            ...     sources,
            ...     transcription_config=config,
            ...     audio_format=audio_fmt,
            ... )

        Note:
            - All audio sources should have the same format (sample rate, encoding)
            - Channels are processed in round-robin order for fair bandwidth usage
            - Results include channel identification for stream disambiguation
            - File handles should remain open for the duration of transcription
        """
        if not sources:
            raise AudioError("sources mapping cannot be empty")

        transcription_config = transcription_config or TranscriptionConfig()
        audio_format = audio_format or AudioFormat()

        await self._transport.connect(ws_headers)

        start_recognition_message = {
            "message": ClientMessageType.START_RECOGNITION,
            "audio_format": audio_format.to_dict(),
            "transcription_config": transcription_config.to_dict(),
        }

        if translation_config:
            start_recognition_message["translation_config"] = translation_config.to_dict()

        if audio_events_config:
            start_recognition_message["audio_events_config"] = audio_events_config.to_dict()

        await self._send_message(start_recognition_message)

        try:
            await asyncio.wait_for(self._rec_started_evt.wait(), timeout=5.0)
            await asyncio.wait_for(self._run_audio_pipeline(sources, audio_format), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Transcription timed out") from exc

    async def _run_audio_pipeline(self, sources: dict[str, BinaryIO], audio_format: AudioFormat) -> None:
        """
        Run the multi-channel audio streaming pipeline and wait for completion.

        This method orchestrates the multi-channel audio streaming process by
        starting the audio producer task and waiting for the session to complete.
        It ensures proper cleanup even if the producer encounters errors.

        Args:
            sources: Dictionary of channel IDs to audio file handles
            audio_format: Audio format configuration
        """
        producer = asyncio.create_task(self._producer(sources, audio_format))
        await self._session_done_evt.wait()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(producer, timeout=2.0)

    async def _producer(self, sources: dict[str, BinaryIO], audio_format: AudioFormat) -> None:
        """
        Continuously read from multiple audio sources and send data to the server.

        This method implements round-robin reading across all channels, ensuring
        fair bandwidth distribution. Each audio chunk is base64-encoded and wrapped
        in a JSON message with channel identification. Progress is logged periodically
        and EOF markers are sent when all streams are exhausted.

        Args:
            sources: Dictionary mapping channel IDs to file-like objects
            audio_format: Audio format configuration for chunk sizing
        """
        framer = JsonB64Framer()
        src = DictSource(sources, chunk_size=audio_format.chunk_size)
        seq_no = 0

        try:
            async for cid, chunk in src:
                if self._session_done_evt.is_set():
                    break

                seq_no += 1
                frame = framer.encode(cid, chunk)

                try:
                    await self._send_message(frame)
                except Exception as e:
                    self._logger.error("Failed to send audio chunk for channel %s: %s", cid, e)
                    self._session_done_evt.set()
                    break

            if not self._eos_sent and not self._session_done_evt.is_set():
                try:
                    for cid in sources:
                        await self._send_message(framer.eos(cid, seq_no))
                except Exception as e:
                    self._logger.error("Failed to send EOF markers: %s", e)
                finally:
                    self._eos_sent = True
        except Exception as e:
            self._logger.error("Audio producer error: %s", e)
            self._session_done_evt.set()

    def _on_recognition_started(self, msg: dict[str, Any]) -> None:
        """Handle RecognitionStarted message from server."""
        self._session.session_id = msg.get("id")
        self._rec_started_evt.set()
        self._logger.debug(
            "Recognition started (session_id=%s)",
            self._session.session_id,
        )

    def _on_eot(self, msg: dict[str, Any]) -> None:
        """Handle EndOfTranscript message from server."""
        self._session_done_evt.set()

    def _on_error(self, msg: dict[str, Any]) -> None:
        """Handle Error message from server."""
        self._session_done_evt.set()
        raise TranscriptionError(msg.get("reason", "unknown"))

    def _on_warning(self, msg: dict[str, Any]) -> None:
        """Handle Warning message from server."""
        self._logger.warning("Server warning: %s", msg.get("reason", "unknown"))

    async def close(self) -> None:
        """
        Close the client and clean up resources.

        Ensures the session is marked as complete and delegates to the base
        class for full cleanup including WebSocket connection termination.
        """
        self._session_done_evt.set()
        await super().close()
