"""Main command."""
from __future__ import annotations

from functools import partialmethod
from pathlib import Path
import logging

from tqdm import tqdm
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
from .utils import DirectorySplitter, WriteSpeeds, setup_logging

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
    setup_logging(debug=debug)
    if debug:
        tqdm.__init__ = partialmethod(  # type: ignore[assignment,method-assign]
            tqdm.__init__, disable=True)
    output_dir_p = Path(output_dir).resolve()
    output_dir_p.mkdir(parents=True, exist_ok=True)
    with keep.running():
        DirectorySplitter(path,
                          prefix or path.name,
                          cross_fs=cross_fs,
                          delete_command='rm -rf' if delete else 'trash',
                          drive=drive,
                          labels=not no_labels,
                          output_dir=output_dir_p,
                          preparer=preparer,
                          publisher=publisher,
                          starting_index=starting_index,
                          write_speeds=WriteSpeeds(cd=cd_write_speed,
                                                   dvd=dvd_write_speed,
                                                   dvd_dl=dvd_dl_write_speed,
                                                   bd=bd_write_speed,
                                                   bd_dl=bd_dl_write_speed,
                                                   bd_tl=bd_tl_write_speed,
                                                   bd_xl=bd_xl_write_speed)).split()


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
    setup_logging(debug=debug)
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
                              keep=keep_svg,
                              debug=debug)
