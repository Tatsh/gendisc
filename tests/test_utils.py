# ruff: noqa: SLF001
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from gendisc.utils import (
    DirectorySplitter,
    LazyMounts,
    MogrifyNotFound,
    Point,
    _line_intersection,  # noqa: PLC2701
    create_spiral_path,
    create_spiral_text_svg,
    get_dir_size,
    get_disc_type,
    is_cross_fs,
    write_spiral_text_png,
    write_spiral_text_svg,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def mocker_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('basepath', [], ['file1', 'file2'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', return_value=1024)
    mocker.patch('gendisc.utils.Path')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='dir1\ndir2\n'))


def test_get_disc_type() -> None:
    assert get_disc_type(700 * 1024 * 1024) == 'DVD-R'
    assert get_disc_type(int(4.7 * 1024 * 1024 * 1024)) == 'DVD-R DL'
    assert get_disc_type(int(8.5 * 1024 * 1024 * 1024)) == 'BD-R'
    assert get_disc_type(25 * 1024 * 1024 * 1024) == 'BD-R DL'
    assert get_disc_type(50 * 1024 * 1024 * 1024) == 'BD-R XL (100 GB)'
    assert get_disc_type(100 * 1024 * 1024 * 1024) == 'BD-R XL (128 GB)'
    with pytest.raises(ValueError, match=r'Disc size exceeds maximum supported size.'):
        get_disc_type(128 * 1024 * 1024 * 1024)


def test_get_dir_size() -> None:
    with pytest.raises(NotADirectoryError):
        get_dir_size('non-existent-path')


def test_get_dir_size_returns_correct_size(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a', 'b', 'c'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', return_value=2048)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = get_dir_size('some_dir')
    assert size == 3 * 2048


def test_get_dir_size_skips_symlinks(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a', 'b'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', side_effect=[False, True])
    mocker.patch('gendisc.utils.get_file_size', return_value=4096)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = get_dir_size('dir')
    assert size == 4096


def test_get_dir_size_handles_oserror(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['z', 'x'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', side_effect=[OSError, 512])
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = get_dir_size('dir2')
    assert size == 512


def test_get_dir_size_raises_not_a_directory(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.isdir', return_value=False)
    with pytest.raises(NotADirectoryError):
        get_dir_size('not_a_dir')


def test_is_cross_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.MOUNTS', ['/', '/mnt'])
    assert is_cross_fs('/') is True
    assert is_cross_fs('/mnt') is True
    assert is_cross_fs('/home') is False


def test_directory_splitter_init(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    assert splitter._prefix == 'prefix'
    assert splitter._delete_command == 'trash'
    assert splitter._drive == '/dev/sr0'
    assert splitter._starting_index == 1


def test_directory_splitter_split(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 1
    assert len(splitter._sets[0]) == 1


def test_directory_splitter_too_large(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter._size = 1024
    splitter._too_large()
    assert splitter._total == 0
    assert len(splitter._current_set) == 0


def test_directory_splitter_append_set(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter._current_set = ['file1', 'file2']
    splitter._total = 2048
    splitter._append_set()
    assert len(splitter._sets) == 1
    assert len(splitter._sets[0]) == 2


def test_directory_splitter_split_skips_cross_fs(mocker: MockerFixture) -> None:
    mock_write_spiral = mocker.patch('gendisc.utils.write_spiral_text_png')
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='.\ndir1\ndir2\n'))
    mock_path = mocker.patch('gendisc.utils.Path')
    mock_path.resolve.return_value = MagicMock(strict=True, parent=MagicMock())
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['file1'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', return_value=1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mocker.patch('gendisc.utils.is_cross_fs', side_effect=lambda d: d == 'dir2')
    splitter = DirectorySplitter('test_path', 'prefix', labels=True)
    splitter.split()
    assert len(splitter._sets) == 1
    assert all('dir1' in entry for entry in splitter._sets[0])
    assert all('dir2' not in entry for entry in splitter._sets[0])
    mock_write_spiral.assert_called_once_with(mock_path.return_value.__truediv__.return_value,
                                              'prefix-01 || ')


def test_directory_splitter_split_file_too_large_for_bluray(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='.\nfile1\n'))
    mocker.patch('gendisc.utils.Path.resolve',
                 return_value=MagicMock(strict=True, parent=MagicMock()))
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size', side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.get_file_size', return_value=200 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 0


def test_directory_splitter_skip_files_that_raise_oserror(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='.\ndir_big\n'))
    mocker.patch('gendisc.utils.Path.resolve',
                 return_value=MagicMock(strict=True, parent=MagicMock()))
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size', side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.get_file_size', side_effect=OSError)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    recursive_called = {}
    orig_split = DirectorySplitter.split

    def fake_split(self: Any) -> None:
        recursive_called['called'] = True

    mocker.patch.object(DirectorySplitter, 'split', fake_split)
    splitter = DirectorySplitter('test_path', 'prefix', labels=True)
    orig_split(splitter)
    assert splitter._total == 0
    assert splitter._current_set == []


def test_lazy_mounts_read(mocker: MockerFixture) -> None:
    mock_mounts_content = '/dev/sda1 / ext4 rw 0 0\n/dev/sdb1 /mnt ext4 rw 0 0'
    mocker.patch('gendisc.utils.Path.read_text', return_value=mock_mounts_content)
    mounts = LazyMounts._read()
    assert mounts == ['/', '/mnt']


def test_lazy_mounts_initialize_and_reload(mocker: MockerFixture) -> None:
    mocker.patch.object(LazyMounts, '_read', return_value=['/mnt', '/media'])
    lm = LazyMounts()
    assert lm._mounts is None
    lm.initialize()
    assert lm._mounts == ['/mnt', '/media']
    lm._mounts = None
    lm.reload()
    assert lm._mounts == ['/mnt', '/media']


def test_lazy_mounts_mounts_property(mocker: MockerFixture) -> None:
    mocker.patch.object(LazyMounts, '_read', return_value=['/foo', '/bar'])
    lm = LazyMounts()
    mounts = lm.mounts
    assert mounts == ['/foo', '/bar']


def test_lazy_mounts_getitem_and_len(mocker: MockerFixture) -> None:
    mocker.patch.object(LazyMounts, '_read', return_value=['/a', '/b', '/c'])
    lm = LazyMounts()
    # __getitem__ int
    assert lm[0] == '/a'
    # __getitem__ slice
    assert lm[1:] == ['/b', '/c']
    # __len__
    assert len(lm) == 3


def test_write_spiral_text_png_success(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.utils.write_spiral_text_svg')
    mock_run = mocker.patch('gendisc.utils.sp.run')
    mocker.patch('gendisc.utils.shutil.which', return_value='/usr/bin/mogrify')
    mock_exists = mocker.patch('gendisc.utils.Path.exists', return_value=True)
    mock_unlink = mocker.patch('gendisc.utils.Path.unlink')
    filename = 'test.png'
    text = 'spiral text'
    # Should not raise
    write_spiral_text_png(filename, text)
    mock_write_svg.assert_called_once()
    mock_run.assert_called_once()
    mock_exists.assert_called_once()
    mock_unlink.assert_called_once()


def test_write_spiral_text_png_keep_svg(mocker: MockerFixture) -> None:
    mock_write_svg = mocker.patch('gendisc.utils.write_spiral_text_svg')
    mocker.patch('gendisc.utils.sp.run')
    mocker.patch('gendisc.utils.shutil.which', return_value='/usr/bin/mogrify')
    mocker.patch('gendisc.utils.Path.exists', return_value=True)
    mock_unlink = mocker.patch('gendisc.utils.Path.unlink')
    write_spiral_text_png('file.png', 'txt', keep=True)
    mock_write_svg.assert_called_once()
    mock_unlink.assert_not_called()


def test_write_spiral_text_png_mogrify_not_found(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.shutil.which', return_value=None)
    with pytest.raises(MogrifyNotFound):
        write_spiral_text_png('file.png', 'txt')


def test_write_spiral_text_png_file_not_created(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.write_spiral_text_svg')
    mocker.patch('gendisc.utils.sp.run')
    mocker.patch('gendisc.utils.shutil.which', return_value='/usr/bin/mogrify')
    mocker.patch('gendisc.utils.Path.exists', return_value=False)
    mocker.patch('gendisc.utils.Path.unlink')
    with pytest.raises(FileNotFoundError):
        write_spiral_text_png('file.png', 'txt')


def test_write_spiral_text_svg_writes_file(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.utils.Path')
    mock_write_text = mock_path.return_value.write_text
    mock_create_svg = mocker.patch('gendisc.utils.create_spiral_text_svg',
                                   return_value='<svg>...</svg>')
    filename = 'spiral.svg'
    text = 'test spiral'
    # Should not raise
    write_spiral_text_svg(filename, text, width=123, height=456, font_size=22)
    mock_create_svg.assert_called_once_with(text, 123, 456, None, 22, None, 0, 20, -6840, 0, 30)
    mock_write_text.assert_called_once()
    args, kwargs = mock_write_text.call_args
    assert args[0].startswith('<svg')
    assert args[0].endswith('\n')
    assert kwargs['encoding'] == 'utf-8'


def test_write_spiral_text_svg_with_all_args(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.utils.Path')
    mock_write_text = mock_path.return_value.write_text
    mock_create_svg = mocker.patch('gendisc.utils.create_spiral_text_svg',
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
    mock_path = mocker.patch('gendisc.utils.Path')
    mock_write_text = mock_path.return_value.write_text
    mocker.patch('gendisc.utils.create_spiral_text_svg', return_value='<svg>spiral</svg>')
    filename = 'file.svg'
    text = 'abc'
    write_spiral_text_svg(filename, text)
    mock_path.assert_any_call(filename)
    mock_write_text.assert_called_once()


def test_create_spiral_text_svg_defaults(mocker: MockerFixture) -> None:
    # Patch create_spiral_path to return a known path string
    mock_path = mocker.patch('gendisc.utils.create_spiral_path', return_value='M 0,0 Q 1,1 2,2')
    text = 'hello spiral'
    svg = create_spiral_text_svg(text)
    assert svg.startswith('<?xml')
    assert '<svg' in svg
    assert '<textPath' in svg
    assert text in svg
    mock_path.assert_called_once()


def test_create_spiral_text_svg_custom_args(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('gendisc.utils.create_spiral_path', return_value='M 1,2 Q 3,4 5,6')
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
    mocker.patch('gendisc.utils.create_spiral_path', return_value='M 0,0 Q 1,1 2,2')
    svg = create_spiral_text_svg('spiral', width=50, height=60)
    assert 'viewBox="0 0 100 120"' in svg


def test_create_spiral_text_svg_center_none(mocker: MockerFixture) -> None:
    # Should use (width, width) as center if not provided
    called_args = {}

    def fake_create_spiral_path(center: Point, *args: Any, **kwargs: Any) -> str:
        called_args['center'] = center
        return 'M 0,0'

    mocker.patch('gendisc.utils.create_spiral_path', side_effect=fake_create_spiral_path)
    width = 77
    create_spiral_text_svg('spiral', width=width)
    assert called_args['center'] == Point(width, width)


def test_create_spiral_path_defaults(mocker: MockerFixture) -> None:
    # Patch math.radians to identity for easier calculation
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 1)
    mocker.patch('math.sin', side_effect=lambda _: 0)
    # Patch _line_intersection to return a fixed point
    mocker.patch('gendisc.utils._line_intersection', return_value=Point(1, 2))
    # Patch _p_str to just return the coordinates as string
    mocker.patch('gendisc.utils._p_str', side_effect=lambda p: f'{p.x},{p.y} ')
    path = create_spiral_path()
    assert path.startswith('M ')
    assert 'Q' in path
    assert isinstance(path, str)


def test_create_spiral_path_custom_args(mocker: MockerFixture) -> None:
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 2)
    mocker.patch('math.sin', side_effect=lambda _: 3)
    mocker.patch('gendisc.utils._line_intersection', return_value=Point(5, 6))
    mocker.patch('gendisc.utils._p_str', side_effect=lambda p: f'{p.x}:{p.y} ')
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

    mocker.patch('gendisc.utils._line_intersection', side_effect=fake_line_intersection)
    mocker.patch('math.radians', side_effect=float)
    mocker.patch('math.cos', side_effect=lambda _: 1)
    mocker.patch('math.sin', side_effect=lambda _: 0)
    mocker.patch('gendisc.utils._p_str', side_effect=lambda p: f'{p.x},{p.y} ')
    with pytest.raises(ValueError, match='parallel'):
        _line_intersection(1, 2, 1, 3)
