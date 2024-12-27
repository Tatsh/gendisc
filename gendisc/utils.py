from collections.abc import Iterable, Sequence
from functools import cache
from pathlib import Path
from typing import overload
import logging
import os
import shlex
import subprocess as sp

from tqdm import tqdm
from typing_extensions import override
from wand.font import Font
from wand.image import Image
import fsutil

from .constants import (
    BLURAY_DUAL_LAYER_SIZE_BYTES,
    BLURAY_QUADRUPLE_LAYER_SIZE_BYTES,
    BLURAY_SINGLE_LAYER_SIZE_BYTES,
    BLURAY_TRIPLE_LAYER_SIZE_BYTES,
    CD_R_BYTES,
    DVD_R_DUAL_LAYER_SIZE_BYTES,
)

__all__ = ('DirectorySplitter', 'generate_label_image')

log = logging.getLogger(__name__)


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
    def __getitem__(self, index_or_slice: int) -> str:
        ...

    @override
    @overload
    def __getitem__(self, index_or_slice: slice) -> Sequence[str]:
        ...

    @override
    def __getitem__(self, index_or_slice: int | slice) -> str | Sequence[str]:
        self.initialize()
        assert self._mounts is not None
        return self._mounts[index_or_slice]

    @override
    def __len__(self) -> int:
        self.initialize()
        assert self._mounts is not None
        return len(self._mounts)


MOUNTS = LazyMounts()
convert_size_bytes_to_string = cache(fsutil.convert_size_bytes_to_string)
get_file_size = cache(fsutil.get_file_size)
isdir = cache(os.path.isdir)
islink = cache(os.path.islink)
path_join = cache(os.path.join)
quote = cache(shlex.quote)
walk = cache(os.walk)


def generate_label_image(contents: Iterable[str], filename: str) -> None:
    with Image() as img:
        img.background_color = 'white'
        img.font = Font('Noto', 20)
        contents_str = '  '.join(contents)
        img.read(filename=f'label: {contents_str} ')
        img.virtual_pixel = 'white'
        # 360 degree arc, rotated -90 degrees
        img.distort('arc', (360, -90))
        img.format = 'png'
        img.save(filename=filename)


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
                    size += get_file_size(filepath)
                except OSError:
                    continue
    return size


def is_cross_fs(dir_: str) -> bool:
    return dir_ in MOUNTS


class DirectorySplitter:
    def __init__(self,
                 path: Path | str,
                 prefix: str,
                 delete_command: str = 'trash',
                 drive: str = '/dev/sr0',
                 output_dir: Path | str = '.',
                 starting_index: int = 1,
                 *,
                 cross_fs: bool = False) -> None:
        self.cross_fs = cross_fs
        self.current_set: list[str] = []
        self.delete_command = delete_command
        self.drive = drive
        self.l_path = len(str(Path(path).resolve(strict=True).parent))
        self.next_total = 0
        self.output_dir_p = Path(output_dir)
        self.path = Path(path)
        self.prefix = prefix
        self.sets: list[list[str]] = []
        self.size = 0
        self.starting_index = starting_index
        self.target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES
        self.total = 0

    def reset(self) -> None:
        self.target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES
        self.current_set = []
        self.total = 0

    def too_large(self) -> None:
        self.append_set()
        self.reset()
        self.next_total = self.size

    def get_disc_type(self) -> str:  # noqa: PLR0911
        if self.total <= CD_R_BYTES:
            return 'CD-R'
        if self.total <= DVD_R_DUAL_LAYER_SIZE_BYTES:
            return 'DVD-R'
        if self.total <= DVD_R_DUAL_LAYER_SIZE_BYTES:
            return 'DVD-R DL'
        if self.total <= BLURAY_SINGLE_LAYER_SIZE_BYTES:
            return 'BD-R'
        if self.total <= BLURAY_DUAL_LAYER_SIZE_BYTES:
            return 'BD-R DL'
        if self.total <= BLURAY_TRIPLE_LAYER_SIZE_BYTES:
            return 'BD-R XL (100 GB)'
        if self.total <= BLURAY_QUADRUPLE_LAYER_SIZE_BYTES:
            return 'BD-R XL (128 GB)'
        raise ValueError

    def append_set(self) -> None:
        if self.current_set:
            dev_arg = quote(f'dev={self.drive}')
            index = len(self.sets) + self.starting_index
            fn_prefix = f'{self.prefix}-{index:03d}'
            volid = f'{self.prefix}-{index:02d}'
            iso_file = str(self.output_dir_p / f'{fn_prefix}.iso')
            list_txt_file = f'{self.output_dir_p / volid}.list.txt'
            pl_filename = f'{fn_prefix}.path-list.txt'
            sh_filename = f'generate-{fn_prefix}.sh'
            sha256_filename = f'{iso_file}.sha256sum'
            tree_txt_file = f'{self.output_dir_p / volid}.tree.txt'
            log.debug('Total: %s', convert_size_bytes_to_string(self.total))
            (self.output_dir_p / pl_filename).write_text('\n'.join(self.current_set) + '\n',
                                                         encoding='utf-8')
            (self.output_dir_p / sh_filename).write_text(rf"""#!/usr/bin/env bash
find {quote(str(self.path))} -type f -name .directory -delete
mkisofs -graft-points -volid {quote(volid)} -appid gendisc -sysid LINUX -rational-rock \
    -no-cache-inodes -udf -full-iso9660-filenames -disable-deep-relocation -iso-level 3 \
    -path-list {quote(str(self.output_dir_p / pl_filename))} \
    -o {quote(iso_file)}
echo 'Size: {convert_size_bytes_to_string(self.total)}'
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
echo 'Insert a blank disc ({self.get_disc_type()} or higher) and press return.'
read
delay 120
cdrecord {dev_arg} gracetime=2 -v driveropts=burnfree speed=4 -eject -sao {quote(iso_file)}
eject -t
delay 30
# wait-for-disc -w 15 '{quote(self.drive)}'
this_sum=$(pv {quote(self.drive)} | sha256sum)
expected_sum=$(< {quote(sha256_filename)})
if [[ "${{this_sum}}" != "${{expected_sum}}" ]]; then
    echo 'Burnt disc is invalid!'
    exit 1
else
    rm {quote(iso_file)}
    {self.delete_command} {shlex.join(y.rsplit("=", 1)[-1] for y in self.current_set)}
    echo 'OK.'
fi
eject
echo 'Move disc to printer.'
""",
                                                         encoding='utf-8')
            (self.output_dir_p / sh_filename).chmod(0o755)
            log.debug('%s total: %s', fn_prefix, convert_size_bytes_to_string(self.total))
            self.sets.append(self.current_set)

    def split(self) -> None:
        for dir_ in sorted(sorted(
                sp.run(('find', str(Path(
                    self.path).resolve(strict=True)), '-maxdepth', '1', '!', '-name', '.directory'),
                       check=True,
                       text=True,
                       capture_output=True).stdout.splitlines()[1:]),
                           key=lambda x: not Path(x).is_dir()):
            if not self.cross_fs and is_cross_fs(dir_):
                log.debug('Not processing %s because it is another file system.', dir_)
                continue
            log.debug('Calculating size: %s', dir_)
            type_ = 'Directory'
            try:
                self.size = get_dir_size(dir_)
            except NotADirectoryError:
                type_ = 'File'
                try:
                    self.size = get_file_size(dir_)
                except OSError:
                    continue
            self.next_total = self.total + self.size
            log.debug('%s: %s - %s', type_, dir_, convert_size_bytes_to_string(self.size))
            log.debug('Current total: %s / %s', convert_size_bytes_to_string(self.next_total),
                      convert_size_bytes_to_string(self.target_size))
            if self.next_total > self.target_size:
                log.debug('Current set with %s exceeds target size.', dir_)
                if self.target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES:
                    log.debug('Trying quad layer.')
                    self.target_size = BLURAY_QUADRUPLE_LAYER_SIZE_BYTES
                    if self.next_total > self.target_size:
                        log.debug('Still too large. Appending to next set.')
                        self.too_large()
                else:
                    self.too_large()
            if (self.next_total > self.target_size
                    and self.target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES
                    and self.next_total > BLURAY_QUADRUPLE_LAYER_SIZE_BYTES):
                if type_ == 'File':
                    log.warning(
                        'File %s too large for largest Blu-ray disc. It will not be processed.',
                        dir_)
                    continue
                log.debug('Directory %s too large for Blu-ray. Splitting separately.', dir_)
                DirectorySplitter(dir_,
                                  f'{self.prefix}-{Path(dir_).name}',
                                  self.delete_command,
                                  self.drive,
                                  self.output_dir_p,
                                  self.starting_index,
                                  cross_fs=self.cross_fs).split()
                self.reset()
                continue
            self.total = self.next_total
            fixed = dir_[self.l_path + 1:].replace('=', '\\=')
            self.current_set.append(f'{fixed}={dir_}')

        self.append_set()
