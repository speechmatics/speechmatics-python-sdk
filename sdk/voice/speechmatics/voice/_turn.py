#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import asyncio
from typing import Callable
from typing import Optional


class TurnTaskProcessor:
    """Container for turn task processing.

    This utility is used to make sure that all processing is completed within a turn. When a
    process is added, once it completes and all other tasks have also completed, then it will
    make a call to the `done_callback` function (sync or async).
    """

    def __init__(self, name: str, turn_id: int = 0, done_callback: Optional[Callable] = None):
        """Create new handler.

        Args:
            name: The name of the processor.
            turn_id: The turn id (used to validate tasks).
            done_callback: The callback to call when all tasks are completed.
        """

        # Processor name
        self._name = name

        # Turn id (used to validate tasks)
        self._turn_id = turn_id
        self._turn_active = False

        # Tasks + events
        self._tasks: dict[str, asyncio.Task] = {}
        self._listener_tasks: list[asyncio.Task] = []

        # Done callback (can be async)
        self._done_callback: Optional[Callable] = done_callback

    @property
    def has_pending_tasks(self) -> bool:
        """Check for any pending tasks.

        Returns:
            True if there are pending tasks, False otherwise.
        """
        return any(not task.done() for task in self._tasks.values())

    @property
    def turn_id(self) -> int:
        """Get the turn id.

        Returns:
            The current turn ID.
        """
        return self._turn_id

    @property
    def turn_active(self) -> bool:
        """Get the turn active state.

        Returns:
            The current turn active state.
        """
        return self._turn_active

    def update_timer(self, delay: float) -> None:
        """Set a new done trigger.

        Args:
            delay: Delay in seconds before triggering done callback.
        """
        if delay < 0:
            return
        self.add_task(
            asyncio.create_task(asyncio.sleep(delay)),
            "done_task",
        )

    def add_task(self, task: asyncio.Task, task_name: str) -> None:
        """Add a task to the end of turn.

        Args:
            task: The asyncio task to add.
            task_name: Name identifier for the task.
        """

        # Cancel any same-named tasks
        if task_name in self._tasks and not self._tasks[task_name].done():
            self._tasks[task_name].cancel()

        # Add the task to the list
        self._tasks[task_name] = task

        # Wait for the task
        async def wait_for_task(task: asyncio.Task) -> None:
            try:
                _turn_id = self._turn_id
                await task
                if _turn_id != self._turn_id:
                    return
                if not self.has_pending_tasks:
                    asyncio.create_task(self._do_done_callback())
            except asyncio.CancelledError:
                pass

        # Start the task
        asyncio.create_task(wait_for_task(task))

    async def _do_done_callback(self) -> None:
        """Do the done callback."""

        # Cancel any pending tasks
        self.complete_turn()

        # Do the callback
        if self._done_callback:
            try:
                if asyncio.iscoroutinefunction(self._done_callback):
                    await self._done_callback()
                else:
                    self._done_callback()
            except Exception:
                pass

    def cancel_tasks(self) -> None:
        """Cancel any pending tasks."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()

    def reset(self) -> None:
        """Reset the end of turn."""
        self.cancel_tasks()

    def start_turn(self) -> None:
        """Start the end of turn."""
        self._turn_active = True

    def complete_turn(self) -> None:
        """Complete the end of turn."""
        self.next()
        self._turn_active = False

    def next(self) -> None:
        """Increment the end of turn."""
        self.reset()
        self._turn_id += 1

    def __str__(self) -> str:
        """Get the string representation of the end of turn.

        Returns:
            String representation of the processor state.
        """
        return f"TurnTaskProcessor(name={self._name}, turn_id={self._turn_id}, tasks={self._tasks.keys()}, pending={self.has_pending_tasks})"
