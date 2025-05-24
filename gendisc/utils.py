"""Utilities."""
from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from os import walk
from os.path import isdir, islink
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


@cache
def quote_incomplete(s: str) -> str:
    return quote(f'{s}.__incomplete__')


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
            dev_arg = quote(f'dev={self._drive}')
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
            speed_s = f'{speed:.1f}' if isinstance(speed, float) else str(speed)
            special_args = []
            if self._preparer:
                special_args.append(f'-preparer {quote(self._preparer)}')
            if self._publisher:
                special_args.append(f'-publisher {quote(self._publisher)}')
            gimp_script_fu = f"""(define (print-label filename)
  (let* ((image (car (gimp-file-load RUN-INTERACTIVE filename filename))))
  (file-print-gtk #:run-mode RUN-INTERACTIVE #:image image)))
(print-label "{label_file}")""".replace('\n', '')
            delete_command = (
                f'{self._delete_command} {shlex.join(y.rsplit("=", 1)[-1] for y in self._current_set)}'  # noqa: E501
                if self._delete_command else '')
            sh_file = (output_dir / sh_filename)
            sh_file.write_text(
                rf"""#!/usr/bin/env bash
make-listing() {{
    loop_dev=$(udisksctl loop-setup --no-user-interaction -r -f {quote(iso_file)} 2>&1 |
        rev | awk '{{ print $1 }}' | rev | cut -d. -f1)
    location=$(udisksctl mount --no-user-interaction -b "${{loop_dev}}" | rev | awk '{{ print $1 }}' | rev)
    pushd "${{location}}" || exit 1
    find . -type f > {quote_incomplete(list_txt_file)} &&
        mv {quote_incomplete(list_txt_file)} {quote(list_txt_file)}
    if command -v exiftool &> /dev/null; then
        find . -type f -exec exiftool -j {{}} ';' > {quote_incomplete(metadata_filename)} &&
            mv {quote_incomplete(metadata_filename)} {quote(metadata_filename)}
        if command -v jq &> /dev/null; then
            jq -rS --slurp 'map(.[0])' {quote(metadata_filename)} > {quote_incomplete(metadata_filename)} &&
                mv {quote_incomplete(metadata_filename)} {quote(metadata_filename)}
        fi
    fi
    tree > {quote_incomplete(tree_txt_file)} &&
        mv {quote_incomplete(tree_txt_file)} {quote(tree_txt_file)}
    popd || exit 1
    udisksctl unmount --no-user-interaction --object-path "block_devices/$(basename "${{loop_dev}}")"
    udisksctl loop-delete --no-user-interaction -b "${{loop_dev}}"
}}
_sha256sum() {{
    if command -v sha256sum &>/dev/null; then
        sha256sum "$@"
    elif command -v shasum &>/dev/null; then
        shasum -a 256 "$@"
    else
        echo 'Command to calculate SHA256 checksum not found!' >&2
        return 1
    fi
}}
make-image() {{
    if ! mkisofs -graft-points -volid {quote(volid)} -appid gendisc -sysid LINUX -rational-rock \
            -no-cache-inodes -udf -full-iso9660-filenames -udf -iso-level 3 \
            {" ".join(special_args)} -path-list {quote(str(pl_file))} -o {quote_incomplete(iso_file)}; then
        echo 'mkisofs failed!' >&2
        rm -f {quote(iso_file)}
        return 1
    fi
    mv {quote_incomplete(iso_file)} {quote(iso_file)}
    echo 'Size: {convert_size_bytes_to_string(self._total)} ({self._total:,} bytes)'
    echo 'Calculating SHA256 checksum...' >&2
    if command -v pv &> /dev/null; then
        pv {quote(iso_file)} | _sha256sum > {quote_incomplete(sha256_filename)} &&
            mv {quote_incomplete(sha256_filename)} {quote(sha256_filename)}
    else
        echo 'If you had pv installed, you would have had a progress bar here. Please be patient!' >&2
        _sha256sum {quote(iso_file)} > {quote_incomplete(sha256_filename)} &&
            mv {quote_incomplete(sha256_filename)} {quote(sha256_filename)}
    fi
}}
cdrecord_found=1
eject_found=1
mkisofs_found=1
sha256sum_found=1
if ! _sha256sum /dev/null &> /dev/null; then
    sha256sum_found=0
fi
if ! command -v mkisofs &> /dev/null; then
    mkisofs_found=0
fi
if ! command -v cdrecord &> /dev/null; then
    cdrecord_found=0
fi
if ! command -v eject &> /dev/null; then
    eject_found=0
fi
found_str() {{
    if (( $1 )); then
        echo 'Found    '
    else
        echo 'Not found'
    fi
}}
if ! ((mkisofs_found)) || ! ((cdrecord_found)) || ! ((sha256sum_found)) || ! ((eject_found)); then
    echo 'Missing required commands.' >&2
    echo "cdrecord:            $(found_str "$cdrecord_found") (cdrtools)" >&2
    echo "mkisofs:             $(found_str "$mkisofs_found") (cdrtools)" >&2
    echo "eject:               $(found_str "$eject_found") (util-linux)" >&2
    echo "sha256sum or shasum: $(found_str "$sha256sum_found") (coreutils or Perl)" >&2
    exit 1
fi
keep_files=0
keep_iso=0
only_iso=0
open_gimp=1
open_gimp_normal=0
skip_cleanup=0
skip_verification=0
skip_wait_for_disc=0
while getopts ':hGKOPSVks' opt; do
    case $opt in
        G) open_gimp=0 ;;
        K) keep_iso=1 ;;
        O) only_iso=1 ;;
        P) open_gimp_normal=1 ;;
        S) skip_wait_for_disc=1 ;;
        V) skip_verification=1 ;;
        k) keep_files=1 ;;
        s) skip_cleanup=1 ;;
        h) echo "Usage: $0 [-h] [-G] [-K] [-k] [-O] [-s] [-S] [-V]"
           echo 'All flags default to no.'
           echo '  -h: Show this help message.'
           echo '  -G: Do not open GIMP on completion (if label file exists).'
           echo '  -P: Open GIMP in normal mode instead of batch mode.'
           echo '  -K: Keep ISO image after burning.'
           echo '  -k: Keep source files after burning.'
           echo '  -O: Only create ISO image.'
           echo '  -S: Skip ejecting tray for blank disc (assume already inserted).'
           echo '  -s: Skip clean-up of .directory files.'
           echo '  -V: Skip verification of burnt disc.'
           exit 0 ;;
        :) echo "Option -$OPTARG requires an argument." >&2 ;;
        ?) echo "Invalid option: -$OPTARG" >&2 ;;
    esac
done
if ! (( skip_cleanup )); then
    echo 'Deleting .directory files.'
    find {quote(str(self._path))} -type f -name .directory -delete
fi
if [ -f {quote(iso_file)} ] && [ -f {quote(sha256_filename)} ]; then
    echo 'Re-create ISO image? If you answer n you must be sure the image was created successfully!'
    read -r -p 'y/n: ' answer
    if [[ "${{answer,,}}" == 'y' ]]; then
        make-image || exit 1
    fi
else
    make-image || exit 1
fi
make-listing || exit 1
if (( only_iso )); then
    echo 'Only creating ISO image.'
    exit
fi
if ! (( skip_wait_for_disc )); then
    eject
    echo 'Insert a blank disc ({disc_type} or higher) and press return.'
    read -r
    delay 120 || sleep 120
fi
cdrecord {dev_arg} gracetime=2 -v driveropts=burnfree speed={speed_s} -eject -sao {quote(iso_file)}
eject -t
delay 30 || sleep 30
if ! ((skip_verification)); then
    this_sum=$(pv {quote(str(self._drive))} | _sha256sum)
    expected_sum=$(<{quote(sha256_filename)})
    if [[ "${{this_sum}}" != "${{expected_sum}}" ]]; then
        echo 'Burnt disc is invalid!'
        exit 1
    fi
fi
if ! ((keep_iso)); then
    rm {quote(iso_file)}
fi
if ! ((keep_files)); then
    echo 'Delaying 30 seconds before deleting source files.'
    delay 30 || sleep 30
    {delete_command}
fi
echo 'OK.'
eject
echo 'Move disc to printer.'
if ((open_gimp)) && command -v gimp &> /dev/null && [ -f {quote(str(label_file))} ]; then
    echo 'Opening GIMP.'
    if ((open_gimp_normal)); then
        gimp {quote(str(label_file))}
    else
        gimp -ns --batch-interpreter=plug-in-script-fu-eval -b {quote(gimp_script_fu)}
    fi
fi
""",  # noqa: E501
                encoding='utf-8')
            sh_file.chmod(0o755)
            log.debug('%s total: %s', fn_prefix, convert_size_bytes_to_string(self._total))
            if self._has_mogrify:
                log.debug('Creating label for "%s".', orig_vol_id)
                l_common_prefix = len(self._prefix_parts[-1])
                text = f'{orig_vol_id} || ' + ' | '.join(
                    sorted(
                        path_list_first_component(x[l_common_prefix + 1:])
                        for x in self._current_set if x.strip()))
                write_spiral_text_png(label_file, text)
            self._sets.append(self._current_set)

    def split(self) -> None:
        """Split the directory into sets."""
        cmd = ('find', str(Path(self._path).resolve(strict=True)), '-maxdepth', '1', '(', '-name',
               '.Trash-*', '-o', '-name', 'Trash', '-o', '-name', '.Trash', '-o', '-name',
               '.directory', ')', '-prune', '-o', '-print')
        log.debug('Running %s', ' '.join(quote(x) for x in cmd))
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
