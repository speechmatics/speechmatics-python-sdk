from __future__ import annotations

import asyncio
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
        self._eos_sent = False

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
        await self._start_recognition_session(
            transcription_config=transcription_config,
            audio_format=audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
            ws_headers=ws_headers,
        )

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
        seq_no = 0

        try:
            async for frame in src:
                if self._session_done_evt.is_set():
                    break

                try:
                    await self.send_audio(frame)
                    seq_no += 1
                except Exception as e:
                    self._logger.error("Failed to send audio frame: %s", e)
                    self._session_done_evt.set()
                    break

            await self._send_eos(seq_no)
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
