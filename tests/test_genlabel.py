from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from gendisc.genlabel import (
    MogrifyNotFound,
    Point,
    create_spiral_path,
    create_spiral_text_svg,
    line_intersection,
    write_spiral_text_png,
    write_spiral_text_svg,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_write_spiral_text_png_success(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.genlabel.write_spiral_text_svg', new_callable=AsyncMock)
    mock_proc = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_exec = mocker.patch('gendisc.genlabel.asyncio.create_subprocess_exec',
                             new_callable=AsyncMock,
                             return_value=mock_proc)
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_file = mock_async_path_cls.return_value
    mock_file.exists = AsyncMock(return_value=True)
    mock_svg = mock_file.with_suffix.return_value
    mock_svg.unlink = AsyncMock()
    await write_spiral_text_png('test.png', 'spiral text')
    mock_write_svg.assert_awaited_once()
    mock_exec.assert_awaited_once()
    mock_file.exists.assert_awaited_once()
    mock_svg.unlink.assert_awaited_once()


async def test_write_spiral_text_png_keep_svg(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.genlabel.write_spiral_text_svg', new_callable=AsyncMock)
    mock_proc = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('gendisc.genlabel.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_file = mock_async_path_cls.return_value
    mock_file.exists = AsyncMock(return_value=True)
    mock_svg = mock_file.with_suffix.return_value
    mock_svg.unlink = AsyncMock()
    await write_spiral_text_png('file.png', 'txt', keep=True)
    mock_write_svg.assert_awaited_once()
    mock_svg.unlink.assert_not_called()


async def test_write_spiral_text_png_mogrify_not_found(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.genlabel.shutil.which', return_value=None)
    with pytest.raises(MogrifyNotFound, match='ImageMagick'):
        await write_spiral_text_png('file.png', 'txt')


async def test_write_spiral_text_png_forwards_svg_args(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.genlabel.write_spiral_text_svg', new_callable=AsyncMock)
    mock_proc = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('gendisc.genlabel.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_file = mock_async_path_cls.return_value
    mock_file.exists = AsyncMock(return_value=True)
    mock_svg = mock_file.with_suffix.return_value
    mock_svg.unlink = AsyncMock()
    center = Point(3, 4)
    await write_spiral_text_png('out.png',
                                'spiral',
                                200,
                                300, (0, 0, 400, 400),
                                150,
                                18,
                                center,
                                5,
                                10,
                                -100,
                                100,
                                10,
                                keep=True)
    mock_write_svg.assert_awaited_once_with(mock_svg, 'spiral', 200, 300, (0, 0, 400, 400), 18,
                                            center, 5, 10, -100, 100, 10)


async def test_write_spiral_text_png_subprocess_fails(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.genlabel.write_spiral_text_svg', new_callable=AsyncMock)
    mock_proc = MagicMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mocker.patch('gendisc.genlabel.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mocker.patch('gendisc.genlabel.AsyncPath')
    with pytest.raises(RuntimeError, match='mogrify exited'):
        await write_spiral_text_png('file.png', 'txt')


async def test_write_spiral_text_png_file_not_created(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.genlabel.write_spiral_text_svg', new_callable=AsyncMock)
    mock_proc = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mocker.patch('gendisc.genlabel.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mocker.patch('gendisc.genlabel.shutil.which', return_value='/usr/bin/mogrify')
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_file = mock_async_path_cls.return_value
    mock_file.exists = AsyncMock(return_value=False)
    mock_svg = mock_file.with_suffix.return_value
    mock_svg.unlink = AsyncMock()
    with pytest.raises(FileNotFoundError):
        await write_spiral_text_png('file.png', 'txt')


async def test_write_spiral_text_svg_writes_file(mocker: MockerFixture) -> None:
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_write_text = mock_async_path_cls.return_value.write_text = AsyncMock()
    mock_create_svg = mocker.patch('gendisc.genlabel.create_spiral_text_svg',
                                   return_value='<svg>...</svg>')
    await write_spiral_text_svg('spiral.svg', 'test spiral', width=123, height=456, font_size=22)
    mock_create_svg.assert_called_once_with('test spiral', 123, 456, None, 22, None, 0, 40, -6840,
                                            0, 30)
    mock_write_text.assert_awaited_once()
    args, kwargs = mock_write_text.call_args
    assert args[0].startswith('<svg')
    assert args[0].endswith('\n')
    assert kwargs['encoding'] == 'utf-8'


async def test_write_spiral_text_svg_with_all_args(mocker: MockerFixture) -> None:
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_write_text = mock_async_path_cls.return_value.write_text = AsyncMock()
    mock_create_svg = mocker.patch('gendisc.genlabel.create_spiral_text_svg',
                                   return_value='<svg>spiral</svg>')
    center = Point(1, 2)
    await write_spiral_text_svg('spiral.svg', 'spiral', 200, 300, (0, 0, 400, 400), 18, center, 5,
                                10, -100, 100, 10)
    mock_create_svg.assert_called_once_with('spiral', 200, 300, (0, 0, 400, 400), 18, center, 5, 10,
                                            -100, 100, 10)
    mock_write_text.assert_awaited_once()


async def test_write_spiral_text_svg_path_conversion(mocker: MockerFixture) -> None:
    mock_async_path_cls = mocker.patch('gendisc.genlabel.AsyncPath')
    mock_async_path_cls.return_value.write_text = AsyncMock()
    mocker.patch('gendisc.genlabel.create_spiral_text_svg', return_value='<svg>spiral</svg>')
    await write_spiral_text_svg('file.svg', 'abc')
    mock_async_path_cls.assert_any_call('file.svg')


def test_create_spiral_text_svg_defaults(mocker: MockerFixture) -> None:
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
    mocker.patch('gendisc.genlabel.create_spiral_path', return_value='M 0,0 Q 1,1 2,2')
    svg = create_spiral_text_svg('spiral', width=50, height=60)
    assert 'viewBox="0 0 100 120"' in svg


def test_create_spiral_text_svg_center_none(mocker: MockerFixture) -> None:
    called_args = {}

    def fake_create_spiral_path(center: Point, *args: Any, **kwargs: Any) -> str:
        called_args['center'] = center
        return 'M 0,0'

    mocker.patch('gendisc.genlabel.create_spiral_path', side_effect=fake_create_spiral_path)
    width = 77
    create_spiral_text_svg('spiral', width=width)
    assert called_args['center'] == Point(width, width)


def test_create_spiral_path_defaults() -> None:
    path = create_spiral_path()
    assert path.startswith('M ')
    assert 'Q' in path
    assert isinstance(path, str)


def test_create_spiral_path_custom_args() -> None:
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


def test_create_spiral_path_looping_and_path_content() -> None:
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


def test_line_intersection_parallel_lines_raises() -> None:
    with pytest.raises(ValueError, match='parallel'):
        line_intersection(1, 2, 1, 3)


def test_line_intersection_returns_point() -> None:
    result = line_intersection(1, 0, -1, 2)
    assert result == Point(1, 1)
