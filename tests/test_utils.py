from unittest.mock import MagicMock

from gendisc.utils import DirectorySplitter, generate_label_image, get_disc_type, is_cross_fs
from pytest_mock import MockerFixture
import pytest


@pytest.fixture
def mocker_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('basepath', [], ['file1', 'file2'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', return_value=1024)
    mocker.patch('gendisc.utils.Path')
    mocker.patch('gendisc.utils.sp.run', return_value=MagicMock(stdout='dir1\ndir2\n'))


def test_generate_label_image(mocker: MockerFixture) -> None:
    mock_image = mocker.patch('gendisc.utils.Image')
    mock_font = mocker.patch('gendisc.utils.Font')
    generate_label_image(['content1', 'content2'], 'test.png')
    mock_image.assert_called_once()
    mock_font.assert_called_once_with('Noto', 20)


def test_get_disc_type() -> None:
    assert get_disc_type(700 * 1024 * 1024) == 'DVD-R'
    assert get_disc_type(int(4.7 * 1024 * 1024 * 1024)) == 'DVD-R'
    assert get_disc_type(int(8.5 * 1024 * 1024 * 1024)) == 'BD-R'
    assert get_disc_type(25 * 1024 * 1024 * 1024) == 'BD-R DL'
    assert get_disc_type(50 * 1024 * 1024 * 1024) == 'BD-R XL (100 GB)'
    assert get_disc_type(100 * 1024 * 1024 * 1024) == 'BD-R XL (128 GB)'
    with pytest.raises(ValueError, match=r'Disc size exceeds maximum supported size.'):
        get_disc_type(128 * 1024 * 1024 * 1024)


def test_is_cross_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.MOUNTS', ['/', '/mnt'])
    assert is_cross_fs('/') is True
    assert is_cross_fs('/mnt') is True
    assert is_cross_fs('/home') is False


def test_directory_splitter_init(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    assert splitter._prefix == 'prefix'  # noqa: SLF001
    assert splitter._delete_command == 'trash'  # noqa: SLF001
    assert splitter._drive == '/dev/sr0'  # noqa: SLF001
    assert splitter._starting_index == 1  # noqa: SLF001


def test_directory_splitter_split(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter.split()
    assert len(splitter._sets) == 1  # noqa: SLF001
    assert len(splitter._sets[0]) == 1  # noqa: SLF001


def test_directory_splitter_too_large(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter._size = 1024  # noqa: SLF001
    splitter._too_large()  # noqa: SLF001
    assert splitter._total == 0  # noqa: SLF001
    assert len(splitter._current_set) == 0  # noqa: SLF001


def test_directory_splitter_append_set(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    splitter._current_set = ['file1', 'file2']  # noqa: SLF001
    splitter._total = 2048  # noqa: SLF001
    splitter._append_set()  # noqa: SLF001
    assert len(splitter._sets) == 1  # noqa: SLF001
    assert len(splitter._sets[0]) == 2  # noqa: SLF001
