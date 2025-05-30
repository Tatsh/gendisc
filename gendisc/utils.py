"""Utilities."""
from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from os import walk
from os.path import commonprefix, isdir, islink
from pathlib import Path
from typing import Literal, NamedTuple, overload
import logging
import logging.config
import os
import re
import shlex
import shutil
import subprocess as sp

from fsutil import get_file_size
from tqdm import tqdm
from typing_extensions import override
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

__all__ = ('DirectorySplitter', 'WriteSpeeds', 'get_disc_type')

log = logging.getLogger(__name__)
_jinja_env = jinja2.Environment(autoescape=jinja2.select_autoescape(),
                                loader=jinja2.PackageLoader(__package__),
                                lstrip_blocks=True,
                                trim_blocks=True,
                                undefined=jinja2.StrictUndefined)


def setup_logging(*,
                  debug: bool = False,
                  force_color: bool = False,
                  no_color: bool = False) -> None:  # pragma: no cover
    """Set up logging configuration."""
    logging.config.dictConfig({
        'disable_existing_loggers': True,
        'root': {
            'level': 'DEBUG' if debug else 'INFO',
            'handlers': ['console'],
        },
        'formatters': {
            'default': {
                '()': 'colorlog.ColoredFormatter',
                'force_color': force_color,
                'format': (
                    '%(light_cyan)s%(asctime)s%(reset)s | %(log_color)s%(levelname)-8s%(reset)s | '
                    '%(light_green)s%(name)s%(reset)s:%(light_red)s%(funcName)s%(reset)s:'
                    '%(blue)s%(lineno)d%(reset)s - %(message)s'),
                'no_color': no_color,
            },
            'simple': {
                'format': '%(levelname)s: %(message)s',
            }
        },
        'handlers': {
            'console': {
                'class': 'colorlog.StreamHandler',
                'formatter': 'default' if debug else 'simple',
            }
        },
        'loggers': {
            'gendisc': {
                'level': 'INFO' if not debug else 'DEBUG',
                'handlers': ('console',),
                'propagate': False,
            },
            'wakepy': {
                'level': 'INFO' if not debug else 'DEBUG',
                'handlers': ('console',),
                'propagate': False,
            },
        },
        'version': 1
    })


convert_size_bytes_to_string = cache(fsutil.convert_size_bytes_to_string)
path_join = cache(os.path.join)
quote = cache(shlex.quote)

_REPORTED_BUGGY_FS = False


def get_dir_size(path: str) -> int:
    global _REPORTED_BUGGY_FS  # noqa: PLW0603
    size = 0
    if not isdir(path):  # noqa: PTH112
        raise NotADirectoryError
    for basepath, _, filenames in tqdm(walk(path), desc=f'Calculating size of {path}', unit=' dir'):
        for filename in filenames:
            filepath = path_join(basepath, filename)
            if not islink(filepath):  # noqa: PTH114
                try:
                    log.debug('Getting file size for %s.', filepath)
                    size += get_file_size(filepath)
                except OSError:
                    if isdir(filepath):  # noqa: PTH112
                        # On cifs with 'unix' option directories get reported as files from walk().
                        if not _REPORTED_BUGGY_FS:
                            log.warning(
                                'Buggy file system (cifs with "unix" option?) reported directory'
                                ' %s as file.', filepath)
                            _REPORTED_BUGGY_FS = True
                        # Still have to traverse this path since walk() did not.
                        size += get_dir_size(filepath)
                    else:
                        log.exception(
                            'Caught error getting file size for %s. It will not be considered '
                            'part of the total.', filepath)
    return size


class LazyMounts(Sequence[str]):
    def __init__(self) -> None:
        self._mounts: list[str] | None = None

    @staticmethod
    def _read() -> list[str]:
        return [x.split()[1] for x in Path('/proc/mounts').read_text(encoding='utf-8').splitlines()]

    def initialize(self) -> None:
        if self._mounts is None:
            self.reload()

    def reload(self) -> None:
        self._mounts = self._read()

    @property
    def mounts(self) -> list[str]:
        self.initialize()
        assert self._mounts is not None
        return self._mounts

    @override
    @overload
    def __getitem__(self, index_or_slice: int) -> str:  # pragma: no cover
        ...

    @override
    @overload
    def __getitem__(self, index_or_slice: slice) -> list[str]:  # pragma: no cover
        ...

    @override
    def __getitem__(self, index_or_slice: int | slice) -> str | list[str]:
        self.initialize()
        assert self._mounts is not None
        return self._mounts[index_or_slice]

    @override
    def __len__(self) -> int:
        self.initialize()
        assert self._mounts is not None
        return len(self._mounts)


ISO_MAX_VOLID_LENGTH = 32
MOUNTS = LazyMounts()


def is_cross_fs(dir_: str) -> bool:
    """Check if the directory is on a different file system."""
    return dir_ in MOUNTS


_DiscType = Literal['CD-R', 'DVD-R', 'DVD-R DL', 'BD-R', 'BD-R DL', 'BD-R XL (100 GB)',
                    'BD-R XL (128 GB)']


@cache
def get_disc_type(total: int) -> _DiscType:  # noqa: PLR0911
    """
    Get disc type based on total size in bytes.

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
    def get_speed(self, disc_type: _DiscType) -> int | float:  # noqa: PLR0911
        """
        Get the write speed for the given disc type.

        Raises
        ------
        ValueError
            If the disc type is unknown.
        """
        if disc_type == 'CD-R':
            return self.cd
        if disc_type == 'DVD-R':
            return self.dvd
        if disc_type == 'DVD-R DL':
            return self.dvd_dl
        if disc_type == 'BD-R':
            return self.bd
        if disc_type == 'BD-R DL':
            return self.bd_dl
        if disc_type == 'BD-R XL (100 GB)':
            return self.bd_tl
        if disc_type == 'BD-R XL (128 GB)':
            return self.bd_xl
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
        self._drive = drive or Path('/dev/sr0')
        # mogrify internally uses Inkscape for SVG to PNG conversion.
        self._has_mogrify = (False if not labels else (shutil.which('mogrify') is not None
                                                       and shutil.which('inkscape') is not None))
        self._l_path = len(str(Path(path).resolve(strict=True).parent))
        self._next_total = 0
        self._output_dir_p = Path(output_dir)
        self._path = Path(path)
        self._prefix = prefix
        self._prefix_parts = prefix_parts or (prefix,)
        self._sets: list[list[str]] = []
        self._size = 0
        self._starting_index = starting_index
        self._target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
        self._total = 0
        self._cached_get_dir_size = cache(get_dir_size)
        self._cached_get_file_size = cache(get_file_size)
        self._write_speeds = write_speeds or WriteSpeeds()
        self._preparer = preparer
        self._publisher = publisher

    def _reset(self) -> None:
        self._target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
        self._current_set = []
        self._total = 0

    def _too_large(self) -> None:
        self._append_set()
        self._reset()
        self._next_total = self._size

    def _append_set(self) -> None:
        if self._current_set:
            index = len(self._sets) + self._starting_index
            fn_prefix = f'{self._prefix}-{index:03d}'
            orig_vol_id = volid = f'{self._prefix}-{index:02d}'
            if len(volid) > ISO_MAX_VOLID_LENGTH:
                volid = f'{volid[:29]}-{index:02d}'
            output_dir = self._output_dir_p / fn_prefix
            output_dir.mkdir(parents=True, exist_ok=True)
            iso_file = str(output_dir / f'{fn_prefix}.iso')
            list_txt_file = f'{output_dir / orig_vol_id}.list.txt'
            pl_filename = f'{fn_prefix}.path-list.txt'
            sh_filename = f'generate-{fn_prefix}.sh'
            sha256_filename = f'{iso_file}.sha256sum'
            tree_txt_file = f'{output_dir / orig_vol_id}.tree.txt'
            metadata_filename = f'{output_dir / orig_vol_id}.metadata.json'
            log.debug('Total: %s', convert_size_bytes_to_string(self._total))
            pl_file = output_dir / pl_filename
            pl_file.write_text('\n'.join(self._current_set) + '\n', encoding='utf-8')
            label_file = output_dir / f'{fn_prefix}.png'
            disc_type = get_disc_type(self._total)
            speed = self._write_speeds.get_speed(disc_type)
            special_args = []
            if self._preparer:
                special_args.append(f'-preparer {quote(self._preparer)}')
            if self._publisher:
                special_args.append(f'-publisher {quote(self._publisher)}')
            delete_command_args = shlex.join(y.rsplit('=', 1)[-1] for y in self._current_set)
            sh_file = (output_dir / sh_filename)
            sh_file.write_text(_jinja_env.get_template('process.sh.j2').render(
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
                volid=quote(volid)) + '\n',
                               encoding='utf-8')
            sh_file.chmod(0o755)
            log.debug('%s total: %s', fn_prefix, convert_size_bytes_to_string(self._total))
            if self._has_mogrify:
                log.debug('Creating label for "%s".', orig_vol_id)
                common_prefix = (commonprefix(self._current_set).split('/', 1)[0] if len(
                    self._current_set) > 1 else self._current_set[0].split('/', 1)[0])
                log.debug('Common prefix: %s', common_prefix)
                l_common_prefix = len(common_prefix) + 1
                text = f'{orig_vol_id} || ' + ' | '.join(
                    sorted(
                        path_list_first_component(x[l_common_prefix:])
                        for x in self._current_set if x.strip()))
                write_spiral_text_png(label_file, text)
            self._sets.append(self._current_set)

    def split(self) -> None:
        """Split the directory into sets."""
        cmd = ('find', str(Path(self._path).resolve(strict=True)), '-maxdepth', '1', '(', '-name',
               '.Trash-*', '-o', '-name', 'Trash', '-o', '-name', '.Trash', '-o', '-name',
               '.directory', ')', '-prune', '-o', '-print')
        log.debug('Running %s', shlex.join(cmd))
        for dir_ in sorted(sorted(
                sp.run(cmd, check=True, text=True, capture_output=True).stdout.splitlines()[1:]),
                           key=lambda x: not isdir(x)):  # noqa: PTH112
            if not self._cross_fs and is_cross_fs(dir_):
                log.debug('Not processing %s because it is another file system.', dir_)
                continue
            log.debug('Calculating size: %s', dir_)
            type_ = 'Directory'
            try:
                self._size = self._cached_get_dir_size(dir_)
            except NotADirectoryError:
                type_ = 'File'
                try:
                    self._size = self._cached_get_file_size(dir_)
                except OSError:
                    continue
            self._next_total = self._total + self._size
            log.debug('%s: %s - %s', type_, dir_, convert_size_bytes_to_string(self._size))
            log.debug('Current total: %s / %s', convert_size_bytes_to_string(self._next_total),
                      convert_size_bytes_to_string(self._target_size))
            if self._next_total > self._target_size:
                log.debug('Current set with %s exceeds target size.', dir_)
                if self._target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED:
                    log.debug('Trying quad layer.')
                    self._target_size = BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED
                    if self._next_total > self._target_size:
                        log.debug('Still too large. Appending to next set.')
                        self._too_large()
                else:
                    self._too_large()
            if (self._next_total > self._target_size
                    and self._target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES_ADJUSTED
                    and self._next_total > BLURAY_QUADRUPLE_LAYER_SIZE_BYTES_ADJUSTED):
                if type_ == 'File':
                    log.warning(
                        'File %s too large for largest Blu-ray disc. It will not be processed.',
                        dir_)
                    continue
                log.debug('Directory %s too large for Blu-ray. Splitting separately.', dir_)
                suffix = Path(dir_).name
                DirectorySplitter(dir_,
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
        self._append_set()
