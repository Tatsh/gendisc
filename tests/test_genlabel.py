from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gendisc.genlabel import (
    MogrifyNotFound,
    Point,
    _line_intersection,  # noqa: PLC2701
    create_spiral_path,
    create_spiral_text_svg,
    write_spiral_text_png,
    write_spiral_text_svg,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_write_spiral_text_png_success(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.genlabel.write_spiral_text_svg')
    mock_run = mocker.patch('gendisc.genlabel.sp.run')
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mock_exists = mocker.patch('gendisc.genlabel.Path.exists', return_value=True)
    mock_unlink = mocker.patch('gendisc.genlabel.Path.unlink')
    filename = 'test.png'
    text = 'spiral text'
    # Should not raise
    write_spiral_text_png(filename, text)
    mock_write_svg.assert_called_once()
    mock_run.assert_called_once()
    mock_exists.assert_called_once()
    mock_unlink.assert_called_once()


def test_write_spiral_text_png_keep_svg(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.genlabel.write_spiral_text_svg')
    mocker.patch('gendisc.genlabel.sp.run')
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mocker.patch('gendisc.genlabel.Path.exists', return_value=True)
    mock_unlink = mocker.patch('gendisc.genlabel.Path.unlink')
    write_spiral_text_png('file.png', 'txt', keep=True)
    mock_write_svg.assert_called_once()
    mock_unlink.assert_not_called()


def test_write_spiral_text_png_mogrify_not_found(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.genlabel.shutil.which', return_value=None)
    with pytest.raises(MogrifyNotFound):
        write_spiral_text_png('file.png', 'txt')


def test_write_spiral_text_png_file_not_created(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.genlabel.write_spiral_text_svg')
    mocker.patch('gendisc.genlabel.sp.run')
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mocker.patch('gendisc.genlabel.Path.exists', return_value=False)
    mocker.patch('gendisc.genlabel.Path.unlink')
    with pytest.raises(FileNotFoundError):
        write_spiral_text_png('file.png', 'txt')


def test_write_spiral_text_svg_writes_file(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.genlabel.Path')
    mock_write_text = mock_path.return_value.write_text
    mock_create_svg = mocker.patch('gendisc.genlabel.create_spiral_text_svg',
                                   return_value='<svg>...</svg>')
    filename = 'spiral.svg'
    text = 'test spiral'
    # Should not raise
    write_spiral_text_svg(filename, text, width=123, height=456, font_size=22)
    mock_create_svg.assert_called_once_with(text, 123, 456, None, 22, None, 0, 40, -6840, 0, 30)
    mock_write_text.assert_called_once()
    args, kwargs = mock_write_text.call_args
    assert args[0].startswith('<svg')
    assert args[0].endswith('\n')
    assert kwargs['encoding'] == 'utf-8'


def test_write_spiral_text_svg_with_all_args(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.genlabel.Path')
    mock_write_text = mock_path.return_value.write_text
    mock_create_svg = mocker.patch('gendisc.genlabel.create_spiral_text_svg',
                                   return_value='<svg>spiral</svg>')
    filename = 'spiral.svg'
    text = 'spiral'
    width = 200
    height = 300
    view_box = (0, 0, 400, 400)
    font_size = 18
    center = Point(1, 2)
    start_radius = 5
    space_per_loop = 10
    start_theta = -100
    end_theta = 100
    theta_step = 10
    write_spiral_text_svg(filename, text, width, height, view_box, font_size, center, start_radius,
                          space_per_loop, start_theta, end_theta, theta_step)
    mock_create_svg.assert_called_once_with(text, width, height, view_box, font_size, center,
                                            start_radius, space_per_loop, start_theta, end_theta,
                                            theta_step)
    mock_write_text.assert_called_once()
    args, kwargs = mock_write_text.call_args
    assert args[0].startswith('<svg')
    assert args[0].endswith('\n')
    assert kwargs['encoding'] == 'utf-8'


def test_write_spiral_text_svg_path_conversion(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.genlabel.Path')
    mock_write_text = mock_path.return_value.write_text
    mocker.patch('gendisc.genlabel.create_spiral_text_svg', return_value='<svg>spiral</svg>')
    filename = 'file.svg'
    text = 'abc'
    write_spiral_text_svg(filename, text)
    mock_path.assert_any_call(filename)
    mock_write_text.assert_called_once()


def test_create_spiral_text_svg_defaults(mocker: MockerFixture) -> None:
    # Patch create_spiral_path to return a known path string
    mock_path = mocker.patch('gendisc.genlabel.create_spiral_path', return_value='M 0,0 Q 1,1 2,2')
    text = 'hello spiral'
    svg = create_spiral_text_svg(text)
    assert svg.startswith('<?xml')
    assert '<svg' in svg
    assert '<textPath' in svg
    assert text in svg
    mock_path.assert_called_once()


def test_create_spiral_text_svg_custom_args(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.genlabel.create_spiral_path', return_value='M 1,2 Q 3,4 5,6')
    text = 'custom'
    width = 123
    height = 456
    view_box = (0, 0, 10, 20)
    font_size = 33
    center = Point(7, 8)
    start_radius = 9
    space_per_loop = 10
    start_theta = -100
    end_theta = 100
    theta_step = 15
    svg = create_spiral_text_svg(
        text,
        width=width,
        height=height,
        view_box=view_box,
        font_size=font_size,
        center=center,
        start_radius=start_radius,
        space_per_loop=space_per_loop,
        start_theta=start_theta,
        end_theta=end_theta,
        theta_step=theta_step,
    )
    assert f'width="{width}"' in svg
    assert f'height="{height}"' in svg
    assert f'font: {font_size}px' in svg
    assert 'viewBox="0 0 10 20"' in svg
    assert text in svg
    mock_path.assert_called_once_with(center, start_radius, space_per_loop, start_theta, end_theta,
                                      theta_step)


def test_create_spiral_text_svg_view_box_none(mocker: MockerFixture) -> None:
    # Should use default viewBox if not provided
    mocker.patch('gendisc.genlabel.create_spiral_path', return_value='M 0,0 Q 1,1 2,2')
    svg = create_spiral_text_svg('spiral', width=50, height=60)
    assert 'viewBox="0 0 100 120"' in svg


def test_create_spiral_text_svg_center_none(mocker: MockerFixture) -> None:
    # Should use (width, width) as center if not provided
    called_args = {}

    def fake_create_spiral_path(center: Point, *args: Any, **kwargs: Any) -> str:
        called_args['center'] = center
        return 'M 0,0'

    mocker.patch('gendisc.genlabel.create_spiral_path', side_effect=fake_create_spiral_path)
    width = 77
    create_spiral_text_svg('spiral', width=width)
    assert called_args['center'] == Point(width, width)


def test_create_spiral_path_defaults(mocker: MockerFixture) -> None:
    # Patch math.radians to identity for easier calculation
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 1)
    mocker.patch('math.sin', side_effect=lambda _: 0)
    # Patch _line_intersection to return a fixed point
    mocker.patch('gendisc.genlabel._line_intersection', return_value=Point(1, 2))
    # Patch _p_str to just return the coordinates as string
    mocker.patch('gendisc.genlabel._p_str', side_effect=lambda p: f'{p.x},{p.y} ')
    path = create_spiral_path()
    assert path.startswith('M ')
    assert 'Q' in path
    assert isinstance(path, str)


def test_create_spiral_path_custom_args(mocker: MockerFixture) -> None:
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 2)
    mocker.patch('math.sin', side_effect=lambda _: 3)
    mocker.patch('gendisc.genlabel._line_intersection', return_value=Point(5, 6))
    mocker.patch('gendisc.genlabel._p_str', side_effect=lambda p: f'{p.x}:{p.y} ')
    center = Point(10, 20)
    path = create_spiral_path(
        center=center,
        start_radius=2,
        space_per_loop=8,
        start_theta=-100,
        end_theta=100,
        theta_step=10,
    )
    assert path.startswith('M ')
    assert 'Q' in path
    assert isinstance(path, str)


def test_create_spiral_path_looping_and_path_content(mocker: MockerFixture) -> None:
    # Use real math for radians, cos, sin, but patch _line_intersection and _p_str
    path = create_spiral_path(
        center=Point(0, 0),
        start_radius=1,
        space_per_loop=2,
        start_theta=-60,
        end_theta=60,
        theta_step=30,
    )
    assert path.startswith('M ')
    assert 'Q' in path
    assert '1.0,0.0' in path


def test_create_spiral_path_parallel_lines_raises(mocker: MockerFixture) -> None:
    # Patch _line_intersection to raise ValueError for parallel lines
    def fake_line_intersection(m1: float, b1: float, m2: float, b2: float) -> Point:
        if m1 == m2:
            msg = 'Lines are parallel and do not intersect.'
            raise ValueError(msg)
        return Point(0, 0)

    mocker.patch('gendisc.genlabel._line_intersection', side_effect=fake_line_intersection)
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 1)
    mocker.patch('math.sin', side_effect=lambda _: 0)
    mocker.patch('gendisc.genlabel._p_str', side_effect=lambda p: f'{p.x},{p.y} ')
    with pytest.raises(ValueError, match='parallel'):
        _line_intersection(1, 2, 1, 3)
