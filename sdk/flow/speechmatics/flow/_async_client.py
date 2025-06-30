from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from typing import BinaryIO
from typing import Optional
from typing import Union

from ._auth import AuthBase
from ._auth import StaticKeyAuth
from ._events import EventEmitter
from ._exceptions import AudioError
from ._exceptions import ConfigurationError
from ._exceptions import ConversationEndedException
from ._exceptions import ConversationError
from ._exceptions import SessionError
from ._exceptions import TimeoutError
from ._logging import get_logger
from ._models import AddInput
from ._models import AudioFormat
from ._models import ClientMessageType
from ._models import ConnectionConfig
from ._models import ConversationConfig
from ._models import DebugMode
from ._models import ServerMessageType
from ._models import SessionInfo
from ._models import ToolFunctionParam
from ._transport import Transport
from ._utils.audio import read_audio_chunks

Tool = Union[ToolFunctionParam, dict[str, Any]]


class AsyncClient(EventEmitter):
    """
    High-level asynchronous client for the Speechmatics Flow API.

    The class wraps the low-level `Transport` WebSocket connection and exposes
    a *producer / consumer* task-pair which streams audio *to* the service and
    receives JSON / binary messages *from* it.

    Key Features
    ------------
    • Context-manager enabled: ``async with AsyncClient(...)`` guarantees
      cleanup of sockets, tasks and event-handlers.

    • Event-driven: subscribe with ``@client.on(ServerMessageType.X)`` to react
      to transcripts, LLM tool calls, warnings, etc.

    • Real-time pacing: frames are throttled according to sample-rate by
      default; can be disabled for batch uploads.

    • Minimal surface: only two public “action” methods –
        start_conversation(...) and close().
      Everything else is done through events.

    A typical usage pattern:

    >>> async with AsyncClient(api_key="live-xyz") as client:
    ...     @client.on(ServerMessageType.ADD_TRANSCRIPT)
    ...     def _on_transcript(msg):
    ...         print(msg["metadata"]["transcript"])
    ...
    ...     with open("pcm.raw", "rb") as mic:
    ...         await client.start_conversation(mic)

    Notes
    -----
    1. If you want to reuse the instance for multiple conversations you can
       call `start_conversation` repeatedly; an internal `SessionInfo` object
       tracks per-conversation state and is reset automatically.

    2. If you do *not* have an asyncio application you can still drive this
       client from synchronous code by running it inside
       ``asyncio.run(...)`` or by wrapping it in a thread.

    """

    __slots__ = ("_auth", "_url", "_conn_config", "_session", "_transport", "_logger", "_conversation_started")

    def __init__(
        self,
        auth: Optional[AuthBase] = None,
        *,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        conn_config: Optional[ConnectionConfig] = None,
    ) -> None:
        """
        Create a new AsyncClient.

        Parameters
        ----------
        auth
            An AuthBase implementation (e.g. JWTAuth).  If *None* a
            StaticKeyAuth instance is created from *api_key* or
            the ``SPEECHMATICS_API_KEY`` environment variable.
        api_key
            Convenience shortcut when using static keys and *auth* is None.
        url
            Override the Flow WebSocket endpoint; defaults to environment
            variable ``SPEECHMATICS_FLOW_URL`` or the public SaaS URL.
        conn_config
            Advanced connection settings such as reconnect policy
            and HTTP proxy support.

        Raises
        ------
        ConfigurationError
            When neither *auth* nor an API key can be resolved.

        """
        super().__init__()

        if auth is None:
            if not api_key and not os.getenv("SPEECHMATICS_API_KEY"):
                raise ConfigurationError(
                    "No authentication provided.  Supply `auth`, `api_key` or "
                    "set the SPEECHMATICS_API_KEY environment variable."
                )
            auth = StaticKeyAuth(api_key)

        self._auth = auth
        self._url = url or os.getenv("SPEECHMATICS_FLOW_URL") or "wss://flow.api.speechmatics.com/v1/flow"
        self._conn_config = conn_config or ConnectionConfig()
        self._session = SessionInfo(request_id=str(uuid.uuid4()))
        self._transport = Transport(self._url, self._conn_config, self._auth, self._session.request_id)

        self._logger = get_logger(__name__)
        self._conversation_started = asyncio.Event()

        self._logger.debug("AsyncClient created request_id=%s", self._session.request_id)

    @property
    def request_id(self) -> str:
        """Unique request-ID generated on construction (per client instance)."""
        return self._session.request_id

    @property
    def conversation_id(self) -> Optional[str]:
        """ID assigned by the service once the conversation actually starts."""
        return self._session.conversation_id

    @property
    def is_running(self) -> bool:
        """True while a conversation is active and audio is still streaming."""
        return self._session.is_running

    async def __aenter__(self) -> AsyncClient:
        """Return self so the instance can be used inside ``async with``."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Ensure we close sockets and cancel tasks on context exit."""
        await self.close()

    async def start_conversation(
        self,
        source: BinaryIO,
        *,
        conversation_config: Optional[ConversationConfig] = None,
        audio_format: Optional[AudioFormat] = None,
        tools: Optional[list[Tool]] = None,
        debug_mode: Optional[DebugMode] = None,
        ws_headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Begin a new Flow conversation and run it to completion.

        This coroutine blocks (i.e. awaits) until either:
        • the server sends *CONVERSATION_ENDED*,
        • an error occurs, **or**
        • the *timeout* elapses.

        Parameters
        ----------
        source
            Any binary-audio provider.  Must ultimately yield raw 16-bit PCM
            frames matching *audio_format*.
        conversation_config
            Template, variables, LLM model, etc.  Uses library defaults when
            omitted.
        audio_format
            Sample-rate / encoding / chunk-size (defaults are wide-band 16-kHz).
        tools
            A list of tool descriptors that the LLM may call.
        debug_mode
            Flags that make the server emit additional DEBUG messages.
        ws_headers
            Extra HTTP headers to add to the WebSocket upgrade request.
        timeout
            Maximum number of **seconds** before a ``TimeoutError`` is raised.
            *None* (default) waits indefinitely.

        Raises
        ------
        AudioError
            Invalid source or failure while reading the stream.
        TimeoutError
            Conversation did not finish within *timeout* seconds.
        ConversationError
            The server sent an ERROR message.
        """
        if source is None:
            raise AudioError("Audio source must be provided")

        conversation_config = conversation_config or ConversationConfig()
        audio_format = audio_format or AudioFormat()

        self._conversation_started.clear()

        self._logger.debug(
            "start_conversation: config=%s, audio_format=%s",
            conversation_config.to_dict(),
            audio_format.to_dict(),
        )

        try:
            await asyncio.wait_for(
                self._conversation_pipeline(
                    source,
                    audio_format,
                    conversation_config,
                    tools,
                    debug_mode,
                    ws_headers,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Conversation timed-out after {timeout} s") from exc
        except ConversationEndedException:
            # Normal end-of-conversation path
            pass
        finally:
            self._session.is_running = False

    async def close(self) -> None:
        """
        Gracefully close the WebSocket and cancel any background tasks.

        It is safe to call this method multiple times; subsequent calls become
        no-ops.

        The method tries to send the *AUDIO_ENDED* message first (unless the
        conversation has already finished), then closes the transport layer
        and finally removes **all** registered event listeners so that the
        client object can be reused or garbage-collected cleanly.
        """
        if self._session.is_running:
            try:
                await self._send_audio_ended()
            except Exception:
                self._logger.debug("Error sending AudioEnded in close()", exc_info=True)

        self._session.is_running = False

        try:
            await self._transport.close()
        except Exception:
            self._logger.debug("Transport.close() failed", exc_info=True)

        self.remove_all_listeners()

    async def _conversation_pipeline(
        self,
        source: BinaryIO,
        audio_format: AudioFormat,
        conversation_config: ConversationConfig,
        tools: Optional[list[Tool]],
        debug_mode: Optional[DebugMode],
        ws_headers: Optional[dict[str, str]],
    ) -> None:
        """
        Run producer + consumer tasks until one of them finishes or errors.

        This method never returns an error itself; any un-expected exception
        from sub-tasks is re-raised **after** both tasks have been cancelled /
        awaited, keeping the call-stack of `start_conversation` clean.
        """
        await self._transport.connect(ws_headers)

        await self._start_conversation(
            conversation_config,
            audio_format,
            tools,
            debug_mode,
        )

        producer = asyncio.create_task(
            self._audio_producer(source, audio_format),
            name="audio_producer",
        )
        consumer = asyncio.create_task(
            self._message_consumer(),
            name="message_consumer",
        )

        done, pending = await asyncio.wait({producer, consumer}, return_when=asyncio.FIRST_EXCEPTION)

        # Ensure that the “other” task sees its CancelledError and finalisers run
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        # If something went wrong – propagate
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, ConversationEndedException):
                raise exc

    async def _start_conversation(
        self,
        conversation_config: ConversationConfig,
        audio_format: AudioFormat,
        tools: Optional[list[Tool]],
        debug_mode: Optional[DebugMode],
    ) -> None:
        """
        Send the *START_CONVERSATION* message and switch the session to “running”.
        """
        msg: dict[str, Any] = {
            "message": ClientMessageType.START_CONVERSATION,
            "audio_format": audio_format.to_dict(),
            "conversation_config": conversation_config.to_dict(),
        }
        if tools:
            msg["tools"] = [t.to_dict() if isinstance(t, ToolFunctionParam) else t for t in tools]
        if debug_mode:
            msg["debug"] = debug_mode.to_dict()

        await self._transport.send_message(msg)
        self._session.is_running = True

    async def _audio_producer(self, source: BinaryIO, audio_format: AudioFormat) -> None:
        """
        Stream raw audio frames to the server.

        The coroutine waits until the server acknowledges the start
        (`_conversation_started` event).
        """
        await self._conversation_started.wait()
        self._logger.debug("Producer: conversation started, streaming audio")
        delay = 0.001

        try:
            async for frame in read_audio_chunks(source, audio_format.chunk_size):
                if not self._session.is_running:
                    break

                self._session.client_seq_no += 1
                await self._transport.send_message(frame)
                # yield control to the event loop
                await asyncio.sleep(delay)

            if self._session.is_running:
                await self._send_audio_ended()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.error("Audio producer error", exc_info=True)
            self._session.is_running = False
            raise AudioError("Failed to send audio") from exc

    async def _message_consumer(self) -> None:
        """
        Receive JSON / binary messages from the WebSocket and dispatch them.
        """
        delay = 0.001

        try:
            while self._session.is_running:
                try:
                    msg = await asyncio.wait_for(
                        self._transport.receive_message(),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    # yield control to the event loop
                    await asyncio.sleep(delay)
                    continue

                if isinstance(msg, bytes):
                    await self._handle_binary_message(msg)
                else:
                    await self._handle_json_message(msg)

        except asyncio.CancelledError:
            raise
        except ConversationEndedException:
            self._session.is_running = False
            raise
        except Exception as exc:
            self._logger.error("Message consumer error", exc_info=True)
            self._session.is_running = False
            raise SessionError("Message consumer error") from exc

    async def _handle_json_message(self, message: dict[str, Any]) -> None:
        """
        Convert *message['message']* to the enum and forward to event handlers.
        """
        msg_type = message.get("message")
        if not msg_type:
            return

        try:
            enum_type = ServerMessageType(msg_type)
        except ValueError:
            self._logger.warning("Unknown message type: %s", msg_type)
            return

        self._handle_server_message(enum_type, message)

        try:
            self.emit(enum_type, message)
        except Exception:
            self._logger.warning("User event-handler raised", exc_info=True)

    def _handle_server_message(self, msg_type: ServerMessageType, message: dict[str, Any]) -> None:
        """Internal state-machine for well-known server messages."""
        if msg_type == ServerMessageType.CONVERSATION_STARTED:
            self._session.conversation_id = message.get("id")
            self._conversation_started.set()

        elif msg_type == ServerMessageType.CONVERSATION_ENDED:
            self._session.is_running = False
            raise ConversationEndedException("Conversation completed normally")

        elif msg_type == ServerMessageType.INFO:
            self._logger.info("INFO: %s", message.get("reason", "unknown"))

        elif msg_type == ServerMessageType.WARNING:
            self._logger.warning("WARNING: %s", message.get("reason", "unknown"))

        elif msg_type == ServerMessageType.ERROR:
            self._session.is_running = False
            reason = message.get("reason", "unknown")
            self._logger.error("ERROR: %s", reason)
            raise ConversationError(reason)

        elif msg_type == ServerMessageType.DEBUG:
            self._logger.debug("DEBUG: %s", message.get("content", "—"))

    async def _handle_binary_message(self, message: Union[bytes, bytearray]) -> None:
        """
        Binary messages are assistant audio.  They are forwarded verbatim to
        subscribers of *ServerMessageType.ADD_AUDIO*.
        """
        try:
            self.emit(ServerMessageType.ADD_AUDIO, bytes(message))
        except Exception:
            self._logger.warning("User event-handler raised", exc_info=True)

    async def _send_audio_ended(self) -> None:
        """Notify the server that no more audio will be sent."""
        msg = {
            "message": ClientMessageType.AUDIO_ENDED,
            "last_seq_no": self._session.client_seq_no,
        }
        await self._transport.send_message(msg)

    async def send_input(
        self,
        *,
        input_text: str,
        immediate: bool = False,
        interrupt_response: bool = False,
    ) -> None:
        """
        Send an *AddInput* message to the server (textual user input).

        Parameters
        ----------
        input_text
            The actual text to feed into the LLM.
        immediate
            If *True* the text is processed immediately, bypassing turn-taking.
        interrupt_response
            If *True* the assistant’s current utterance (if any) is interrupted.
        """
        add_input = AddInput(
            input=input_text,
            immediate=immediate,
            interrupt_response=interrupt_response,
        )
        await self._transport.send_message(add_input.to_dict())

    async def send_tool_result(self, *, tool_call_id: str, content: str, status: str) -> None:
        """
        Return the result of a tool-function execution back to the LLM.

        Parameters
        ----------
        tool_call_id
            The *id* of the TOOL_CALL request we’re responding to.
        content
            Text string containing the result.
        status
            "ok", "failed", "rejected"
        """
        await self._transport.send_message(
            {
                "message": ClientMessageType.TOOL_RESULT,
                "id": tool_call_id,
                "content": content,
                "status": status,
            }
        )
