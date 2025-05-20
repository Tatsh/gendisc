"""Disc label generation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import (
    TYPE_CHECKING,
    SupportsFloat,
    SupportsIndex,
    TypeAlias,
)
from xml.sax.saxutils import escape
import logging
import math
import shutil
import subprocess as sp

if TYPE_CHECKING:
    import os

__all__ = ('MogrifyNotFound', 'Point', 'create_spiral_path', 'create_spiral_text_svg',
           'write_spiral_text_png', 'write_spiral_text_svg')

log = logging.getLogger(__name__)


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
DEFAULT_START_RADIUS = 0
DEFAULT_SPACE_PER_LOOP = 40
DEFAULT_START_THETA = -6840
DEFAULT_END_THETA = 0
DEFAULT_THETA_STEP = 30
DEFAULT_FONT_SIZE = 32
DEFAULT_WIDTH_HEIGHT = 800
DEFAULT_DPI = 300


def create_spiral_path(center: Point | None = None,
                       start_radius: float = DEFAULT_START_RADIUS,
                       space_per_loop: float = DEFAULT_SPACE_PER_LOOP,
                       start_theta: _SupportsFloatOrIndex = DEFAULT_START_THETA,
                       end_theta: _SupportsFloatOrIndex = DEFAULT_END_THETA,
                       theta_step: _SupportsFloatOrIndex = DEFAULT_THETA_STEP) -> str:
    """
    Get a path string for a spiral in a SVG file.

    Defaults to creating a spiral that starts at the outside and goes inwards.

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
        The starting angle of the spiral in degrees. Use a negative number to have the spiral start
        at the outside and go inwards.
    end_theta : float
        The ending angle of the spiral in degrees.
    theta_step : float
        The step size of the angle in degrees.

    Returns
    -------
    str
        The path string for the spiral. Goes inside a ``<path>`` in the ``d`` attribute.
    """
    log.debug(
        'Creating spiral path with center %s, start radius %.2f, space per loop %.2f, '
        'start theta %.2f, end theta %.2f, and theta step %.2f.', center, start_radius,
        space_per_loop, start_theta, end_theta, theta_step)
    center = center or Point(DEFAULT_WIDTH_HEIGHT, DEFAULT_WIDTH_HEIGHT)
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
    paths = f'M {_p_str(new_point)} Q '
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
        paths += f'{_p_str(control_point)}{_p_str(new_point)} '
    return paths.strip()


def create_spiral_text_svg(text: str,
                           width: int = DEFAULT_WIDTH_HEIGHT,
                           height: int | None = None,
                           view_box: tuple[int, int, int, int] | None = None,
                           font_size: int = DEFAULT_FONT_SIZE,
                           center: Point | None = None,
                           start_radius: float = DEFAULT_START_RADIUS,
                           space_per_loop: float = DEFAULT_SPACE_PER_LOOP,
                           start_theta: _SupportsFloatOrIndex = DEFAULT_START_THETA,
                           end_theta: _SupportsFloatOrIndex = DEFAULT_END_THETA,
                           theta_step: _SupportsFloatOrIndex = DEFAULT_THETA_STEP) -> str:
    """
    Create a spiral SVG text.

    Defaults to creating a spiral that starts at the outside and goes inwards.

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
    font_size : int
        The font size of the text in the SVG in pixels.
    center : Point
        The center of the spiral. If not specified, it will be set to (width, width).
    start_radius : float
        The starting radius of the spiral.
    space_per_loop : float
        The space between each loop of the spiral.
    start_theta : float
        The starting angle of the spiral in degrees. Use a negative number to have the spiral start
        at the outside and go inwards.
    end_theta : float
        The ending angle of the spiral in degrees.
    theta_step : float
        The step size of the angle in degrees.

    Returns
    -------
    str
        The SVG string for the spiral.
    """
    text = escape(text)
    center = center or Point(width, width)
    height = height or width
    view_box_s = ' '.join((str(x) for x in view_box) if view_box else ('0', '0', str(width * 2),
                                                                       str(height * 2)))
    path_d = create_spiral_path(center, start_radius, space_per_loop, start_theta, end_theta,
                                theta_step)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{view_box_s}">
  <style>
    .small {{
      font: {font_size}px sans-serif;
    }}
  </style>
  <path id="spiral" d="{path_d}" fill="none" stroke="black" stroke-width="0" />
  <text>
    <textPath href="#spiral" class="small">
    {text}
    </textPath>
  </text>
</svg>""".strip()


def write_spiral_text_svg(filename: str | os.PathLike[str],
                          text: str,
                          width: int = DEFAULT_WIDTH_HEIGHT,
                          height: int | None = None,
                          view_box: tuple[int, int, int, int] | None = None,
                          font_size: int = DEFAULT_FONT_SIZE,
                          center: Point | None = None,
                          start_radius: float = DEFAULT_START_RADIUS,
                          space_per_loop: float = DEFAULT_SPACE_PER_LOOP,
                          start_theta: _SupportsFloatOrIndex = DEFAULT_START_THETA,
                          end_theta: _SupportsFloatOrIndex = DEFAULT_END_THETA,
                          theta_step: _SupportsFloatOrIndex = DEFAULT_THETA_STEP) -> None:
    """
    Write a spiral text SVG string to a file.

    Defaults to creating a spiral that starts at the outside and goes inwards.

    Parameters
    ----------
    filename : str | os.PathLike[str]
        The filename to write the SVG to.
    text: str
        The text to put in the spiral.
    width : int
        The width of the SVG.
    height : int
        The height of the SVG.
    view_box : tuple[int, int, int, int] | None
        The view box of the SVG. If not specified, it will be set to
        ``(0, 0, width * 2, height * 2)``.
    font_size : int
        The font size of the text in the SVG in pixels.
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
    """
    filename = Path(filename)
    spiral_svg = create_spiral_text_svg(text, width, height or width, view_box, font_size, center,
                                        start_radius, space_per_loop, start_theta, end_theta,
                                        theta_step)
    filename.write_text(f'{spiral_svg}\n', encoding='utf-8')


class MogrifyNotFound(FileNotFoundError):
    """Raised when ``mogrify`` is not found in ``PATH``."""
    def __init__(self) -> None:
        msg = '`mogrify` not found in PATH. Please install ImageMagick.'
        super().__init__(msg)


def write_spiral_text_png(filename: str | os.PathLike[str],
                          text: str,
                          width: int = DEFAULT_WIDTH_HEIGHT,
                          height: int | None = None,
                          view_box: tuple[int, int, int, int] | None = None,
                          dpi: int = DEFAULT_DPI,
                          font_size: int = DEFAULT_FONT_SIZE,
                          center: Point | None = None,
                          start_radius: float = DEFAULT_START_RADIUS,
                          space_per_loop: float = DEFAULT_SPACE_PER_LOOP,
                          start_theta: _SupportsFloatOrIndex = DEFAULT_START_THETA,
                          end_theta: _SupportsFloatOrIndex = DEFAULT_END_THETA,
                          theta_step: _SupportsFloatOrIndex = DEFAULT_THETA_STEP,
                          *,
                          debug: bool = False,
                          keep: bool = False) -> None:
    """
    Write a spiral text SVG string to a file.

    Defaults to creating a spiral that starts at the outside and goes inwards.

    Requires ``mogrify`` from ImageMagick to be installed and in ``PATH``.

    Parameters
    ----------
    filename : str | os.PathLike[str]
        The filename to write the PNG to.
    text: str
        The text to put in the spiral.
    width : int
        The width of the SVG.
    height : int
        The height of the SVG.
    view_box : tuple[int, int, int, int] | None
        The view box of the SVG. If not specified, it will be set to
        ``(0, 0, width * 2, height * 2)``.
    font_size : int
        The font size of the text in the SVG in pixels.
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
    keep : bool
        If ``True``, keep the SVG file after conversion.

    Raises
    ------
    MogrifyNotFound
        If ``mogrify`` is not found in ``PATH``.
    FileNotFoundError
        If the PNG file could not be created.
    """
    if not (mogrify := shutil.which('mogrify')):
        raise MogrifyNotFound
    log.debug('Writing spiral text image to %s. Be patient!', filename)
    filename = Path(filename)
    svg_file = filename.with_suffix('.svg')
    write_spiral_text_svg(svg_file, text, width, height, view_box, font_size, center, start_radius,
                          space_per_loop, start_theta, end_theta, theta_step)
    size_args = ('-density', str(dpi), '-gravity', 'center', '-resize', '2800x2800', '-extent',
                 '2835x2835')
    cmd: tuple[str, ...] = (mogrify, '-comment', 'gendisc', '-colorspace', 'sRGB', '-units',
                            'PixelsPerInch', *size_args, '-background', 'none', '-format', 'png',
                            str(svg_file))
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)
    if not filename.exists():
        msg = f'Failed to create {filename}.'
        raise FileNotFoundError(msg)
    if not keep:
        svg_file.unlink()
