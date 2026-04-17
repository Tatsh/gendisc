"""Utilities."""
from __future__ import annotations

from functools import cache
from os import walk
from os.path import commonpath, isdir, islink
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple
import asyncio
import logging
import os
import re
import shlex
import shutil

from anyio import Path as AsyncPath
from anyio.to_thread import run_sync
from fsutil import get_file_size
from rich.progress import (
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
import fsutil
import jinja2

from .constants import (
    BLURAY_DUAL_LAYER_SIZE_BYTES_ADJUSTED,
    BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED,
    BLURAY_SINGLE_LAYER_SIZE_BYTES_ADJUSTED,
    BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED,
    CD_R_BYTES_ADJUSTED,
    DVD_R_DUAL_LAYER_SIZE_BYTES_ADJUSTED,
    DVD_R_SINGLE_LAYER_SIZE_BYTES,
)
from .genlabel import write_spiral_text_png

if TYPE_CHECKING:
    from collections.abc import Coroutine, Iterable

__all__ = ('DirectorySplitter', 'WriteSpeeds', 'get_disc_type')

log = logging.getLogger(__name__)
_jinja_env = jinja2.Environment(
    autoescape=jinja2.select_autoescape(),
    loader=jinja2.PackageLoader(__package__),  # ty: ignore[invalid-argument-type]
    lstrip_blocks=True,
    trim_blocks=True,
    undefined=jinja2.StrictUndefined)

convert_size_bytes_to_string = cache(fsutil.convert_size_bytes_to_string)
quote = cache(shlex.quote)


@cache
def path_join(a: str, b: str) -> str:
    """
    Join two path components.

    Parameters
    ----------
    a : str
        First path component.
    b : str
        Second path component.

    Returns
    -------
    str
        The joined path.
    """
    return os.path.join(a, b)  # noqa: PTH118


_STAT_CONCURRENCY = 64
"""Maximum number of concurrent ``stat``-like calls made by :py:func:`get_dir_size`."""


@cache
def _warn_buggy_fs_once(filepath: str) -> None:
    """
    Log the buggy-filesystem warning at most once per ``filepath``.

    Using :py:func:`functools.cache` guarantees the message is suppressed on
    repeat reports for the same path. Callers can reset this via
    ``_warn_buggy_fs_once.cache_clear()``.
    """
    log.warning('Buggy file system (cifs with "unix" option?) reported directory'
                ' `%s` as file.', filepath)


async def _file_size(filepath: str, semaphore: asyncio.Semaphore) -> int | None:
    """
    Return the size of a file, bounded by ``semaphore``.

    When ``filepath`` unexpectedly resolves to a directory, the directory is
    traversed with :py:func:`get_dir_size` and that total is returned.

    Parameters
    ----------
    filepath : str
        Path to the file whose size should be returned.
    semaphore : asyncio.Semaphore
        Semaphore bounding the number of concurrent stat-like calls.

    Returns
    -------
    int | None
        Size in bytes, or ``None`` when the file cannot be stat-ed and is
        not a directory.
    """
    async with semaphore:
        try:
            log.debug('Getting file size for `%s`.', filepath)
            return await run_sync(get_file_size, filepath)
        except OSError:
            if isdir(filepath):  # noqa: ASYNC240, PTH112
                # On cifs with 'unix' option, directories get reported as files from walk().
                _warn_buggy_fs_once(filepath)
                return await get_dir_size(filepath)
            log.exception(
                'Caught error getting file size for `%s`. It will not be considered '
                'part of the total.', filepath)
            return None


async def get_dir_size(path: str) -> int:
    """
    Calculate the total size of a directory recursively.

    Parameters
    ----------
    path : str
        Path to the directory to size.

    Returns
    -------
    int
        Total size in bytes.

    Raises
    ------
    NotADirectoryError
        If ``path`` is not a directory.
    """
    if not isdir(path):  # noqa: ASYNC240, PTH112
        raise NotADirectoryError
    size = 0
    semaphore = asyncio.Semaphore(_STAT_CONCURRENCY)
    with Progress(SpinnerColumn(),
                  TextColumn('[progress.description]{task.description}'),
                  MofNCompleteColumn(),
                  TimeElapsedColumn(),
                  transient=True) as progress:
        task_id = progress.add_task(f'Calculating size of {path}', total=None)
        for basepath, _, filenames in walk(path):
            progress.advance(task_id)
            if not filenames:
                continue
            filepaths = [
                path_join(basepath, filename) for filename in filenames
                if not islink(path_join(basepath, filename))  # noqa: ASYNC240, PTH114
            ]
            if not filepaths:
                continue
            results = await asyncio.gather(*(_file_size(filepath, semaphore)
                                             for filepath in filepaths))
            size += sum(r for r in results if r is not None)
    return size


_MOUNTS_CACHE: list[str] | None = None
_MOUNTS_LOCK = asyncio.Lock()


async def get_mounts() -> list[str]:
    """
    Read mount points from ``/proc/mounts``.

    Returns
    -------
    list[str]
        Mount point paths. Cached after the first call; call :py:func:`reload_mounts`
        to refresh.
    """
    global _MOUNTS_CACHE  # noqa: PLW0603
    async with _MOUNTS_LOCK:
        if _MOUNTS_CACHE is None:
            _MOUNTS_CACHE = await _read_mounts()
        return _MOUNTS_CACHE


async def reload_mounts() -> list[str]:
    """
    Reload mount points from ``/proc/mounts``, bypassing the cache.

    Returns
    -------
    list[str]
        Mount point paths.
    """
    global _MOUNTS_CACHE  # noqa: PLW0603
    async with _MOUNTS_LOCK:
        _MOUNTS_CACHE = await _read_mounts()
        return _MOUNTS_CACHE


async def clear_mounts_cache() -> None:
    """Drop the cached mount points so the next :py:func:`get_mounts` call re-reads them."""
    global _MOUNTS_CACHE  # noqa: PLW0603
    async with _MOUNTS_LOCK:
        _MOUNTS_CACHE = None


async def _read_mounts() -> list[str]:
    text = await AsyncPath('/proc/mounts').read_text(encoding='utf-8')
    return [x.split()[1] for x in text.splitlines()]


ISO_MAX_VOLID_LENGTH = 32


async def is_cross_fs(dir_: str) -> bool:
    """
    Check if the directory is on a different file system.

    Parameters
    ----------
    dir_ : str
        Directory path to check.

    Returns
    -------
    bool
        Whether ``dir_`` is listed as a mount point.
    """
    return dir_ in await get_mounts()


_DiscType = Literal['CD-R', 'DVD-R', 'DVD-R DL', 'BD-R', 'BD-R DL', 'BD-R XL (100 GB)',
                    'BD-R XL (128 GB)']


@cache
def get_disc_type(total: int) -> _DiscType:
    """
    Get disc type based on total size in bytes.

    Parameters
    ----------
    total : int
        Total size in bytes.

    Returns
    -------
    _DiscType
        The disc type that fits ``total`` bytes.

    Raises
    ------
    ValueError
        If the total size exceeds the maximum supported size.
    """
    if total <= CD_R_BYTES_ADJUSTED:
        return 'CD-R'
    if total <= DVD_R_SINGLE_LAYER_SIZE_BYTES:
        return 'DVD-R'
    if total <= DVD_R_DUAL_LAYER_SIZE_BYTES_ADJUSTED:
        return 'DVD-R DL'
    if total <= BLURAY_SINGLE_LAYER_SIZE_BYTES_ADJUSTED:
        return 'BD-R'
    if total <= BLURAY_DUAL_LAYER_SIZE_BYTES_ADJUSTED:
        return 'BD-R DL'
    if total <= BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED:
        return 'BD-R XL (100 GB)'
    if total <= BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED:
        return 'BD-R XL (128 GB)'
    msg = 'Disc size exceeds maximum supported size.'
    raise ValueError(msg)


@cache
def path_list_first_component(line: str) -> str:
    """
    Return the first path-list component of ``line``.

    Parameters
    ----------
    line : str
        A path-list line of the form ``alias=actual`` where ``=`` may be escaped
        with a backslash.

    Returns
    -------
    str
        The alias part with escaped ``=`` unescaped.
    """
    return re.split(r'(?<!\\)=', line, maxsplit=1)[0].replace('\\=', '=')


class WriteSpeeds(NamedTuple):
    """Write speeds for different disc types."""
    cd: int = 24
    """CD-R write speed."""
    dvd: int = 8
    """DVD-R write speed."""
    dvd_dl: float = 8
    """DVD-R DL write speed."""
    bd: int = 4
    """BD-R write speed."""
    bd_dl: int = 6
    """BD-R DL write speed."""
    bd_tl: int = 4
    """BD-R TL write speed."""
    bd_xl: int = 4
    """BD-R XL write speed."""
    def get_speed(self, disc_type: _DiscType) -> int | float:
        """
        Get the write speed for the given disc type.

        Parameters
        ----------
        disc_type : _DiscType
            Disc type identifier.

        Returns
        -------
        int | float
            Nominal write speed for ``disc_type``.

        Raises
        ------
        ValueError
            If the disc type is unknown.
        """
        match disc_type:
            case 'CD-R':
                return self.cd
            case 'DVD-R':
                return self.dvd
            case 'DVD-R DL':
                return self.dvd_dl
            case 'BD-R':
                return self.bd
            case 'BD-R DL':
                return self.bd_dl
            case 'BD-R XL (100 GB)':
                return self.bd_tl
            case 'BD-R XL (128 GB)':
                return self.bd_xl
            case _:
                msg = f'Unknown disc type: {disc_type}'  # type: ignore[unreachable]
                raise ValueError(msg)


class DirectorySplitter:
    """Split directories into sets for burning to disc."""
    def __init__(self,
                 path: os.PathLike[str] | str,
                 prefix: str,
                 delete_command: str = 'trash',
                 drive: os.PathLike[str] | str = '/dev/sr0',
                 output_dir: os.PathLike[str] | str = '.',
                 prefix_parts: tuple[str, ...] | None = None,
                 preparer: str | None = None,
                 publisher: str | None = None,
                 starting_index: int = 1,
                 write_speeds: WriteSpeeds | None = None,
                 *,
                 cross_fs: bool = False,
                 labels: bool = False) -> None:
        self._cross_fs = cross_fs
        self._current_set: list[str] = []
        self._delete_command = delete_command
        self._drive = drive or '/dev/sr0'
        # mogrify internally uses Inkscape for SVG to PNG conversion.
        self._has_mogrify = (False if not labels else (shutil.which('mogrify') is not None
                                                       and shutil.which('inkscape') is not None))
        self._l_path = len(str(Path(path).resolve(strict=True).parent))
        self._next_total = 0
        self._output_dir_p = AsyncPath(output_dir)
        self._path = AsyncPath(path)
        self._prefix = prefix
        self._prefix_parts = prefix_parts or (prefix,)
        self._sets: list[list[str]] = []
        self._size = 0
        self._size_cache: dict[str, int] = {}
        self._starting_index = starting_index
        self._target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
        self._total = 0
        self._write_speeds = write_speeds or WriteSpeeds()
        self._preparer = preparer
        self._publisher = publisher

    @property
    def sets(self) -> list[list[str]]:
        """Sets of entries produced by :py:meth:`split`. Each inner list fits on one disc."""
        return self._sets

    def _reset(self) -> None:
        self._target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
        self._current_set = []
        self._total = 0

    async def _too_large(self) -> None:
        await self._append_set()
        self._reset()
        self._next_total = self._size

    async def _append_set(self) -> None:  # noqa: PLR0914
        if not self._current_set:
            return
        index = len(self._sets) + self._starting_index
        fn_prefix = f'{self._prefix}-{index:03d}'
        orig_vol_id = volid = f'{self._prefix}-{index:02d}'
        if len(volid) > ISO_MAX_VOLID_LENGTH:
            volid = f'{volid[:29]}-{index:02d}'
        output_dir = self._output_dir_p / fn_prefix
        await output_dir.mkdir(parents=True, exist_ok=True)
        iso_file = str(output_dir / f'{fn_prefix}.iso')
        list_txt_file = f'{output_dir / orig_vol_id}.list.txt'
        pl_filename = f'{fn_prefix}.path-list.txt'
        sh_filename = f'generate-{fn_prefix}.sh'
        sha256_filename = f'{iso_file}.sha256sum'
        tree_txt_file = f'{output_dir / orig_vol_id}.tree.txt'
        metadata_filename = f'{output_dir / orig_vol_id}.metadata.json'
        log.debug('Total: %s', convert_size_bytes_to_string(self._total))
        pl_file = output_dir / pl_filename
        label_file = output_dir / f'{fn_prefix}.png'
        disc_type = get_disc_type(self._total)
        speed = self._write_speeds.get_speed(disc_type)
        special_args = []
        if self._preparer:
            special_args.append(f'-preparer {quote(self._preparer)}')
        if self._publisher:
            special_args.append(f'-publisher {quote(self._publisher)}')
        delete_command_args = shlex.join(y.rsplit('=', 1)[-1] for y in self._current_set)
        sh_file = output_dir / sh_filename
        sh_contents = _jinja_env.get_template('process.sh.j2').render(
            delete_command=(f'{self._delete_command} {delete_command_args}'
                            if self._delete_command else ''),
            disc_type=disc_type,
            drive=quote(str(self._drive)),
            gimp_script_fu=quote(''.join(
                re.sub(r'^\s+', '', x)
                for x in _jinja_env.get_template('print-label.scm.j2').render(
                    label_file=str(label_file).replace('"', r'\"')).splitlines())),
            iso_file=quote(iso_file),
            label_file=quote(str(label_file)),
            list_txt_file=quote(list_txt_file),
            metadata_filename=quote(metadata_filename),
            pl_file=quote(str(pl_file)),
            sha256_file=quote(sha256_filename),
            size_str=convert_size_bytes_to_string(self._total),
            size_bytes_formatted=f'{self._total:,}',
            special_args=' '.join(special_args),
            speed=quote(f'{speed:.1f}' if isinstance(speed, float) else str(speed)),
            tree_txt_file=quote(tree_txt_file),
            volid=quote(volid)) + '\n'
        pl_contents = '\n'.join(self._current_set) + '\n'
        tasks: list[Coroutine[Any, Any, object]] = [
            pl_file.write_text(pl_contents, encoding='utf-8'),
            sh_file.write_text(sh_contents, encoding='utf-8'),
        ]
        if self._has_mogrify:
            log.debug('Creating label for `%s`.', orig_vol_id)
            common_prefix = (commonpath(self._current_set).split('/', 1)[0] if len(
                self._current_set) > 1 else self._current_set[0].split('/', 1)[0])
            log.debug('Common prefix: %s', common_prefix)
            l_common_prefix = len(common_prefix) + 1
            text = f'{orig_vol_id} || ' + ' | '.join(
                sorted(
                    path_list_first_component(x[l_common_prefix:])
                    for x in self._current_set if x.strip()))
            tasks.append(write_spiral_text_png(label_file, text))
        await asyncio.gather(*tasks)
        await sh_file.chmod(0o755)
        log.debug('%s total: %s', fn_prefix, convert_size_bytes_to_string(self._total))
        self._sets.append(self._current_set)

    async def _size_of(self, dir_: str) -> tuple[str, int | None, Literal['Directory', 'File']]:
        if dir_ in self._size_cache:
            cached = self._size_cache[dir_]
            return dir_, cached, ('Directory' if isdir(dir_) else 'File')  # noqa: ASYNC240, PTH112
        try:
            size = await get_dir_size(dir_)
            self._size_cache[dir_] = size
        except NotADirectoryError:
            try:
                size = await run_sync(get_file_size, dir_)
                self._size_cache[dir_] = size
            except OSError:
                return dir_, None, 'File'
            return dir_, size, 'File'
        return dir_, size, 'Directory'

    async def _list_entries(self) -> list[str]:
        path = await self._path.resolve(strict=True)
        cmd = ('find', str(path), '-maxdepth', '1', '(', '-name', '.Trash-*', '-o', '-name',
               'Trash', '-o', '-name', '.Trash', '-o', '-name', '.directory', ')', '-prune', '-o',
               '-print')
        log.debug('Running %s', shlex.join(cmd))
        proc = await asyncio.create_subprocess_exec(*cmd,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            msg = f'find exited with code {proc.returncode}.'
            raise RuntimeError(msg)
        entries = stdout.decode('utf-8').splitlines()[1:]
        return sorted(sorted(entries), key=lambda x: not isdir(x))  # noqa: PTH112

    async def split(self) -> None:
        """Split the directory into sets."""
        entries = await self._list_entries()
        # Filter out cross-filesystem entries up front (mount lookup is cheap and cached).
        allowed: list[str] = []
        for dir_ in entries:
            if not self._cross_fs and await is_cross_fs(dir_):
                log.debug('Not processing `%s` because it is another file system.', dir_)
                continue
            allowed.append(dir_)
        # Compute sizes concurrently; bin-packing below remains sequential.
        sized: Iterable[tuple[str, int | None,
                              Literal['Directory',
                                      'File']]] = await (asyncio.gather(*(self._size_of(dir_)
                                                                          for dir_ in allowed)))
        for dir_, size, type_ in sized:
            if size is None:
                continue
            self._size = size
            self._next_total = self._total + self._size
            log.debug('%s: %s - %s', type_, dir_, convert_size_bytes_to_string(self._size))
            log.debug('Current total: %s / %s', convert_size_bytes_to_string(self._next_total),
                      convert_size_bytes_to_string(self._target_size))
            if self._next_total > self._target_size:
                log.debug('Current set with `%s` exceeds target size.', dir_)
                if self._target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED:
                    log.debug('Trying quad layer.')
                    self._target_size = BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED
                    if self._next_total > self._target_size:
                        log.debug('Still too large. Appending to next set.')
                        await self._too_large()
                else:
                    await self._too_large()
            if (self._next_total > self._target_size
                    and self._target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
                    and self._next_total > BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED):
                if type_ == 'File':
                    log.warning(
                        'File `%s` too large for largest Blu-ray disc. It will not be processed.',
                        dir_)
                    continue
                log.debug('Directory `%s` too large for Blu-ray. Splitting separately.', dir_)
                suffix = AsyncPath(dir_).name
                await DirectorySplitter(dir_,
                                        f'{self._prefix}-{suffix}',
                                        cross_fs=self._cross_fs,
                                        delete_command=self._delete_command,
                                        drive=self._drive,
                                        labels=self._has_mogrify,
                                        output_dir=self._output_dir_p,
                                        prefix_parts=(*self._prefix_parts, suffix),
                                        preparer=self._preparer,
                                        publisher=self._publisher,
                                        starting_index=self._starting_index,
                                        write_speeds=self._write_speeds).split()
                self._reset()
                continue
            self._total = self._next_total
            fixed = dir_[self._l_path + 1:].replace('=', '\\=')
            self._current_set.append(f'{fixed}={dir_}')
        await self._append_set()
