# ruff: noqa: SLF001
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from gendisc.utils import (
    DirectorySplitter,
    LazyMounts,
    WriteSpeeds,
    get_dir_size,
    get_disc_type,
    is_cross_fs,
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
    mocker.patch('gendisc.utils.get_file_size', side_effect=[OSError, 512, 512, 512])
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = get_dir_size('dir2')
    assert size == 1536


def test_get_dir_size_raises_not_a_directory(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.isdir', return_value=False)
    with pytest.raises(NotADirectoryError):
        get_dir_size('not_a_dir')


def test_get_dir_size_reports_buggy_fs_once(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils._REPORTED_BUGGY_FS', False)  # noqa: FBT003
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mock_log_warning = mocker.patch('gendisc.utils.log.warning')
    mocker.patch('gendisc.utils.walk',
                 side_effect=[[('base', [], ['a'])], [('base', [], ['a'])], [('base', [], ['a'])],
                              [('base', [], ['a'])]])
    mocker.patch('gendisc.utils.get_file_size', side_effect=[OSError, 2048, OSError, 2048])
    get_dir_size('dir')
    mock_log_warning.assert_called_once_with(
        'Buggy file system (cifs with "unix" option?) reported directory %s as file.', 'base/a')
    mock_log_warning.reset_mock()
    get_dir_size('dir')
    assert mock_log_warning.call_count == 0


def test_get_dir_size_reports_oserror_exception(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.isdir', side_effect=[True, False])
    mock_log_exception = mocker.patch('gendisc.utils.log.exception')
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a'])])
    mocker.patch('gendisc.utils.get_file_size', side_effect=OSError)
    get_dir_size('dir')
    mock_log_exception.assert_called_once_with(
        'Caught error getting file size for %s. It will not be considered part of the total.',
        'base/a')


def test_write_speeds_defaults() -> None:
    speeds = WriteSpeeds()
    assert speeds.cd == 24
    assert speeds.dvd == 8
    assert speeds.dvd_dl == 8
    assert speeds.bd == 4
    assert speeds.bd_dl == 6
    assert speeds.bd_tl == 4
    assert speeds.bd_xl == 4


def test_write_speeds_get_speed_valid() -> None:
    speeds = WriteSpeeds()
    assert speeds.get_speed('CD-R') == 24
    assert speeds.get_speed('DVD-R') == 8
    assert speeds.get_speed('DVD-R DL') == 8
    assert speeds.get_speed('BD-R') == 4
    assert speeds.get_speed('BD-R DL') == 6
    assert speeds.get_speed('BD-R XL (100 GB)') == 4
    assert speeds.get_speed('BD-R XL (128 GB)') == 4


def test_write_speeds_get_speed_invalid() -> None:
    speeds = WriteSpeeds()
    with pytest.raises(ValueError, match=r'Unknown disc type:'):
        speeds.get_speed('UNKNOWN-DISC')  # type: ignore[arg-type]


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


def test_directory_splitter_split(mocker: MockerFixture, mocker_fs: None) -> None:
    mock_path = mocker.patch('gendisc.utils.Path')
    mock_path.reset_mock()
    mock_write_text = (
        mock_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text)
    splitter = DirectorySplitter('test_path',
                                 'prefix-' * 10,
                                 preparer='preparer',
                                 publisher='publisher')
    splitter.split()
    assert len(splitter._sets) == 1
    assert len(splitter._sets[0]) == 1
    # Test the prefix is truncated
    shell = mock_write_text.call_args_list[1].args[0]
    assert 'mkisofs -graft-points -volid prefix-prefix-prefix-prefix-p-01' in shell
    assert '-preparer preparer -publisher publisher' in shell


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


def test_directory_splitter_split_skips_cross_fs(mocker: MockerFixture, mocker_fs: None) -> None:
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
    mock_write_spiral.assert_called_once_with(
        mock_path.return_value.__truediv__.return_value.__truediv__.return_value, 'prefix-01 || ')


def test_directory_splitter_split_file_too_large_for_bluray(mocker: MockerFixture,
                                                            mocker_fs: None) -> None:
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


def test_directory_splitter_split_file_too_large_for_bluray_already_xl(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='.\nfile1\nfile2\n'))
    mocker.patch('gendisc.utils.Path.resolve',
                 return_value=MagicMock(strict=True, parent=MagicMock()))
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 side_effect=[101 * 1024 * 1024 * 1024, 101 * 1024 * 1024 * 1024])
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 2


def test_directory_splitter_split_file_too_large_for_bluray_tl_but_not_xl(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='.\nfile1\n'))
    mocker.patch('gendisc.utils.Path.resolve',
                 return_value=MagicMock(strict=True, parent=MagicMock()))
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size', side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.get_file_size', return_value=100 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 1


def test_directory_splitter_split_file_too_large_for_split_dir_separately(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mock_log_debug = mocker.patch('gendisc.utils.log.debug')
    mocker.patch('gendisc.utils.shutil.which')
    mocker.patch('gendisc.utils.sp.run',
                 side_effect=[MagicMock(stdout='.\nfile1\n'),
                              MagicMock(stdout='.\n')])
    mocker.patch('gendisc.utils.Path.resolve',
                 return_value=MagicMock(strict=True, parent=MagicMock()))
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size', return_value=122 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 0
    mock_log_debug.assert_has_calls(
        [mocker.call('Directory %s too large for Blu-ray. Splitting separately.', 'file1')])


def test_directory_splitter_skip_files_that_raise_oserror(mocker: MockerFixture,
                                                          mocker_fs: None) -> None:
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
