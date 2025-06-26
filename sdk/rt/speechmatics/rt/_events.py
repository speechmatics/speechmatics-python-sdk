from __future__ import annotations

import inspect
from typing import Any
from typing import Callable
from typing import Optional

from ._logging import get_logger
from ._models import ServerMessageType


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
                self._logger.warning("Event handler error (%s): %s", event, e, exc_info=True)

        # Call one-time handlers and remove them
        once_handlers = self._once_handlers.get(event, set()).copy()
        if once_handlers:
            self._once_handlers[event].clear()
            for callback in once_handlers:
                try:
                    callback(message)
                except Exception as e:
                    self._logger.warning("One-time event handler error (%s): %s", event, e, exc_info=True)

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
