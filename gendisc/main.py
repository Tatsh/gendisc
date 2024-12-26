from __future__ import annotations

from functools import cache, partialmethod
from pathlib import Path
from shlex import quote
import logging
import os
import shlex
import subprocess as sp

from fsutil import assert_dir, convert_size_bytes_to_string, get_file_size
from tqdm import tqdm
from wakepy import keep
import click

from .constants import BLURAY_QUADRUPLE_LAYER_SIZE_BYTES, BLURAY_TRIPLE_LAYER_SIZE_BYTES

__all__ = ('main',)

log = logging.getLogger(__name__)

cached_convert = cache(convert_size_bytes_to_string)
cached_get_file_size = cache(get_file_size)
cached_islink = cache(os.path.islink)
cached_join = cache(os.path.join)
cached_quote = cache(quote)
cached_walk = cache(os.walk)


@cache
def get_dir_size(path: str) -> int:
    size = 0
    assert_dir(path)
    for basepath, _, filenames in tqdm(cached_walk(path),
                                       desc=f'Calculating size of {path}',
                                       unit=' dir'):
        for filename in filenames:
            filepath = cached_join(basepath, filename)
            if not cached_islink(filepath):
                size += cached_get_file_size(filepath)
    return size


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.argument('path')
@click.option('-D',
              '--drive',
              default='/dev/sr0',
              help='Drive path.',
              type=click.Path(dir_okay=False))
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
              type=click.Path(file_okay=False))
@click.option('-p', '--prefix', help='Prefix for volume ID and files.')
@click.option('-r', '--delete', help='Issue rm commands instead of trash.', is_flag=True)
def main(path: str,
         drive: str = '/dev/sr0',
         output_dir: str = '.',
         prefix: str | None = None,
         starting_index: int = 0,
         *,
         debug: bool = False,
         delete: bool = False) -> None:
    """Make a file listing filling up a disc."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    if debug:
        tqdm.__init__ = partialmethod(  # type: ignore[assignment,method-assign]
            tqdm.__init__, disable=True)
    l_path = len(str(Path(path).resolve(strict=True).parent))
    if not prefix:
        prefix = Path(path).name
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)
    delete_command = 'rm -rf' if delete else 'trash'

    def split_dir(dir2: str, prefix: str, starting_index: int = 1) -> None:
        sets: list[list[str]] = []
        current_set: list[str] = []
        target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES
        total = 0
        next_total = 0

        def append_set() -> None:
            nonlocal current_set, sets
            if current_set:
                index = len(sets) + starting_index
                volid = f'{prefix}-{index:02d}'
                fn_prefix = f'{prefix}-{index:03d}'
                pl_filename = f'{fn_prefix}.path-list.txt'
                sh_filename = f'generate-{fn_prefix}.sh'
                iso_file = str(output_dir_p / f'{fn_prefix}.iso')
                sha256_filename = f'{iso_file}.sha256sum'
                list_txt_file = f'{output_dir_p / volid}.list.txt'
                tree_txt_file = f'{output_dir_p / volid}.tree.txt'
                dev_arg = cached_quote(f'dev={drive}')
                log.debug('Total: %s', cached_convert(total))
                (output_dir_p / pl_filename).write_text('\n'.join(current_set) + '\n',
                                                        encoding='utf-8')
                (output_dir_p / sh_filename).write_text(rf"""#!/usr/bin/env bash
find {cached_quote(path)} -type f -name .directory -delete
mkisofs -graft-points -volid {cached_quote(volid)} -appid gendisc -sysid LINUX -rational-rock \
    -no-cache-inodes -udf -full-iso9660-filenames -disable-deep-relocation -iso-level 3 \
    -path-list {cached_quote(str(output_dir_p / pl_filename))} \
    -o {cached_quote(iso_file)}
echo 'Size: {cached_convert(total)}'
pv {cached_quote(iso_file)} | sha256sum > {cached_quote(sha256_filename)}
loop_dev=$(udisksctl loop-setup --no-user-interaction -r -f {cached_quote(iso_file)} 2>&1 |
    rev | awk '{{ print $1 }}' | rev | cut -d. -f1)
location=$(udisksctl mount --no-user-interaction -b "${{loop_dev}}" | rev | awk '{{ print $1 }}' |
    rev)
pushd "${{location}}" || exit 1
find . -type f > {cached_quote(list_txt_file)}
tree > {cached_quote(tree_txt_file)}
popd || exit 1
udisksctl unmount --no-user-interaction --object-path "block_devices/$(basename "${{loop_dev}}")"
udisksctl loop-delete --no-user-interaction -b "${{loop_dev}}"
eject
echo 'Insert a blank disc and press return.'
read
delay 120
cdrecord {dev_arg} gracetime=2 -v driveropts=burnfree speed=4 -eject -sao {cached_quote(iso_file)}
eject -t
delay 30
# wait-for-disc -w 15 '{cached_quote(drive)}'
this_sum=$(pv {cached_quote(drive)} | sha256sum)
expected_sum=$(< {cached_quote(sha256_filename)})
if [[ "${{this_sum}}" != "${{expected_sum}}" ]]; then
    echo 'Burnt disc is invalid!'
    exit 1
else
    rm {cached_quote(iso_file)}
    {delete_command} {shlex.join(y.rsplit("=", 1)[-1] for y in current_set)}
    echo 'OK.'
fi
eject
echo 'Move disc to printer.'
""",
                                                        encoding='utf-8')
                (output_dir_p / sh_filename).chmod(0o755)
                log.debug('%s total: %s', fn_prefix, cached_convert(total))
                sets.append(current_set)

        def reset() -> None:
            nonlocal target_size, current_set, total
            target_size = BLURAY_TRIPLE_LAYER_SIZE_BYTES
            current_set = []
            total = 0

        def too_large() -> None:
            nonlocal next_total
            append_set()
            reset()
            next_total = size

        for dir_ in sorted(sorted(
                sp.run(('find', str(
                    Path(dir2).resolve(strict=True)), '-maxdepth', '1', '!', '-name', '.directory'),
                       check=True,
                       text=True,
                       capture_output=True).stdout.splitlines()[1:]),
                           key=lambda x: not Path(x).is_dir()):
            log.debug('Calculating size: %s', dir_)
            type_ = 'Directory'
            try:
                size = get_dir_size(dir_)
            except OSError:
                type_ = 'File'
                size = cached_get_file_size(dir_)
            next_total = total + size
            log.debug('%s: %s - %s', type_, dir_, cached_convert(size))
            log.debug('Current total: %s / %s', cached_convert(next_total),
                      cached_convert(target_size))
            if next_total > target_size:
                log.debug('Current set with %s exceeds target size.', dir_)
                if target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES:
                    log.debug('Trying quad layer.')
                    target_size = BLURAY_QUADRUPLE_LAYER_SIZE_BYTES
                    if next_total > target_size:
                        log.debug('Still too large. Appending to next set.')
                        too_large()
                else:
                    too_large()
            if (next_total > target_size and target_size == BLURAY_TRIPLE_LAYER_SIZE_BYTES
                    and next_total > BLURAY_QUADRUPLE_LAYER_SIZE_BYTES):
                if type_ == 'File':
                    log.warning(
                        'File %s too large for largest Blu-ray disc. It will not be processed.',
                        dir_)
                    continue
                log.debug('Directory %s too large for Blu-ray. Splitting separately.', dir_)
                split_dir(dir_, f'{prefix}-{Path(dir_).name}')
                reset()
                continue
            total = next_total
            fixed = dir_[l_path + 1:].replace('=', '\\=')
            current_set.append(f'{fixed}={dir_}')

        append_set()

    with keep.running():
        split_dir(path, prefix, starting_index)
