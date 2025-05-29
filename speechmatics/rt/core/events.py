"""
Simplified and type-safe event emitter for the Speechmatics RT SDK.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

from .logging import get_logger
from .models import ServerMessageType


class EventEmitter:
    """
    Type-safe event emitter for handling server messages.

    Supports both decorator and direct registration patterns.
    Only synchronous callbacks are supported for simplicity.
    """

    def __init__(self) -> None:
        self._handlers: dict[ServerMessageType, set[Callable]] = {}
        self._once_handlers: dict[ServerMessageType, set[Callable]] = {}
        self._logger = get_logger(__name__)

    def on(self, event: ServerMessageType, callback: Optional[Callable] = None) -> Callable:
        """
        Register persistent event handler.

        Args:
            event: The event type to listen for
            callback: The callback function (optional for decorator usage)

        Returns:
            The callback function or decorator

        Example:
            @client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_transcript(message):
                print(message["metadata"]["transcript"])
        """
        if callback is not None:
            self._add_handler(event, callback, persistent=True)
            return callback

        def decorator(func: Callable) -> Callable:
            self._add_handler(event, func, persistent=True)
            return func

        return decorator

    def once(self, event: ServerMessageType, callback: Optional[Callable] = None) -> Callable:
        """
        Register one-time event handler.

        Args:
            event: The event type to listen for
            callback: The callback function (optional for decorator usage)

        Returns:
            The callback function or decorator
        """
        if callback is not None:
            self._add_handler(event, callback, persistent=False)
            return callback

        def decorator(func: Callable) -> Callable:
            self._add_handler(event, func, persistent=False)
            return func

        return decorator

    def off(self, event: ServerMessageType, callback: Callable) -> None:
        """
        Remove event handler.

        Args:
            event: The event type
            callback: The callback to remove
        """
        self._handlers.get(event, set()).discard(callback)
        self._once_handlers.get(event, set()).discard(callback)

    def emit(self, event: ServerMessageType, message: dict[str, Any]) -> None:
        """
        Emit event to all registered handlers.

        Args:
            event: The event type
            message: The message data
        """
        # Call persistent handlers
        for callback in self._handlers.get(event, set()).copy():
            try:
                callback(message)
            except Exception as e:
                # Log error but don't stop other handlers
                self._logger.warning(
                    "event_handler_error", error=str(e), event=str(event), exc_info=True
                )

        # Call one-time handlers and remove them
        once_handlers = self._once_handlers.get(event, set()).copy()
        if once_handlers:
            self._once_handlers[event].clear()
            for callback in once_handlers:
                try:
                    callback(message)
                except Exception as e:
                    self._logger.warning(
                        "once_event_handler_error",
                        error=str(e),
                        event=str(event),
                        exc_info=True,
                    )

    def remove_all_listeners(self, event: Optional[ServerMessageType] = None) -> None:
        """
        Remove all listeners for an event, or all events if none specified.

        Args:
            event: Specific event type, or None for all events
        """
        if event is not None:
            self._handlers.pop(event, None)
            self._once_handlers.pop(event, None)
        else:
            self._handlers.clear()
            self._once_handlers.clear()

    def listeners(self, event: ServerMessageType) -> list[Callable]:
        """
        Get all listeners for an event.

        Args:
            event: The event type

        Returns:
            List of callback functions
        """
        persistent = list(self._handlers.get(event, set()))
        once = list(self._once_handlers.get(event, set()))
        return persistent + once

    def on_transcript(self, callback: Optional[Callable] = None) -> Callable:
        """
        Register handler for final transcript results.

        This is a convenience method for ServerMessageType.ADD_TRANSCRIPT.

        Args:
            callback: Function to handle transcript messages

        Returns:
            The callback function or decorator

        Examples:
            >>> @client.on_transcript
            >>> def handle_final(message):
            ...     result = TranscriptResult.from_message(message)
            ...     print(f"Final: {result.transcript}")
        """
        return self.on(ServerMessageType.ADD_TRANSCRIPT, callback)

    def on_partial(self, callback: Optional[Callable] = None) -> Callable:
        """
        Register handler for partial transcript results.

        This is a convenience method for ServerMessageType.ADD_PARTIAL_TRANSCRIPT.

        Args:
            callback: Function to handle partial transcript messages

        Returns:
            The callback function or decorator

        Examples:
            >>> @client.on_partial
            >>> def handle_partial(message):
            ...     result = TranscriptResult.from_message(message)
            ...     print(f"Partial: {result.transcript}")
        """
        return self.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT, callback)

    def on_error(self, callback: Optional[Callable] = None) -> Callable:
        """
        Register handler for error messages.

        This is a convenience method for ServerMessageType.ERROR.

        Args:
            callback: Function to handle error messages

        Returns:
            The callback function or decorator

        Examples:
            >>> @client.on_error
            >>> def handle_error(message):
            ...     print(f"Error: {message.get('reason', 'Unknown error')}")
        """
        return self.on(ServerMessageType.ERROR, callback)

    def on_translation(self, callback: Optional[Callable] = None) -> Callable:
        """
        Register handler for final translation results.

        This is a convenience method for ServerMessageType.ADD_TRANSLATION.

        Args:
            callback: Function to handle translation messages

        Returns:
            The callback function or decorator

        Examples:
            >>> @client.on_translation
            >>> def handle_translation(message):
            ...     print(f"Translation: {message['metadata']['translation']}")
        """
        return self.on(ServerMessageType.ADD_TRANSLATION, callback)

    def _add_handler(self, event: ServerMessageType, callback: Callable, persistent: bool) -> None:
        """Add handler to appropriate collection."""
        if inspect.iscoroutinefunction(callback):
            raise ValueError("Only synchronous callbacks are supported")

        if not callable(callback):
            raise TypeError("Callback must be callable")

        target = self._handlers if persistent else self._once_handlers
        if event not in target:
            target[event] = set()
        target[event].add(callback)
