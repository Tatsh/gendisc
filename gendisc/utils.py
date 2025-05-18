"""Utilities."""
from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Literal, overload
import logging
import logging.config
import os
import re
import shlex
import shutil
import subprocess as sp

from tqdm import tqdm
from typing_extensions import override
import fsutil

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

__all__ = ('DirectorySplitter', 'get_disc_type')

log = logging.getLogger(__name__)


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
get_file_size = cache(fsutil.get_file_size)
isdir = cache(os.path.isdir)
islink = cache(os.path.islink)
path_join = cache(os.path.join)
quote = cache(shlex.quote)
walk = cache(os.walk)


@cache
def get_dir_size(path: str) -> int:
    size = 0
    if not isdir(path):
        raise NotADirectoryError
    for basepath, _, filenames in tqdm(walk(path), desc=f'Calculating size of {path}', unit=' dir'):
        for filename in filenames:
            filepath = path_join(basepath, filename)
            if not islink(filepath):
                try:
                    log.debug('Getting file size for %s.', filepath)
                    size += get_file_size(filepath)
                except OSError:
                    log.exception(
                        'Caught error getting file size for %s. It will not be considered '
                        'part of the total.', filepath)
                    continue
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


MOUNTS = LazyMounts()


def is_cross_fs(dir_: str) -> bool:
    """Check if the directory is on a different file system."""
    return dir_ in MOUNTS


_DiscType = Literal['CD-R', 'DVD-R', 'DVD-R DL', 'BD-R', 'BD-R DL', 'BD-R XL (100 GB)',
                    'BD-R XL (128 GB)']


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


def path_list_first_component(line: str) -> str:
    return re.split(r'(?<!\\)=', line, maxsplit=1)[0].replace('\\=', '=')


class DirectorySplitter:
    """Split directories into sets for burning to disc."""
    def __init__(self,
                 path: os.PathLike[str] | str,
                 prefix: str,
                 prefix_parts: tuple[str, ...] | None = None,
                 delete_command: str = 'trash',
                 drive: os.PathLike[str] | str = '/dev/sr0',
                 output_dir: os.PathLike[str] | str = '.',
                 starting_index: int = 1,
                 *,
                 cross_fs: bool = False,
                 labels: bool = False) -> None:
        self._cross_fs = cross_fs
        self._current_set: list[str] = []
        self._delete_command = delete_command
        self._drive = drive or Path('/dev/sr0')
        self._has_mogrify = False if not labels else shutil.which('mogrify') is not None
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
            dev_arg = quote(f'dev={self._drive}')
            index = len(self._sets) + self._starting_index
            fn_prefix = f'{self._prefix}-{index:03d}'
            volid = f'{self._prefix}-{index:02d}'
            iso_file = str(self._output_dir_p / f'{fn_prefix}.iso')
            list_txt_file = f'{self._output_dir_p / volid}.list.txt'
            pl_filename = f'{fn_prefix}.path-list.txt'
            sh_filename = f'generate-{fn_prefix}.sh'
            sha256_filename = f'{iso_file}.sha256sum'
            tree_txt_file = f'{self._output_dir_p / volid}.tree.txt'
            log.debug('Total: %s', convert_size_bytes_to_string(self._total))
            (self._output_dir_p / pl_filename).write_text('\n'.join(self._current_set) + '\n',
                                                          encoding='utf-8')
            (self._output_dir_p / sh_filename).write_text(rf"""#!/usr/bin/env bash
find {quote(str(self._path))} -type f -name .directory -delete
mkisofs -graft-points -volid {quote(volid)} -appid gendisc -sysid LINUX -rational-rock \
    -no-cache-inodes -udf -full-iso9660-filenames -disable-deep-relocation -iso-level 3 \
    -path-list {quote(str(self._output_dir_p / pl_filename))} \
    -o {quote(iso_file)}
echo 'Size: {convert_size_bytes_to_string(self._total)}'
pv {quote(iso_file)} | sha256sum > {quote(sha256_filename)}
loop_dev=$(udisksctl loop-setup --no-user-interaction -r -f {quote(iso_file)} 2>&1 |
    rev | awk '{{ print $1 }}' | rev | cut -d. -f1)
location=$(udisksctl mount --no-user-interaction -b "${{loop_dev}}" | rev | awk '{{ print $1 }}' |
    rev)
pushd "${{location}}" || exit 1
find . -type f > {quote(list_txt_file)}
tree > {quote(tree_txt_file)}
popd || exit 1
udisksctl unmount --no-user-interaction --object-path "block_devices/$(basename "${{loop_dev}}")"
udisksctl loop-delete --no-user-interaction -b "${{loop_dev}}"
eject
echo 'Insert a blank disc ({get_disc_type(self._total)} or higher) and press return.'
read
delay 120
cdrecord {dev_arg} gracetime=2 -v driveropts=burnfree speed=4 -eject -sao {quote(iso_file)}
eject -t
delay 30
# wait-for-disc -w 15 '{quote(str(self._drive))}'
this_sum=$(pv {quote(str(self._drive))} | sha256sum)
expected_sum=$(< {quote(sha256_filename)})
if [[ "${{this_sum}}" != "${{expected_sum}}" ]]; then
    echo 'Burnt disc is invalid!'
    exit 1
else
    rm {quote(iso_file)}
    {self._delete_command} {shlex.join(y.rsplit("=", 1)[-1] for y in self._current_set)}
    echo 'OK.'
fi
eject
echo 'Move disc to printer.'
""",
                                                          encoding='utf-8')
            (self._output_dir_p / sh_filename).chmod(0o755)
            log.debug('%s total: %s', fn_prefix, convert_size_bytes_to_string(self._total))
            if self._has_mogrify:
                log.debug('Creating label for "%s".', volid)
                l_common_prefix = len(self._prefix_parts[-1])
                text = f'{volid} || '
                text += ' | '.join(
                    sorted(
                        path_list_first_component(x[l_common_prefix + 1:])
                        for x in self._current_set if x.strip()))
                write_spiral_text_png(self._output_dir_p / f'{fn_prefix}.png', text)
            self._sets.append(self._current_set)

    def split(self) -> None:
        """Split the directory into sets."""
        for dir_ in sorted(sorted(
                sp.run(('find', str(Path(self._path).resolve(strict=True)), '-maxdepth', '1', '!',
                        '-name', '.directory'),
                       check=True,
                       text=True,
                       capture_output=True).stdout.splitlines()[1:]),
                           key=lambda x: not Path(x).is_dir()):
            if not self._cross_fs and is_cross_fs(dir_):
                log.debug('Not processing %s because it is another file system.', dir_)
                continue
            log.debug('Calculating size: %s', dir_)
            type_ = 'Directory'
            try:
                self._size = get_dir_size(dir_)
            except NotADirectoryError:
                type_ = 'File'
                try:
                    self._size = get_file_size(dir_)
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
                                  f'{self._prefix}-{suffix}', (*self._prefix_parts, suffix),
                                  self._delete_command,
                                  self._drive,
                                  self._output_dir_p,
                                  self._starting_index,
                                  cross_fs=self._cross_fs,
                                  labels=self._has_mogrify).split()
                self._reset()
                continue
            self._total = self._next_total
            fixed = dir_[self._l_path + 1:].replace('=', '\\=')
            self._current_set.append(f'{fixed}={dir_}')
        self._append_set()
