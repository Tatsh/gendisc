from __future__ import annotations

from functools import partialmethod
from pathlib import Path
import logging

from tqdm import tqdm
from wakepy import keep
import click

from .utils import DirectorySplitter

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
@click.option('-r', '--delete', help='Issue rm commands instead of trash.', is_flag=True)
@click.option('--cross-fs', help='Allow crossing file systems.', is_flag=True)
def main(path: str,
         drive: str = '/dev/sr0',
         output_dir: str = '.',
         prefix: str | None = None,
         starting_index: int = 0,
         *,
         cross_fs: bool = False,
         debug: bool = False,
         delete: bool = False) -> None:
    """Make a file listing filling up a disc."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    if debug:
        tqdm.__init__ = partialmethod(  # type: ignore[assignment,method-assign]
            tqdm.__init__, disable=True)
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)
    with keep.running():
        DirectorySplitter(path,
                          prefix or Path(path).name,
                          'rm -rf' if delete else 'trash',
                          drive,
                          output_dir_p,
                          starting_index,
                          cross_fs=cross_fs).split()
