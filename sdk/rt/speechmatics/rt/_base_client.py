from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import uuid
from typing import Any
from typing import Callable
from typing import Optional

from typing_extensions import Self

from ._auth import AuthBase
from ._auth import StaticKeyAuth
from ._events import EventEmitter
from ._exceptions import TimeoutError
from ._exceptions import TranscriptionError
from ._exceptions import TransportError
from ._logging import get_logger
from ._models import AudioEventsConfig
from ._models import AudioFormat
from ._models import ConnectionConfig
from ._models import SessionInfo
from ._models import TranscriptionConfig
from ._models import TranslationConfig
from ._transport import Transport
from ._utils.message import build_start_recognition_message


class _BaseClient(EventEmitter):
    """
    Base client providing core WebSocket functionality for RT clients.

    This class handles the low-level plumbing that's common to all real-time
    clients, including connection management, message routing, and event handling.

    Parameters:
        transport: Pre-configured Transport instance for WebSocket communication.
    """

    def __init__(self, transport: Transport) -> None:
        super().__init__()
        self._transport = transport
        self._recv_task: Optional[asyncio.Task[None]] = None
        self._closed_evt = asyncio.Event()
        self._eos_sent = False
        self._audio_bytes_sent = 0
        self._seq_no = 0
        self._last_error_reason: Optional[str] = None

        self._session: SessionInfo
        self._session_done_evt: asyncio.Event
        self._build_transport: Callable[[str], Transport]

        if not hasattr(self, "_logger"):
            self._logger = get_logger("speechmatics.rt.base_client")

    @classmethod
    def _init_session_info(cls, request_id: Optional[str] = None) -> tuple[SessionInfo, asyncio.Event, asyncio.Event]:
        """
        Create common session state used by RT clients.

        This centralizes the creation of session state objects that are
        common across single and multi-channel clients, reducing duplication.

        Args:
            request_id: Optional request ID, generated if not provided

        Returns:
            Tuple of (session_info, recognition_started_event, session_done_event)
        """
        session = SessionInfo(request_id=request_id or str(uuid.uuid4()))
        recognition_started_evt = asyncio.Event()
        session_done_evt = asyncio.Event()

        return session, recognition_started_evt, session_done_evt

    @classmethod
    def _create_transport_from_config(
        cls,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
        request_id: Optional[str] = None,
        sdk_identifier: Optional[str] = None,
    ) -> Transport:
        """
        Create a Transport instance from common configuration parameters.

        Args:
            auth: Authentication instance or None to create from api_key
            api_key: API key for StaticKeyAuth (ignored if auth provided)
            url: WebSocket URL or None for default
            conn_config: Connection configuration or None for default
            request_id: Request ID for debugging/tracking
            sdk_identifier: Value reported to the service as `sm-sdk`, or None for this
                package's own identifier

        Returns:
            Configured Transport instance
        """
        auth = auth or StaticKeyAuth(api_key)
        url = url or os.getenv("SPEECHMATICS_RT_URL") or "wss://eu2.rt.speechmatics.com/v2"
        conn_config = conn_config or ConnectionConfig()
        request_id = request_id or str(uuid.uuid4())

        return Transport(url, conn_config, auth, request_id, sdk_identifier=sdk_identifier)

    async def _ws_connect(self, ws_headers: Optional[dict] = None) -> None:
        await self._transport.connect(ws_headers)
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def send_audio(self, payload: bytes) -> None:
        """
        Send an audio frame through the WebSocket.

        Examples:
            >>> audio_chunk = b""
            >>> await client.send_audio(audio_chunk)
        """
        if self._closed_evt.is_set() or self._eos_sent:
            raise TransportError("Client is closed")

        if not isinstance(payload, bytes):
            raise ValueError("Payload must be bytes")

        try:
            await self._transport.send_message(payload)
            self._audio_bytes_sent += len(payload)
            self._seq_no += 1
        except Exception:
            self._closed_evt.set()
            raise

    @property
    def audio_bytes_sent(self) -> int:
        """Number of audio bytes sent to the server."""
        return self._audio_bytes_sent

    @property
    def request_id(self) -> str:
        """Client-generated id for this session, used for tracing."""
        return self._session.request_id

    @property
    def session_id(self) -> Optional[str]:
        """Service-assigned session id, set once RecognitionStarted arrives."""
        return self._session.session_id

    async def send_message(self, message: dict[str, Any]) -> None:
        """
        Send a message through the WebSocket.

        Examples:
            >>> # Send JSON message
            >>> msg = json.dumps({"message": "StartRecognition", ...})
            >>> await client.send_message(msg)
        """
        if self._closed_evt.is_set() or self._eos_sent:
            raise TransportError("Client is closed")

        if not isinstance(message, dict):
            raise ValueError("Message must be a dict")

        try:
            data = json.dumps(message)
            await self._transport.send_message(data)
        except Exception:
            self._closed_evt.set()
            raise

    async def _recv_loop(self) -> None:
        """
        Background task that continuously receives and dispatches server messages.

        This coroutine runs for the lifetime of the connection, receiving messages
        from the WebSocket and emitting them as events. It handles graceful shutdown
        when cancelled and logs any unexpected errors.
        """
        try:
            while True:
                msg = await self._transport.receive_message()

                if isinstance(msg, dict) and "message" in msg:
                    self.emit(msg["message"], msg)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._logger.error("Receive loop error: %s", exc)
            self._closed_evt.set()
            self._session_done_evt.set()
            try:
                await self._transport.close()
            except Exception:
                pass  # Ignore close errors - we're already in error state
        finally:
            self._closed_evt.set()

    def _reset_session_events(self) -> None:
        """Clear the subclass-owned session-tracking events, for a fresh session."""
        raise NotImplementedError()

    def _begin_new_session(self) -> None:
        """
        Reset per-connection state for a fresh session on a client that already ran one.

        Without this, a second start_session()/transcribe() after close() would reuse a
        Transport that can never reconnect (Transport.close() is a one-way latch), under
        the request_id of a session that already ended.
        """
        self._session.request_id = str(uuid.uuid4())
        self._session.session_id = None
        self._reset_session_events()
        self._transport = self._build_transport(self._session.request_id)
        self._recv_task = None
        self._closed_evt = asyncio.Event()
        self._eos_sent = False
        self._audio_bytes_sent = 0
        self._seq_no = 0
        self._last_error_reason = None
        self._logger.debug("Starting new session (request_id=%s)", self._session.request_id)

    async def _start_recognition_session(
        self,
        *,
        transcription_config: Optional[TranscriptionConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        translation_config: Optional[TranslationConfig] = None,
        audio_events_config: Optional[AudioEventsConfig] = None,
        ws_headers: Optional[dict] = None,
    ) -> tuple[TranscriptionConfig, AudioFormat]:
        if self._closed_evt.is_set():
            self._begin_new_session()

        transcription_config = transcription_config or TranscriptionConfig()
        audio_format = audio_format or AudioFormat()

        if transcription_config.operating_point is not None:
            logging.warning(
                "TranscriptionConfig.operating_point is deprecated and will be removed in the future. Please use the model property instead."
            )

        start_recognition_message = build_start_recognition_message(
            transcription_config=transcription_config,
            audio_format=audio_format,
            translation_config=translation_config,
            audio_events_config=audio_events_config,
        )

        try:
            await self._ws_connect(ws_headers)
            await self.send_message(start_recognition_message)
            await self._wait_recognition_started()
        except BaseException:
            # BaseException, not Exception: a caller's own timeout cancels this via CancelledError.
            with contextlib.suppress(Exception):
                await self.close()
            raise

        return transcription_config, audio_format

    async def _wait_recognition_started(self, timeout: float = 5.0) -> None:
        """Wait for RecognitionStarted message from server."""
        raise NotImplementedError()

    async def _wait_started_or_session_done(self, started_evt: asyncio.Event, timeout: float) -> None:
        """
        Wait for `started_evt`, but stop as soon as the session ends first.

        Error and EndOfTranscript only set `_session_done_evt`, so without this a rejection
        before RecognitionStarted would report a bare timeout instead of why.

        Raises:
            TranscriptionError: The session ended (Error or EndOfTranscript) before
                RecognitionStarted, with the service's reason when one was reported.
            TimeoutError: Neither happened within `timeout`.
        """
        started = asyncio.create_task(started_evt.wait())
        session_done = asyncio.create_task(self._session_done_evt.wait())
        try:
            done, _ = await asyncio.wait({started, session_done}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (started, session_done):
                if not task.done():
                    task.cancel()

        if not done:
            raise TimeoutError("Timed out waiting for RecognitionStarted")
        if started_evt.is_set():
            return
        raise TranscriptionError(self._last_error_reason or "Session ended before RecognitionStarted")

    async def close(self) -> None:
        """
        Gracefully close the client connection and clean up resources.
        """
        self._closed_evt.set()

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            # CancelledError is a BaseException (3.8+), so suppress(Exception) alone misses it.
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(self._recv_task, timeout=2.0)

        await self._transport.close()
