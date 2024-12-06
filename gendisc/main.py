from __future__ import annotations

from pathlib import Path
from shlex import quote
import logging
import subprocess as sp

from fsutil import get_dir_size
import click

from .constants import BLURAY_QUADRUPLE_LAYER_SIZE_BYTES, BLURAY_TRIPLE_LAYER_SIZE_BYTES

__all__ = ('main',)

log = logging.getLogger(__name__)


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
def main(path: str,
         prefix: str | None = None,
         output_dir: str = '.',
         starting_index: int = 0,
         drive: str = '/dev/sr0',
         *,
         debug: bool = False) -> None:
    """Make a file listing filling up a disc."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    l_path = len(str(Path(path).resolve(strict=True).parent))
    if not prefix:
        prefix = Path(path).name
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)

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
                iso_file = f'{output_dir_p}/{fn_prefix}.iso'
                (output_dir_p / pl_filename).write_text('\n'.join(current_set) + '\n',
                                                        encoding='utf-8')
                (output_dir_p / sh_filename).write_text(rf"""#!/usr/bin/env bash
find '{path}' -type f -name .directory -delete
mkisofs -graft-points -volid '{volid}' -appid gendisc -sysid LINUX -rational-rock \
    -no-cache-inodes -udf -full-iso9660-filenames -disable-deep-relocation -iso-level 3 \
    -path-list '{output_dir_p}/{pl_filename}' \
    -o '{iso_file}'
echo 'Size: {total / 1024 ** 3:.02f} GiB'
pv '{iso_file}' | sha256sum > '{iso_file}.sha256sum'
loop_dev=$(udisksctl loop-setup --no-user-interaction -r -f '{iso_file}' 2>&1 |
    rev | awk '{{ print $1 }}' | rev | cut -d. -f1)
location=$(udisksctl mount --no-user-interaction -b "${{loop_dev}}" | rev | awk '{{ print $1 }}' |
    rev)
pushd "${{location}}" || exit 1
find . -type f > '{output_dir_p}/{volid}.list.txt'
tree > '{output_dir_p}/{volid}.tree.txt'
popd || exit 1
udisksctl unmount --no-user-interaction --object-path "block_devices/$(basename "${{loop_dev}}")"
udisksctl loop-delete --no-user-interaction -b "${{loop_dev}}"
cdrecord 'dev={drive}' gracetime=2 -v driveropts=burnfree speed=4 -eject -sao '{iso_file}'
eject -t
delay 30
# wait-for-disc -w 15 '{drive}'
this_sum=$(pv '{drive}' | sha256sum)
expected_sum=$(< '{iso_file}.sha256sum')
if [[ "${{this_sum}}" != "${{expected_sum}}" ]]; then
    echo 'Burnt disc is invalid!'
    exit 1
else
    rm '{iso_file}'
    echo trash {" ".join(quote(x) for x in (y.rsplit("=", 1)[-1] for y in current_set))}
    echo 'OK.'
fi
eject
""",
                                                        encoding='utf-8')
                (output_dir_p / sh_filename).chmod(0o755)
                log.info('%s total: %02f GiB', fn_prefix, total / 1024 ** 3)
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
            try:
                size = get_dir_size(dir_)
            except OSError:
                size = Path(dir_).stat().st_size
            next_total = total + size
            log.debug('Directory: %s - %f GiB', dir_, size / 1024 ** 3)
            log.debug('Current total: %.02f / %.02f', total / 1024 ** 3, target_size / 1024 ** 3)
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
                log.debug('Directory %s too large for Blu-ray. Splitting separately.', dir_)
                split_dir(dir_, f'{prefix}-{Path(dir_).name}')
                reset()
                continue
            total = next_total
            fixed = dir_[l_path + 1:].replace('=', '\\=')
            current_set.append(f'{fixed}={dir_}')

        append_set()

    split_dir(path, prefix, starting_index)
