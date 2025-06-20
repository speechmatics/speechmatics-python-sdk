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
from ._framers import RawFramer
from ._logging import get_logger
from ._models import AudioEventsConfig
from ._models import AudioFormat
from ._models import ClientMessageType
from ._models import ConnectionConfig
from ._models import ServerMessageType
from ._models import TranscriptionConfig
from ._models import TranslationConfig
from ._sources import FileSource


class AsyncClient(_BaseClient):
    """
    Asynchronous client for Speechmatics real-time audio transcription.

    This client provides a full-featured async interface to the Speechmatics RT API,
    supporting real-time audio streaming, event-driven transcript handling, and
    comprehensive error management.

    Args:
        auth: Authentication instance. If not provided, uses StaticKeyAuth
                with api_key parameter or SPEECHMATICS_API_KEY environment variable.
        api_key: Speechmatics API key (used only if auth not provided).
        url: WebSocket endpoint URL. If not provided, uses SPEECHMATICS_RT_URL
                environment variable or defaults to EU endpoint.
        conn_config: Complete connection configuration object. If provided, overrides
                api_key and url parameters.

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
        self._logger = get_logger(__name__)

        self._session, self._recognition_started_evt, self._session_done_evt = self._init_session_info()
        self._eos_sent = False

        transport = self._create_transport_from_config(
            auth=auth, api_key=api_key, url=url, conn_config=conn_config, request_id=self._session.request_id
        )
        super().__init__(transport)

        self.on(ServerMessageType.RECOGNITION_STARTED, self._on_recognition_started)
        self.on(ServerMessageType.END_OF_TRANSCRIPT, self._on_eot)
        self.on(ServerMessageType.ERROR, self._on_error)
        self.on(ServerMessageType.WARNING, self._on_warning)

        self._logger.debug("AsyncClient initialized (request_id=%s)", self._session.request_id)

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
            audio_stream: Audio data source with a read() method. Can be a file
                        object, BytesIO, or any object supporting the binary
                        read interface.
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
            AudioError: If audio_stream is invalid or cannot be read.
            TimeoutError: If transcription exceeds the specified timeout.
            TranscriptionError: If the server reports an error during transcription.
            ConnectionError: If the WebSocket connection fails.

        Examples:
            Basic transcription:
            >>> with open("speech.wav", "rb") as audio:
            ...     await client.transcribe(audio)

            With custom configuration:
            >>> config = TranscriptionConfig(
            ...     language="es",
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
            raise AudioError("source cannot be None")

        transcription_config = transcription_config or TranscriptionConfig()
        audio_format = audio_format or AudioFormat()

        await self._transport.connect(ws_headers)

        start_recognition_msg = {
            "message": ClientMessageType.START_RECOGNITION,
            "audio_format": audio_format.to_dict(),
            "transcription_config": transcription_config.to_dict(),
        }

        if translation_config:
            start_recognition_msg["translation_config"] = translation_config.to_dict()
        if audio_events_config:
            start_recognition_msg["audio_events_config"] = audio_events_config.to_dict()

        await self._send_message(start_recognition_msg)

        try:
            await asyncio.wait_for(self._recognition_started_evt.wait(), timeout=5.0)
            await asyncio.wait_for(self._run_audio_pipeline(source, audio_format), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Transcription timed out") from exc

    async def _run_audio_pipeline(self, source: BinaryIO, audio_format: AudioFormat) -> None:
        """
        Run the audio streaming pipeline and wait for completion.

        This method orchestrates the audio streaming process by starting the
        audio producer task and waiting for the session to complete. It ensures
        proper cleanup even if the producer encounters errors.

        Args:
            source: The audio source to stream
            audio_format: Audio format configuration
        """
        producer = asyncio.create_task(self._audio_producer(source, audio_format))
        await self._session_done_evt.wait()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(producer, timeout=2.0)

    async def _audio_producer(self, source: BinaryIO, audio_format: AudioFormat) -> None:
        """
        Continuously read from source and send data to the server.

        This method reads audio data in chunks and sends it as binary WebSocket
        frames. It includes progress logging and automatically sends an EOF
        marker when the stream is exhausted.

        Args:
            source: File-like object to read audio from
            audio_format: Audio format configuration for chunk sizing
        """
        framer = RawFramer()
        fs = FileSource(source, chunk_size=audio_format.chunk_size)
        seq_no = 0

        try:
            async for chunk in fs:
                if self._session_done_evt.is_set():
                    break

                seq_no += 1

                try:
                    await self._send_message(framer.encode(chunk))
                except Exception as e:
                    self._logger.error("Failed to send audio chunk: %s", e)
                    self._session_done_evt.set()
                    break

            if not self._eos_sent and not self._session_done_evt.is_set():
                try:
                    await self._send_message(framer.eos(seq_no))
                except Exception as e:
                    self._logger.error("Failed to send EndOfStream message: %s", e)
                finally:
                    self._eos_sent = True
        except Exception as e:
            self._logger.error("Audio producer error: %s", e)
            self._session_done_evt.set()

    def _on_recognition_started(self, msg: dict[str, Any]) -> None:
        """Handle RecognitionStarted message from server."""
        self._session.session_id = msg.get("id")
        self._recognition_started_evt.set()
        self._logger.debug("Recognition started (session_id=%s)", self._session.session_id)

    def _on_eot(self, _msg: dict[str, Any]) -> None:
        """Handle EndOfTranscript message from server."""
        self._logger.debug("Received EndOfTranscript message")
        self._session_done_evt.set()

    def _on_error(self, msg: dict[str, Any]) -> None:
        """Handle Error message from server."""
        error = msg.get("reason", "uknown")
        self._logger.error("Server error: %s", error)
        self._session_done_evt.set()
        raise TranscriptionError(error)

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
