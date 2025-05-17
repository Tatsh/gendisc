"""Utilities."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import (
    SupportsFloat,
    SupportsIndex,
    TypeAlias,
    overload,
)
import logging
import math
import os
import shlex
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

__all__ = ('DirectorySplitter', 'Point', 'create_spiral_path', 'create_spiral_svg', 'get_disc_type',
           'write_spiral_svg')

log = logging.getLogger(__name__)

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


def get_disc_type(total: int) -> str:  # noqa: PLR0911
    """
    Get disc type based on total size.

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


class DirectorySplitter:
    """Split directories into sets for burning to disc."""
    def __init__(self,
                 path: Path | str,
                 prefix: str,
                 delete_command: str = 'trash',
                 drive: str = '/dev/sr0',
                 output_dir: Path | str = '.',
                 starting_index: int = 1,
                 *,
                 cross_fs: bool = False) -> None:
        self._cross_fs = cross_fs
        self._current_set: list[str] = []
        self._delete_command = delete_command
        self._drive = drive
        self._l_path = len(str(Path(path).resolve(strict=True).parent))
        self._next_total = 0
        self._output_dir_p = Path(output_dir)
        self._path = Path(path)
        self._prefix = prefix
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
# wait-for-disc -w 15 '{quote(self._drive)}'
this_sum=$(pv {quote(self._drive)} | sha256sum)
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
                DirectorySplitter(dir_,
                                  f'{self._prefix}-{Path(dir_).name}',
                                  self._delete_command,
                                  self._drive,
                                  self._output_dir_p,
                                  self._starting_index,
                                  cross_fs=self._cross_fs).split()
                self._reset()
                continue
            self._total = self._next_total
            fixed = dir_[self._l_path + 1:].replace('=', '\\=')
            self._current_set.append(f'{fixed}={dir_}')

        self._append_set()


@dataclass
class Point:
    """Point class for SVG paths."""
    x: float
    """X coordinate."""
    y: float
    """Y coordinate."""


def _line_intersection(m1: float, b1: float, m2: float, b2: float) -> Point:
    """
    Find the intersection of two lines.

    Parameters
    ----------
    m1 : int
        Slope of the first line.
    b1 : int
        Y-intercept of the first line.
    m2 : int
        Slope of the second line.
    b2 : int
        Y-intercept of the second line.

    Returns
    -------
    Point
        X and Y coordinates of the intersection point.

    Raises
    ------
    ValueError
        If the lines are parallel and do not intersect.
    """
    if m1 == m2:
        msg = 'Lines are parallel and do not intersect.'
        raise ValueError(msg)
    x = (b2 - b1) / (m1 - m2)
    y = m1 * x + b1
    return Point(x, y)


def _p_str(point: Point) -> str:
    """
    Convert a point to a string.

    Parameters
    ----------
    point : tuple[int, int]
        The point to convert.

    Returns
    -------
    str
        The point as a string.
    """
    return f'{point.x},{point.y} '


_SupportsFloatOrIndex: TypeAlias = SupportsFloat | SupportsIndex


def create_spiral_path(center: Point | None = None,
                       start_radius: float = 0,
                       space_per_loop: float = 25,
                       start_theta: _SupportsFloatOrIndex = 0,
                       end_theta: _SupportsFloatOrIndex = 2160,
                       theta_step: _SupportsFloatOrIndex = 30) -> str:
    """
    Get a path string for a spiral in a SVG file.

    Algorithm borrowed from `How to make a spiral in SVG? <https://stackoverflow.com/a/49099258/374110>`_.

    Parameters
    ----------
    center : Point
        The center of the spiral.
    start_radius : float
        The starting radius of the spiral.
    space_per_loop : float
        The space between each loop of the spiral.
    start_theta : float
        The starting angle of the spiral in degrees.
    end_theta : float
        The ending angle of the spiral in degrees.
    theta_step : float
        The step size of the angle in degrees.

    Returns
    -------
    str
        The path string for the spiral. Goes inside a ``<path>`` in the ``d`` attribute.
    """
    center = center or Point(400, 400)
    # Rename spiral parameters for the formula r = a + bθ.
    a = start_radius  # Start distance from center
    b = space_per_loop / math.pi / 2  # Space between each loop
    # Convert angles to radians.
    old_theta = new_theta = math.radians(start_theta)
    end_theta = math.radians(end_theta)
    theta_step = math.radians(theta_step)
    # Radii
    new_r = a + b * new_theta
    # Start and end points
    old_point = Point(0, 0)
    new_point = Point(center.x + new_r * math.cos(new_theta),
                      center.y + new_r * math.sin(new_theta))
    # Slopes of tangents
    new_slope = ((b * math.sin(old_theta) + (a + b * new_theta) * math.cos(old_theta)) /
                 (b * math.cos(old_theta) - (a + b * new_theta) * math.sin(old_theta)))
    paths = f'M {_p_str(new_point)}'
    while old_theta < end_theta - theta_step:
        old_theta = new_theta
        new_theta += theta_step
        old_r = new_r
        new_r = a + b * new_theta
        old_point.x = new_point.x
        old_point.y = new_point.y
        new_point.x = center.x + new_r * math.cos(new_theta)
        new_point.y = center.y + new_r * math.sin(new_theta)
        # Slope calculation with the formula
        # m := (b * sin(θ) + (a + b * θ) * cos(θ)) / (b * cos(θ) - (a + b * θ) * sin(θ))
        a_plus_b_theta = a + b * new_theta
        old_slope = new_slope
        new_slope = ((b * math.sin(new_theta) + a_plus_b_theta * math.cos(new_theta)) /
                     (b * math.cos(new_theta) - a_plus_b_theta * math.sin(new_theta)))

        old_intercept = -(old_slope * old_r * math.cos(old_theta) - old_r * math.sin(old_theta))
        new_intercept = -(new_slope * new_r * math.cos(new_theta) - new_r * math.sin(new_theta))
        control_point = _line_intersection(old_slope, old_intercept, new_slope, new_intercept)
        # Offset the control point by the center offset.
        control_point.x += center.x
        control_point.y += center.y
        paths += f'Q {_p_str(control_point)}{_p_str(new_point)}'
    return paths.strip()


def create_spiral_svg(text: str,
                      width: int = 400,
                      height: int = 400,
                      view_box: str = '0 0 800 800',
                      font_size: int = 13,
                      center: Point | None = None,
                      start_radius: float = 0,
                      space_per_loop: float = 25,
                      start_theta: _SupportsFloatOrIndex = 0,
                      end_theta: _SupportsFloatOrIndex = 2160,
                      theta_step: _SupportsFloatOrIndex = 30,
                      start_offset: float | str = 0) -> str:
    """
    Create a spiral SVG.

    Parameters
    ----------
    text: str
        The text to put in the spiral.
    width : int
        The width of the SVG.
    height : int
        The height of the SVG.
    view_box : str
        The view box of the SVG.
    center : Point
        The center of the spiral.
    start_radius : float
        The starting radius of the spiral.
    space_per_loop : float
        The space between each loop of the spiral.
    start_theta : float
        The starting angle of the spiral in degrees.
    end_theta : float
        The ending angle of the spiral in degrees.
    theta_step : float
        The step size of the angle in degrees.
    start_offset: float | str
        The starting offset of the text in the spiral. Can be a percentage (e.g. '50%') or a
        number (e.g. 100). If a number, it is the distance from the start of the spiral in pixels.

    Returns
    -------
    str
        The SVG string for the spiral.
    """
    center = center or Point(400, 400)
    path = create_spiral_path(center, start_radius, space_per_loop, start_theta, end_theta,
                              theta_step)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{view_box}">
  <style>
    .small {{
      font: {font_size}px sans-serif;
    }}
  </style>
  <path id="spiral" d="{path}" fill="none" stroke="black" stroke-width="0" />
  <text>
    <textPath href="#spiral" class="small" startOffset="{start_offset}">
    {text}
    </textPath>
  </text>
</svg>""".strip()


def write_spiral_svg(filename: str | Path,
                     text: str,
                     width: int = 400,
                     height: int = 400,
                     view_box: str = '0 0 800 800',
                     font_size: int = 13,
                     center: Point | None = None,
                     start_radius: float = 0,
                     space_per_loop: float = 25,
                     start_theta: _SupportsFloatOrIndex = 0,
                     end_theta: _SupportsFloatOrIndex = 2160,
                     theta_step: _SupportsFloatOrIndex = 30,
                     start_offset: float | str = 0) -> None:
    """
    Write a spiral SVG to a file.

    Create a spiral SVG.

    Parameters
    ----------
    filename : str | Path
        The filename to write the SVG to.
    text: str
        The text to put in the spiral.
    width : int
        The width of the SVG.
    height : int
        The height of the SVG.
    view_box : str
        The view box of the SVG.
    center : Point
        The center of the spiral.
    start_radius : float
        The starting radius of the spiral.
    space_per_loop : float
        The space between each loop of the spiral.
    start_theta : float
        The starting angle of the spiral in degrees.
    end_theta : float
        The ending angle of the spiral in degrees.
    theta_step : float
        The step size of the angle in degrees.
    start_offset: float | str
        The starting offset of the text in the spiral. Can be a percentage (e.g. '50%') or a
        number (e.g. 100). If a number, it is the distance from the start of the spiral in pixels.
    """
    filename = Path(filename)
    spiral_svg = create_spiral_svg(text, width, height, view_box, font_size, center, start_radius,
                                   space_per_loop, start_theta, end_theta, theta_step, start_offset)
    filename.write_text(f'{spiral_svg}\n', encoding='utf-8')
