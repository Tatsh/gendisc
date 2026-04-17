"""Typing helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine

__all__ = ('AsyncStatusRun', 'SizeProgress', 'SizeProgressTask')

T = TypeVar('T')


class AsyncStatusRun(Protocol):
    """
    Await a coroutine while optionally showing transient status (for example a spinner).

    Implementations are supplied by the CLI layer so that :py:mod:`gendisc.utils` stays
    free of any specific console dependency.
    """
    async def run(self, message: str, awaitable: Coroutine[Any, Any, T]) -> T:
        """
        Await ``awaitable`` while displaying ``message`` as status.

        Parameters
        ----------
        message : str
            Short status text.
        awaitable : collections.abc.Coroutine[Any, Any, T]
            Coroutine to await.

        Returns
        -------
        T
            The value produced by ``awaitable``.
        """


class SizeProgressTask(Protocol):
    """A single progress task handed out by :py:class:`SizeProgress`."""
    def advance(self, amount: float = 1) -> None:
        """
        Advance the task by ``amount`` steps.

        Parameters
        ----------
        amount : float
            Number of steps to advance.
        """

    def set_bounds(self, *, total: float, description: str | None = None) -> None:
        """
        Set a determinate total and optionally replace the task description.

        Parameters
        ----------
        total : float
            Total step count for the task.
        description : str | None
            New description, or ``None`` to leave the description unchanged.
        """


class SizeProgress(Protocol):
    """
    A progress reporter used by :py:func:`gendisc.utils.get_dir_size`.

    Implementations are supplied by the CLI layer so that :py:mod:`gendisc.utils`
    stays free of any specific progress-rendering dependency.
    """
    def add_task(self, description: str, total: float | None = ...) -> SizeProgressTask:
        """
        Create a new task.

        Parameters
        ----------
        description : str
            Human-readable description for the task.
        total : float | None
            Total number of steps, or ``None`` when indeterminate.

        Returns
        -------
        SizeProgressTask
            The newly created task.
        """
