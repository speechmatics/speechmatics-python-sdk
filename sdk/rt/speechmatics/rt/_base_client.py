from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from typing import Any
from typing import Optional

from ._auth import AuthBase
from ._auth import StaticKeyAuth
from ._events import EventEmitter
from ._exceptions import TransportError
from ._logging import get_logger
from ._models import ConnectionConfig
from ._models import SessionInfo
from ._transport import Transport


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

        self._logger = get_logger(__name__)

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
    ) -> Transport:
        """
        Create a Transport instance from common configuration parameters.

        Args:
            auth: Authentication instance or None to create from api_key
            api_key: API key for StaticKeyAuth (ignored if auth provided)
            url: WebSocket URL or None for default
            conn_config: Connection configuration or None for default
            request_id: Request ID for debugging/tracking

        Returns:
            Configured Transport instance
        """
        auth = auth or StaticKeyAuth(api_key)
        url = url or os.getenv("SPEECHMATICS_RT_URL") or "wss://eu2.rt.speechmatics.com/v2"
        conn_config = conn_config or ConnectionConfig()
        request_id = request_id or str(uuid.uuid4())

        return Transport(url, conn_config, auth, request_id)

    async def __aenter__(self) -> _BaseClient:
        await self._transport.connect({})
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _send_message(self, payload: Any) -> None:
        """
        Send a message through the WebSocket.

        Args:
            payload: Message data (dict for JSON messages, bytes for audio).

        Raises:
            Any exception from transport layer.
        """
        if self._closed_evt.is_set():
            raise TransportError("Client is closed")

        try:
            await self._transport.send_message(payload)
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
            try:
                await self._transport.close()
            except Exception:
                pass  # Ignore close errors - we're already in error state
        finally:
            self._closed_evt.set()

    async def close(self) -> None:
        """
        Gracefully close the client connection and clean up resources.
        """
        self._closed_evt.set()

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._recv_task, timeout=2.0)

        await self._transport.close()
