"""
Asynchronous client for Speechmatics real-time transcription.

This module provides the main AsyncClient class that handles real-time
speech-to-text transcription using the Speechmatics RT API.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from typing import BinaryIO
from typing import Optional

from .events import EventEmitter
from .exceptions import AudioError
from .exceptions import ConfigurationError
from .exceptions import EndOfTranscriptError
from .exceptions import ForceEndSession
from .exceptions import SessionError
from .exceptions import TimeoutError
from .exceptions import TranscriptionError
from .helpers import read_audio_chunks
from .logging import get_logger
from .models import AudioEncoding
from .models import AudioEventsConfig
from .models import AudioFormat
from .models import ClientMessageType
from .models import ConnectionConfig
from .models import ServerMessageType
from .models import SessionInfo
from .models import TranscriptionConfig
from .models import TranslationConfig
from .transport import Transport


class AsyncClient(EventEmitter):
    """
    Asynchronous client for Speechmatics real-time audio transcription.

    This client provides a full-featured async interface to the Speechmatics RT API,
    supporting real-time audio streaming, event-driven transcript handling, and
    comprehensive error management.

    Args:
        api_key: Speechmatics API key for authentication. If not provided,
                uses the SPEECHMATICS_API_KEY environment variable.
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

        With custom configuration:
            >>> config = ConnectionConfig(
            ...     url="wss://eu2.rt.speechmatics.com/v2",
            ...     api_key="your-key",
            ... )
            >>> async with AsyncClient(conn_config=config) as client:
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
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        """
        Initialize the AsyncClient.

        Args:
            api_key: Speechmatics API key. If None, uses SPEECHMATICS_API_KEY env var.
            url: WebSocket endpoint URL. If None, uses SPEECHMATICS_RT_URL env var
                 or defaults to EU endpoint.
            conn_config: Complete connection configuration. Overrides api_key and url.

        Raises:
            ConfigurationError: If API key is not provided and not found in environment.
        """
        super().__init__()

        if conn_config:
            self._conn_config = conn_config
        else:
            api_key = api_key or os.environ.get("SPEECHMATICS_API_KEY")
            if not api_key:
                raise ConfigurationError("API key required: provide api_key parameter or set SPEECHMATICS_API_KEY")

            url = url or os.environ.get("SPEECHMATICS_RT_URL", "wss://eu2.rt.speechmatics.com/v2")
            self._conn_config = ConnectionConfig(url=url, api_key=api_key)  # type: ignore[arg-type]

        self._session = SessionInfo(request_id=str(uuid.uuid4()))
        self._transport = Transport(self._conn_config, self._session.request_id)
        self._logger = get_logger(__name__)
        self._recognition_started = asyncio.Event()
        self._seq_no = 0
        self._logger = self._logger.bind(request_id=self._session.request_id)

    async def __aenter__(self) -> AsyncClient:
        """
        Async context manager entry.

        Returns:
            Self for use in async with statements.

        Examples:
            >>> async with AsyncClient(api_key="key") as client:
            ...     await client.transcribe(audio_stream)
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Async context manager exit with automatic cleanup.

        Ensures all resources are properly cleaned up when exiting the
        async context manager, including closing connections and removing
        event listeners.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        await self.close()

    async def transcribe(
        self,
        audio_stream: BinaryIO,
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        This is the main method for transcribing audio. It establishes a WebSocket
        connection to the Speechmatics RT API, streams audio data, and processes
        transcription results through registered event handlers.

        The method handles the complete transcription workflow:
        1. Validates input parameters
        2. Establishes WebSocket connection
        3. Starts recognition session
        4. Streams audio data concurrently with receiving results
        5. Handles session completion and cleanup

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
            AudioError: If the audio stream is invalid or audio processing fails.
            AuthenticationError: If API key is invalid or authentication fails.
            ConnectionError: If connection to the service cannot be established.
            SessionError: If there's an error in session management.
            TimeoutError: If the operation exceeds the specified timeout.
            TranscriptionError: If transcription processing fails.
            EndOfTranscriptError: Normal completion signal (caught internally).
            ForceEndSession: If session is terminated early by user code.

        Examples:
            Basic transcription:
                >>> async with AsyncClient(api_key="key") as client:
                ...     @client.on(ServerMessageType.ADD_TRANSCRIPT)
                ...     def handle_result(message):
                ...         result = TranscriptResult.from_message(message)
                ...         print(result.transcript)
                ...
                ...     with open("audio.wav", "rb") as audio:
                ...         await client.transcribe(audio)

            With custom configuration:
                >>> config = TranscriptionConfig(
                ...     language="es",
                ...     enable_partials=True,
                ...     enable_entities=True
                ... )
                >>> audio_format = AudioFormat(
                ...     encoding=AudioEncoding.PCM_S16LE,
                ...     sample_rate=16000
                ... )
                >>>
                >>> await client.transcribe(
                ...     audio_stream,
                ...     transcription_config=config,
                ...     audio_format=audio_format,
                ...     timeout=300.0
                ... )
        """
        if not audio_stream:
            raise AudioError("Audio stream cannot be None")

        transcription_config = transcription_config or TranscriptionConfig()
        audio_format = audio_format or AudioFormat(encoding=AudioEncoding.PCM_S16LE)

        self._session.is_running = False
        self._recognition_started.clear()
        self._end_of_stream_sent = False
        self._seq_no = 0

        try:
            await asyncio.wait_for(
                self._run_transcription(
                    audio_stream,
                    transcription_config,
                    audio_format,
                    translation_config,
                    audio_events_config,
                    ws_headers,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Transcription timed out after {timeout} seconds")
        except (EndOfTranscriptError, ForceEndSession):
            # Normal completion
            pass
        finally:
            self._session.is_running = False

    async def close(self) -> None:
        """
        Close the client and cleanup all resources.

        This method ensures proper cleanup of all client resources including:
        - Sending end-of-stream message if not already sent
        - Closing WebSocket connection
        - Removing all registered event listeners
        - Marking session as not running

        Examples:
            >>> client = AsyncClient(api_key="key")
            >>> try:
            ...     await client.transcribe(audio_stream)
            >>> finally:
            ...     await client.close()
        """
        self._session.is_running = False

        try:
            if not self._end_of_stream_sent:
                await self._send_end_of_stream()
        except Exception:
            pass

        try:
            await self._transport.close()
        except Exception:
            pass

        self.remove_all_listeners()

    async def _run_transcription(
        self,
        audio_stream: BinaryIO,
        transcription_config: TranscriptionConfig,
        audio_format: AudioFormat,
        translation_config: Optional[TranslationConfig],
        audio_events_config: Optional[AudioEventsConfig],
        ws_headers: Optional[dict],
    ) -> None:
        """
        This internal method orchestrates the entire transcription process:
        1. Establishes WebSocket connection
        2. Sends start recognition message
        3. Waits for recognition confirmation
        4. Runs audio streaming and message receiving concurrently

        Args:
            audio_stream: Audio data source to transcribe.
            transcription_config: Transcription configuration settings.
            audio_format: Audio format specification.
            translation_config: Optional translation configuration.
            audio_events_config: Optional audio events configuration.
            ws_headers: Additional WebSocket headers.
        """
        await self._transport.connect(ws_headers)

        await self._start_recognition(
            transcription_config,
            audio_format,
            translation_config,
            audio_events_config,
        )

        await asyncio.gather(
            self._audio_producer(audio_stream, audio_format),
            self._message_consumer(),
            return_exceptions=True,
        )

    async def _start_recognition(
        self,
        transcription_config: TranscriptionConfig,
        audio_format: AudioFormat,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
    ) -> None:
        """
        Send StartRecognition message to begin transcription session.

        Constructs and sends the StartRecognition message with the specified
        transcription and audio format configuration to initialize the
        transcription session.

        Args:
            transcription_config: Configuration for transcription behavior.
            audio_format: Audio format specification for the session.
            translation_config: Optional configuration for translation.
            audio_events_config: Optional configuration for audio events.

        Raises:
            TransportError: If sending the message fails.
        """
        start_message = {
            "message": ClientMessageType.START_RECOGNITION,
            "audio_format": audio_format.to_dict(),
            "transcription_config": transcription_config.to_dict(),
        }

        if translation_config:
            start_message["translation_config"] = translation_config.to_dict()

        if audio_events_config:
            start_message["audio_events_config"] = audio_events_config.to_dict()

        await self._transport.send_message(start_message)
        self._session.is_running = True

    async def _audio_producer(self, audio_stream: BinaryIO, audio_format: AudioFormat) -> None:
        """
        This method continuously reads audio chunks from the input stream and
        sends them to the service via WebSocket. It handles the audio streaming
        loop and sends an end-of-stream message when complete.

        Args:
            audio_stream: Audio data source with read() method.
            audio_format: Audio format specification including chunk size.

        Raises:
            AudioError: If audio reading or sending fails.
        """
        await self._recognition_started.wait()
        try:
            while self._session.is_running:
                async for chunk in read_audio_chunks(audio_stream, audio_format.chunk_size):
                    self._seq_no += 1
                    await self._transport.send_message(chunk)

                # Break out of the loop when EOF is reached
                break

            await self._send_end_of_stream()

        except Exception as e:
            self._logger.error(f"Audio sender error: {e}")
            self._session.is_running = False
            raise AudioError(f"Failed to send audio: {e}")

    async def _message_consumer(self) -> None:
        """
        Continuously receive and process messages from the transcription service.

        This method runs a message receiving loop that handles all incoming
        messages from the server including transcription results, errors, and
        session control messages. It processes each message and routes them
        to appropriate handlers.

        The method uses timeouts to avoid blocking indefinitely and handles
        connection closure gracefully with specific error detection for
        authentication failures.

        Raises:
            AuthenticationError: If authentication fails or connection is closed
                                due to invalid credentials.
            SessionError: For other session or connection errors.
        """
        try:
            while self._session.is_running:
                try:
                    message = await asyncio.wait_for(
                        self._transport.receive_message(),
                        timeout=1.0,
                    )
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    continue

        except (EndOfTranscriptError, ForceEndSession):
            # These are expected control flow exceptions, not errors
            # EndOfTranscriptError signals normal completion
            # ForceEndSession signals user-requested early termination
            self._session.is_running = False
            raise

        except Exception as e:
            self._logger.error("session_error", error=str(e))
            self._session.is_running = False
            raise SessionError(f"Message receiver error: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """
        Process an incoming message from the transcription service.

        This method handles different types of server messages including:
        - RecognitionStarted: Marks recognition as started
        - EndOfTranscript: Signals transcription completion
        - Error: Handles various error conditions
        - All other messages: Emitted as events to registered handlers

        Args:
            message: The message dictionary received from the server.

        Raises:
            AuthenticationError: For authentication-related errors.
            SessionError: For other server errors.
            EndOfTranscriptError: When transcription completes normally.
            ForceEndSession: If user code requests early termination.
        """
        message_type = message.get("message")

        if not message_type:
            return

        try:
            server_msg_type = ServerMessageType(message_type)
        except ValueError:
            self._logger.warning("unknown_message_type", message_type=message_type)
            return

        if server_msg_type == ServerMessageType.RECOGNITION_STARTED:
            self._session.session_id = message.get("id")
            self._recognition_started.set()
            self._logger.info("recognition_started", session_id=self._session.session_id)

        elif server_msg_type == ServerMessageType.END_OF_TRANSCRIPT:
            self._session.is_running = False
            self._logger.info("transcription_completed", session_id=self._session.session_id)
            raise EndOfTranscriptError("Transcription completed")

        elif server_msg_type == ServerMessageType.WARNING:
            self._logger.warning("session_warning", session_id=self._session.session_id, warning=message["reason"])

        elif server_msg_type == ServerMessageType.ERROR:
            self._session.is_running = False
            self._logger.error("transcription_error", session_id=self._session.session_id, error=message["reason"])
            raise TranscriptionError(message["reason"])

        try:
            self.emit(server_msg_type, message)
        except ForceEndSession:
            self._logger.warning(
                "force_end_session",
                session_id=self._session.session_id,
                warning="Session was ended forcefully by an event handler.",
            )
            self._session.is_running = False
            raise
        except Exception as e:
            self._logger.warning("event_handler_error", error=str(e))

    async def _send_end_of_stream(self) -> None:
        """
        This method constructs and sends the EndOfStream message to notify
        the server that no more audio data will be sent. It includes the
        last sequence number for tracking.

        Raises:
            TransportError: If sending the message fails.
        """
        if self._end_of_stream_sent:
            return

        end_message = {
            "message": ClientMessageType.END_OF_STREAM,
            "last_seq_no": self._seq_no,
        }
        await self._transport.send_message(end_message)
        self._end_of_stream_sent = True
