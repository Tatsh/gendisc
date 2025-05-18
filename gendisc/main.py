"""Main command."""
from __future__ import annotations

from functools import partialmethod
from pathlib import Path
import logging

from tqdm import tqdm
from wakepy import keep
import click

from .genlabel import Point, write_spiral_text_png, write_spiral_text_svg
from .utils import DirectorySplitter

__all__ = ('main',)

log = logging.getLogger(__name__)


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
def main(path: Path,
         output_dir: Path,
         drive: Path,
         prefix: str | None = None,
         starting_index: int = 0,
         *,
         cross_fs: bool = False,
         debug: bool = False,
         delete: bool = False,
         no_labels: bool = False) -> None:
    """Make a file listing filling up discs."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    if debug:
        tqdm.__init__ = partialmethod(  # type: ignore[assignment,method-assign]
            tqdm.__init__, disable=True)
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)
    with keep.running():
        DirectorySplitter(path,
                          prefix or path.name,
                          delete_command='rm -rf' if delete else 'trash',
                          drive=drive,
                          output_dir=output_dir_p,
                          starting_index=starting_index,
                          cross_fs=cross_fs,
                          labels=not no_labels).split()


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.argument('text', nargs=-1)
@click.option('-E', '--end-theta', help='End theta.', type=float, default=0)
@click.option('-H', '--height', help='Height of the image.', type=int)
@click.option('-S', '--space-per-loop', help='Space per loop.', type=int, default=20)
@click.option('-T', '--start-theta', help='Start theta.', type=float, default=-6840)
@click.option('-V',
              '--view-box',
              help='SVG view box.',
              type=click.Tuple((int, int, int, int)),
              required=False)
@click.option('--dpi', help='Dots per inch.', type=int, default=600)
@click.option('--keep-svg', help='When generating the PNG, keep the SVG file.', is_flag=True)
@click.option('-c', '--center', help='Center of the spiral.', type=click.Tuple((float, float)))
@click.option('-f', '--font-size', help='Font size.', type=float, default=16)
@click.option('-g', '--svg', help='Output SVG.', is_flag=True)
@click.option('-o',
              '--output',
              help='Output file name.',
              type=click.Path(path_type=Path, dir_okay=False),
              default='out.png')
@click.option('-r', '--start-radius', help='Start radius.', type=float, default=0)
@click.option('-t', '--theta-step', help='Theta step.', type=float, default=30)
@click.option('-w',
              '--width',
              help='Width of the image.',
              type=click.IntRange(1, 10000),
              default=400)
def genlabel_main(text: tuple[str, ...],
                  output: Path,
                  center: tuple[float, float] | None = None,
                  dpi: int = 600,
                  end_theta: float = 0,
                  font_size: int = 16,
                  height: int | None = None,
                  space_per_loop: int = 20,
                  start_radius: int = 0,
                  start_theta: float = -6840,
                  theta_step: float = 30,
                  view_box: tuple[int, int, int, int] | None = None,
                  width: int = 400,
                  *,
                  keep_svg: bool = False,
                  svg: bool = False) -> None:
    """Generate an image intended for printing on disc consisting of text in a spiral."""
    if svg:
        write_spiral_text_svg(output.with_suffix('.svg'), ' '.join(text), width, height, view_box,
                              font_size,
                              Point(*center) if center else None, start_radius, space_per_loop,
                              start_theta, end_theta, theta_step)
    else:
        write_spiral_text_png(output,
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
                              keep=keep_svg)
