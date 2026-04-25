"""Main command."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
import asyncio
import logging

if TYPE_CHECKING:
    from collections.abc import Coroutine

from bascom import setup_logging
from rich.progress import (
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from wakepy import keep
import click

from .genlabel import (
    DEFAULT_DPI,
    DEFAULT_END_THETA,
    DEFAULT_FONT_SIZE,
    DEFAULT_SPACE_PER_LOOP,
    DEFAULT_START_RADIUS,
    DEFAULT_START_THETA,
    DEFAULT_THETA_STEP,
    DEFAULT_WIDTH_HEIGHT,
    Point,
    write_spiral_text_png,
    write_spiral_text_svg,
)
from .utils import DirectorySplitter, MogrifyLabelPool, WriteSpeeds

__all__ = ('main',)

log = logging.getLogger(__name__)

T = TypeVar('T')


def _run_async_cli(coro: Coroutine[Any, Any, None]) -> None:
    """
    Run ``coro`` under :py:func:`asyncio.run` with ``Ctrl+C`` messaging.

    Parameters
    ----------
    coro : collections.abc.Coroutine[Any, Any, None]
        Main coroutine for the event loop.

    Raises
    ------
    SystemExit
        With code ``130`` after :py:exc:`KeyboardInterrupt` (typically ``Ctrl+C``).
    """
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        try:
            click.echo('\nInterrupt received; shutting down (partial results may be incomplete).',
                       err=True)
        except KeyboardInterrupt:
            click.echo(
                '\nRepeated interrupt: exiting without full cleanup; '
                'outputs may be inconsistent or corrupted.',
                err=True)
        raise SystemExit(130) from None


class _RichSizeProgressTask:  # pragma: no cover
    """Adapt a :py:class:`rich.progress.Progress` task to ``SizeProgressTask``."""
    def __init__(self, progress: Progress, task_id: TaskID) -> None:
        self._progress = progress
        self._task_id = task_id

    def set_bounds(self, *, total: float, description: str | None = None) -> None:
        """
        Set the task total and optionally update its description.

        Parameters
        ----------
        total : float
            Total step count for the task.
        description : str | None
            New description, or ``None`` to leave the description unchanged.
        """
        if description is None:
            self._progress.update(self._task_id, total=total)
        else:
            self._progress.update(self._task_id, total=total, description=description)

    def advance(self, amount: float = 1) -> None:
        """
        Advance the underlying :py:mod:`rich` task by ``amount`` steps.

        Parameters
        ----------
        amount : float
            Number of steps to advance.
        """
        self._progress.advance(self._task_id, amount)


class _RichSizeProgress:  # pragma: no cover
    """Adapt a :py:class:`rich.progress.Progress` to ``SizeProgress``."""
    def __init__(self, progress: Progress) -> None:
        self._progress = progress

    def add_task(self, description: str, total: float | None = None) -> _RichSizeProgressTask:
        """
        Create a new :py:mod:`rich` task.

        Parameters
        ----------
        description : str
            Human-readable description for the task.
        total : float | None
            Total number of steps, or ``None`` when indeterminate.

        Returns
        -------
        _RichSizeProgressTask
            The wrapped task.
        """
        return _RichSizeProgressTask(self._progress,
                                     self._progress.add_task(description, total=total))


class _RichAsyncStatusRun:  # pragma: no cover
    """
    Show :py:class:`rich.console.Console` status during utils work.

    Used so :py:mod:`gendisc.utils` can show a spinner without importing :py:mod:`rich`.
    """
    def __init__(self, progress: Progress) -> None:
        self._console = progress.console

    async def run(self, message: str, awaitable: Coroutine[Any, Any, T]) -> T:
        """
        Await ``awaitable`` while displaying ``message`` with a spinner.

        Parameters
        ----------
        message : str
            Status text.
        awaitable : collections.abc.Coroutine[Any, Any, T]
            Coroutine to await.

        Returns
        -------
        T
            The coroutine result.
        """
        with self._console.status(message, spinner='dots'):
            return await awaitable


async def _run_split(path: Path, output_dir: Path, drive: Path, preparer: str | None,
                     publisher: str | None, prefix: str | None, starting_index: int,
                     write_speeds: WriteSpeeds, delete_command: str, *, cross_fs: bool,
                     labels: bool, quiet: bool) -> None:
    progress_cm = nullcontext(None) if quiet else Progress(
        SpinnerColumn(),
        TextColumn('[progress.description]{task.description}'),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        transient=True)
    with progress_cm as rich_progress:
        progress = _RichSizeProgress(rich_progress) if rich_progress is not None else None
        status_run = _RichAsyncStatusRun(rich_progress) if rich_progress is not None else None
        mogrify_pool = MogrifyLabelPool() if labels else None
        if mogrify_pool is not None:
            await mogrify_pool.start()
        try:
            await DirectorySplitter(path,
                                    prefix or path.name,
                                    cross_fs=cross_fs,
                                    delete_command=delete_command,
                                    drive=drive,
                                    labels=labels,
                                    mogrify_pool=mogrify_pool,
                                    output_dir=output_dir,
                                    preparer=preparer,
                                    progress=progress,
                                    publisher=publisher,
                                    starting_index=starting_index,
                                    status_run=status_run,
                                    write_speeds=write_speeds).split()
        finally:
            if mogrify_pool is not None:
                await mogrify_pool.wait_until_finished()


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.argument('path', type=click.Path(file_okay=False, resolve_path=True, path_type=Path))
@click.option('--cross-fs', help='Allow crossing file systems.', is_flag=True)
@click.option('-D',
              '--drive',
              default='/dev/sr0',
              help='Drive path.',
              type=click.Path(dir_okay=False, resolve_path=True, path_type=Path))
@click.option('-d', '--debug', help='Enable debug logging.', is_flag=True)
@click.option('-i',
              '--starting-index',
              default=1,
              help='Index to start with (defaults to 1).',
              metavar='INDEX',
              type=click.IntRange(1))
@click.option('-o',
              '--output-dir',
              default='.',
              help='Output directory. Will be created if it does not exist.',
              type=click.Path(file_okay=False, resolve_path=True, path_type=Path))
@click.option('-p', '--prefix', help='Prefix for volume ID and files.')
@click.option('-r', '--delete', help='Unlink instead of sending to trash.', is_flag=True)
@click.option('--no-labels', help='Do not create labels.', is_flag=True)
@click.option('--cd-write-speed', help='CD-R write speed.', type=int, default=24)
@click.option('--dvd-write-speed', help='DVD-R write speed.', type=int, default=8)
@click.option('--dvd-dl-write-speed', help='DVD-R DL write speed.', type=float, default=8)
@click.option('--bd-write-speed', help='BD-R write speed.', type=int, default=4)
@click.option('--bd-dl-write-speed', help='BD-R DL write speed.', type=int, default=6)
@click.option('--bd-tl-write-speed', help='BD-R TL write speed.', type=int, default=4)
@click.option('--bd-xl-write-speed', help='BD-R XL write speed.', type=int, default=4)
@click.option('--preparer', help='Preparer string (128 characters).', type=str)
@click.option('--publisher', help='Publisher string (128 characters).', type=str)
def main(path: Path,
         output_dir: Path,
         drive: Path,
         preparer: str | None = None,
         publisher: str | None = None,
         prefix: str | None = None,
         starting_index: int = 0,
         cd_write_speed: int = 24,
         dvd_write_speed: int = 8,
         dvd_dl_write_speed: float = 8,
         bd_write_speed: int = 4,
         bd_dl_write_speed: int = 6,
         bd_tl_write_speed: int = 4,
         bd_xl_write_speed: int = 4,
         *,
         cross_fs: bool = False,
         debug: bool = False,
         delete: bool = False,
         no_labels: bool = False) -> None:
    """Make a file listing filling up discs."""
    setup_logging(debug=debug,
                  loggers={
                      'gendisc': {},
                      **({
                          'wakepy': {}
                      } if debug else {})
                  },
                  root={'level': 'DEBUG' if debug else 'INFO'})
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)
    if not debug:
        click.echo(f'Scanning "{path}"...')
    with keep.running():
        _run_async_cli(
            _run_split(path,
                       output_dir_p,
                       drive,
                       preparer,
                       publisher,
                       prefix,
                       starting_index,
                       WriteSpeeds(cd=cd_write_speed,
                                   dvd=dvd_write_speed,
                                   dvd_dl=dvd_dl_write_speed,
                                   bd=bd_write_speed,
                                   bd_dl=bd_dl_write_speed,
                                   bd_tl=bd_tl_write_speed,
                                   bd_xl=bd_xl_write_speed),
                       'rm -rf' if delete else 'trash',
                       cross_fs=cross_fs,
                       labels=not no_labels,
                       quiet=debug))


async def _run_genlabel(output: Path, text: str, width: int, height: int | None,
                        view_box: tuple[int, int, int, int] | None, dpi: int, font_size: int,
                        center: Point | None, start_radius: int, space_per_loop: float,
                        start_theta: float, end_theta: float, theta_step: float, *, keep_svg: bool,
                        svg: bool) -> None:
    if svg:
        await write_spiral_text_svg(output.with_suffix('.svg'), text, width, height, view_box,
                                    font_size, center, start_radius, space_per_loop, start_theta,
                                    end_theta, theta_step)
    else:
        await write_spiral_text_png(output,
                                    text,
                                    width,
                                    height,
                                    view_box,
                                    dpi,
                                    font_size,
                                    center,
                                    start_radius,
                                    space_per_loop,
                                    start_theta,
                                    end_theta,
                                    theta_step,
                                    keep=keep_svg)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.argument('text', nargs=-1)
@click.option('-E', '--end-theta', help='End theta.', type=float, default=0)
@click.option('-H', '--height', help='Height of the image.', type=int)
@click.option('-S',
              '--space-per-loop',
              help='Space per loop.',
              type=float,
              default=DEFAULT_SPACE_PER_LOOP)
@click.option('-T', '--start-theta', help='Start theta.', type=float, default=DEFAULT_START_THETA)
@click.option('-V',
              '--view-box',
              help='SVG view box.',
              type=click.Tuple((int, int, int, int)),
              required=False)
@click.option('--dpi', help='Dots per inch.', type=int, default=DEFAULT_DPI)
@click.option('--keep-svg', help='When generating the PNG, keep the SVG file.', is_flag=True)
@click.option('-c', '--center', help='Center of the spiral.', type=click.Tuple((float, float)))
@click.option('-d', '--debug', help='Enable debug logging.', is_flag=True)
@click.option('-f', '--font-size', help='Font size.', type=float, default=DEFAULT_FONT_SIZE)
@click.option('-g', '--svg', help='Output SVG.', is_flag=True)
@click.option('-o',
              '--output',
              help='Output file name.',
              type=click.Path(path_type=Path, dir_okay=False),
              default='out.png')
@click.option('-r',
              '--start-radius',
              help='Start radius.',
              type=float,
              default=DEFAULT_START_RADIUS)
@click.option('-t', '--theta-step', help='Theta step.', type=float, default=DEFAULT_THETA_STEP)
@click.option('-w',
              '--width',
              help='Width of the image.',
              type=click.IntRange(1, 10000),
              default=DEFAULT_WIDTH_HEIGHT)
def genlabel_main(text: tuple[str, ...],
                  output: Path,
                  center: tuple[float, float] | None = None,
                  dpi: int = DEFAULT_DPI,
                  end_theta: float = DEFAULT_END_THETA,
                  font_size: int = DEFAULT_FONT_SIZE,
                  height: int | None = None,
                  space_per_loop: float = DEFAULT_SPACE_PER_LOOP,
                  start_radius: int = DEFAULT_START_RADIUS,
                  start_theta: float = DEFAULT_START_THETA,
                  theta_step: float = DEFAULT_THETA_STEP,
                  view_box: tuple[int, int, int, int] | None = None,
                  width: int = DEFAULT_WIDTH_HEIGHT,
                  *,
                  debug: bool = False,
                  keep_svg: bool = False,
                  svg: bool = False) -> None:
    """Generate an image intended for printing on disc consisting of text in a spiral."""
    setup_logging(debug=debug, loggers={'gendisc': {}})
    _run_async_cli(
        _run_genlabel(output,
                      ' '.join(text),
                      width,
                      height,
                      view_box,
                      dpi,
                      font_size,
                      Point(*center) if center else None,
                      start_radius,
                      space_per_loop,
                      start_theta,
                      end_theta,
                      theta_step,
                      keep_svg=keep_svg,
                      svg=svg))
