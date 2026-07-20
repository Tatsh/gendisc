from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from gendisc.utils import (
    DirectorySplitter,
    MogrifyLabelPool,
    WriteSpeeds,
    clear_mounts_cache,
    get_dir_size,
    get_disc_type,
    get_mounts,
    is_cross_fs,
    reload_mounts,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from pytest_mock import MockerFixture


@pytest.fixture
def mocker_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('basepath', [], ['file1', 'file2'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_file_size', return_value=1024)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=1024)
    mocker.patch('gendisc.utils.Path')
    mocker.patch('gendisc.utils.AsyncPath')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'dir1\ndir2\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)


def test_get_disc_type() -> None:
    assert get_disc_type(700 * 1024 * 1024) == 'DVD-R'
    assert get_disc_type(int(4.7 * 1024 * 1024 * 1024)) == 'DVD-R DL'
    assert get_disc_type(int(8.5 * 1024 * 1024 * 1024)) == 'BD-R'
    assert get_disc_type(25 * 1024 * 1024 * 1024) == 'BD-R DL'
    assert get_disc_type(50 * 1024 * 1024 * 1024) == 'BD-R XL (100 GB)'
    assert get_disc_type(100 * 1024 * 1024 * 1024) == 'BD-R XL (128 GB)'
    with pytest.raises(ValueError, match=r'Disc size exceeds maximum supported size.'):
        get_disc_type(128 * 1024 * 1024 * 1024)


async def test_get_dir_size_raises_not_a_directory() -> None:
    with pytest.raises(NotADirectoryError):
        await get_dir_size('non-existent-path')


async def test_get_dir_size_returns_correct_size(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a', 'b', 'c'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=2048)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = await get_dir_size('some_dir')
    assert size == 3 * 2048


async def test_get_dir_size_with_progress_counts_via_run_sync(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a', 'b'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mock_progress = MagicMock()
    mock_task = MagicMock()
    mock_progress.add_task.return_value = mock_task

    def fake_run_sync(fn: object, *args: object, **kwargs: object) -> int:
        if getattr(fn, '__name__', '') == '_count_dir_files':
            return 2
        return 1024

    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, side_effect=fake_run_sync)
    size = await get_dir_size('some_dir', progress=mock_progress)
    assert size == 2048
    add_call = mock_progress.add_task.call_args
    assert 'Counting files' in add_call.args[0]
    assert add_call.kwargs['total'] is None
    mock_task.set_bounds.assert_called_once_with(total=2.0,
                                                 description='Calculating size of some_dir')


async def test_get_dir_size_skips_symlinks(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a', 'b'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', side_effect=[False, True, False, True])
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=4096)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = await get_dir_size('dir')
    assert size == 4096


async def test_get_dir_size_handles_oserror(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['z', 'x'])])
    # First isdir check passes for the top-level dir; subsequent checks for files return False,
    # so the OSError path treats it as a regular file and is skipped.
    mocker.patch('gendisc.utils.isdir', side_effect=[True, False, False])
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, side_effect=[OSError, 512])
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = await get_dir_size('dir2')
    assert size == 512


async def test_get_dir_size_reports_buggy_fs_once(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mock_log_warning = mocker.patch('gendisc.utils.log.warning')
    mocker.patch(
        'gendisc.utils.walk',
        side_effect=[[('base', [], ['unique-buggy-a'])], [('base', [], ['unique-buggy-a'])],
                     [('base', [], ['unique-buggy-a'])], [('base', [], ['unique-buggy-a'])]])
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync',
                 new_callable=AsyncMock,
                 side_effect=[OSError, 2048, OSError, 2048])
    await get_dir_size('dir')
    mock_log_warning.assert_called_once_with(
        'Buggy file system (cifs with "unix" option?) reported directory'
        ' `%s` as file.', 'base/unique-buggy-a')
    mock_log_warning.reset_mock()
    await get_dir_size('dir')
    assert mock_log_warning.call_count == 0


async def test_get_dir_size_skips_walk_entries_without_files(mocker: MockerFixture) -> None:
    # A walk entry with no filenames should be skipped entirely.
    mocker.patch('gendisc.utils.walk',
                 return_value=[('base', ['subdir'], []), ('base/subdir', [], ['a'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=2048)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = await get_dir_size('dir')
    assert size == 2048


async def test_get_dir_size_skips_when_all_entries_are_symlinks(mocker: MockerFixture) -> None:
    # When every file in a walk entry is a symlink, the entry should be skipped.
    mocker.patch('gendisc.utils.walk',
                 return_value=[('base', [], ['link1', 'link2']), ('base2', [], ['real'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', side_effect=[True, True, False])
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    size = await get_dir_size('dir')
    assert size == 1024


async def test_get_dir_size_reports_oserror_exception(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.isdir', side_effect=[True, False])
    mock_log_exception = mocker.patch('gendisc.utils.log.exception')
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a'])])
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, side_effect=OSError)
    await get_dir_size('dir')
    mock_log_exception.assert_called_once_with(
        'Caught error getting file size for `%s`. It will not be considered part of the total.',
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
        speeds.get_speed(
            'UNKNOWN-DISC')  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]


async def test_is_cross_fs(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=['/', '/mnt'])
    assert await is_cross_fs('/') is True
    assert await is_cross_fs('/mnt') is True
    assert await is_cross_fs('/home') is False


async def test_get_mounts_reads_and_caches(mocker: MockerFixture) -> None:
    # Ensure the cache is empty so get_mounts has to populate it from the (mocked) file.
    await clear_mounts_cache()
    mock_read_text = AsyncMock(return_value='/dev/sda1 / ext4 rw 0 0\n/dev/sdb1 /mnt ext4 rw 0 0')
    mocker.patch('gendisc.utils.AsyncPath.read_text', mock_read_text)
    mounts = await get_mounts()
    assert mounts == ('/', '/mnt')
    mock_read_text.assert_called_once()
    # Second call should hit the cache: AsyncPath.read_text must not be called again.
    mock_read_text.reset_mock()
    mounts2 = await get_mounts()
    assert mounts2 == ('/', '/mnt')
    mock_read_text.assert_not_called()


async def test_reload_mounts_bypasses_cache(mocker: MockerFixture) -> None:
    # Prime the cache with a value we expect to be replaced.
    mocker.patch('gendisc.utils.AsyncPath.read_text',
                 new_callable=AsyncMock,
                 return_value='/dev/sda1 /old ext4 rw 0 0')
    await reload_mounts()
    mocker.patch('gendisc.utils.AsyncPath.read_text',
                 new_callable=AsyncMock,
                 return_value='/dev/sda1 /new ext4 rw 0 0')
    mounts = await reload_mounts()
    assert mounts == ('/new',)


def test_directory_splitter_sets_is_empty_before_split(mocker_fs: None) -> None:
    splitter = DirectorySplitter('test_path', 'prefix')
    assert splitter.sets == ()


async def test_directory_splitter_split(mocker: MockerFixture, mocker_fs: None) -> None:
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.reset_mock()
    mock_write_text = AsyncMock()
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = mock_write_text
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path',
                                 'prefix-' * 10,
                                 preparer='preparer',
                                 publisher='publisher')
    await splitter.split()
    assert len(splitter.sets) == 1
    assert len(splitter.sets[0]) == 1
    shell = mock_write_text.call_args_list[1].args[0]
    assert 'VOLID=prefix-prefix-prefix-prefix-p-01' in shell
    assert '-preparer preparer -publisher publisher' in shell


async def test_directory_splitter_uses_drive_and_starting_index(mocker: MockerFixture,
                                                                mocker_fs: None) -> None:
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_write_text = AsyncMock()
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = mock_write_text
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix', drive='/dev/custom-drive', starting_index=7)
    await splitter.split()
    assert len(splitter.sets) == 1
    shell = mock_write_text.call_args_list[1].args[0]
    # starting_index=7 shows up as -07 in the volume ID.
    assert 'VOLID=prefix-07' in shell
    # The configured drive should be referenced in the generated shell script.
    assert 'DRIVE=/dev/custom-drive' in shell


async def test_directory_splitter_delete_command_in_shell(mocker: MockerFixture,
                                                          mocker_fs: None) -> None:
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_write_text = AsyncMock()
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = mock_write_text
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix', delete_command='rm -rf')
    await splitter.split()
    shell = mock_write_text.call_args_list[1].args[0]
    assert 'rm -rf' in shell


async def test_directory_splitter_split_skips_cross_fs(mocker: MockerFixture,
                                                       mocker_fs: None) -> None:
    mock_write_spiral = mocker.patch('gendisc.utils.write_spiral_text_png', new_callable=AsyncMock)
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\ndir1\ndir2\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['file1'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mocker.patch('gendisc.utils.is_cross_fs',
                 new_callable=AsyncMock,
                 side_effect=lambda d: d == 'dir2')
    splitter = DirectorySplitter('test_path', 'prefix', labels=True)
    await splitter.split()
    assert len(splitter.sets) == 1
    assert all('dir1' in entry for entry in splitter.sets[0])
    assert all('dir2' not in entry for entry in splitter.sets[0])
    mock_write_spiral.assert_called_once()


async def test_directory_splitter_label_submits_to_mogrify_pool(mocker: MockerFixture) -> None:
    mock_write_spiral = mocker.patch('gendisc.utils.write_spiral_text_png', new_callable=AsyncMock)
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\ndir1\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['file1'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    mocker.patch('gendisc.utils.Path')

    async def status_run(message: str, awaitable: Awaitable[Any]) -> Any:
        return await awaitable

    mock_status = MagicMock()
    mock_status.run = AsyncMock(side_effect=status_run)
    pool = MogrifyLabelPool(worker_count=2)
    await pool.start()
    splitter = DirectorySplitter('test_path',
                                 'prefix',
                                 labels=True,
                                 mogrify_pool=pool,
                                 status_run=mock_status)
    await splitter.split()
    await pool.wait_until_finished()
    mock_write_spiral.assert_awaited_once()


async def test_mogrify_label_pool_drains_queue(mocker: MockerFixture) -> None:
    mock_write = mocker.patch('gendisc.utils.write_spiral_text_png', new_callable=AsyncMock)
    pool = MogrifyLabelPool(worker_count=2)
    await pool.start()
    await pool.submit('out/label-a.png', 't1', fn_prefix='p-001')
    await pool.submit('out/label-b.png', 't2', fn_prefix='p-002')
    await pool.wait_until_finished()
    assert mock_write.await_count == 2


async def test_mogrify_label_pool_wait_without_start_raises() -> None:
    pool = MogrifyLabelPool()
    with pytest.raises(ValueError, match='start'):
        await pool.wait_until_finished()


async def test_get_dir_size_with_progress_calls_count_dir_files(mocker: MockerFixture) -> None:
    import gendisc.utils as utils_mod

    count_fn = utils_mod._count_dir_files  # ruff:ignore[private-member-access]

    def run_sync_side_effect(fn: object, *args: object, **_kwargs: object) -> int:
        if fn is count_fn:
            return int(count_fn(str(args[0])))
        return 2048

    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, side_effect=run_sync_side_effect)
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['a'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mock_progress = MagicMock()
    mock_task = MagicMock()
    mock_progress.add_task.return_value = mock_task
    size = await get_dir_size('some_dir', progress=mock_progress)
    assert size == 2048


async def test_mogrify_label_pool_second_start_does_not_add_workers(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.utils.write_spiral_text_png', new_callable=AsyncMock)
    pool = MogrifyLabelPool(2)
    await pool.start()
    workers_after_first = list(pool._workers)  # ruff:ignore[private-member-access]
    await pool.start()
    assert pool._workers == workers_after_first  # ruff:ignore[private-member-access]
    await pool.submit('out/label-once.png', 't', fn_prefix='p-001')
    await pool.wait_until_finished()


async def test_mogrify_label_pool_raises_on_invalid_queue_item() -> None:
    pool = MogrifyLabelPool(worker_count=1)
    await pool.start()
    await pool._queue.put(object())  # ruff:ignore[private-member-access]
    with pytest.raises(TypeError, match='Unexpected item on mogrify queue'):
        await pool.wait_until_finished()


async def test_directory_splitter_label_status_run_without_mogrify_pool(
        mocker: MockerFixture) -> None:
    mock_write_spiral = mocker.patch('gendisc.utils.write_spiral_text_png', new_callable=AsyncMock)
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\ndir1\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], ['file1'])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, return_value=1024)
    mocker.patch('gendisc.utils.path_join', side_effect=lambda base, f: f'{base}/{f}')
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    mocker.patch('gendisc.utils.Path')

    async def status_run(message: str, awaitable: Awaitable[Any]) -> Any:
        return await awaitable

    mock_status = MagicMock()
    mock_status.run = AsyncMock(side_effect=status_run)
    splitter = DirectorySplitter('test_path',
                                 'prefix',
                                 labels=True,
                                 mogrify_pool=None,
                                 status_run=mock_status)
    await splitter.split()
    mock_write_spiral.assert_awaited_once()
    run_messages = [str(c[0][0]) for c in mock_status.run.call_args_list if c[0]]
    assert any('mogrify' in m for m in run_messages)


async def test_directory_splitter_split_file_too_large_for_bluray(mocker: MockerFixture,
                                                                  mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\nfile1\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 new_callable=AsyncMock,
                 side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.run_sync',
                 new_callable=AsyncMock,
                 return_value=200 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix')
    await splitter.split()
    assert len(splitter.sets) == 0


async def test_directory_splitter_split_file_too_large_for_bluray_already_xl(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\nfile1\nfile2\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 new_callable=AsyncMock,
                 side_effect=[101 * 1024 * 1024 * 1024, 101 * 1024 * 1024 * 1024])
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix')
    await splitter.split()
    assert len(splitter.sets) == 2


async def test_directory_splitter_split_file_too_large_for_bluray_tl_but_not_xl(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\nfile1\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 new_callable=AsyncMock,
                 side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.run_sync',
                 new_callable=AsyncMock,
                 return_value=100 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix')
    await splitter.split()
    assert len(splitter.sets) == 1


async def test_directory_splitter_split_file_too_large_for_split_dir_separately(
        mocker: MockerFixture, mocker_fs: None) -> None:
    mock_log_debug = mocker.patch('gendisc.utils.log.debug')
    mocker.patch('gendisc.utils.shutil.which')
    first_proc = MagicMock()
    first_proc.communicate = AsyncMock(return_value=(b'.\nfile1\n', b''))
    first_proc.returncode = 0
    second_proc = MagicMock()
    second_proc.communicate = AsyncMock(return_value=(b'.\n', b''))
    second_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 side_effect=[first_proc, second_proc])
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 new_callable=AsyncMock,
                 return_value=122 * 1024 * 1024 * 1024)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix')
    await splitter.split()
    assert len(splitter.sets) == 0
    mock_log_debug.assert_has_calls(
        [mocker.call('Directory `%s` too large for Blu-ray. Splitting separately.', 'file1')])


async def test_directory_splitter_skip_files_that_raise_oserror(mocker: MockerFixture,
                                                                mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which', return_value='fake-mogrify')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\ndir_big\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mocker.patch('gendisc.utils.get_dir_size',
                 new_callable=AsyncMock,
                 side_effect=NotADirectoryError)
    mocker.patch('gendisc.utils.run_sync', new_callable=AsyncMock, side_effect=OSError)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix', labels=True)
    await splitter.split()
    # An entry whose size cannot be determined is skipped entirely, so no set is produced.
    assert splitter.sets == ()


async def test_directory_splitter_find_nonzero_exit_raises(mocker: MockerFixture,
                                                           mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b'find: bad argument'))
    mock_proc.returncode = 1
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    splitter = DirectorySplitter('test_path', 'prefix')
    with pytest.raises(RuntimeError, match=r'find exited with code 1'):
        await splitter.split()


async def test_directory_splitter_size_of_uses_cache_on_repeat(mocker: MockerFixture,
                                                               mocker_fs: None) -> None:
    mocker.patch('gendisc.utils.shutil.which')
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b'.\nshared-dir\n', b''))
    mock_proc.returncode = 0
    mocker.patch('gendisc.utils.asyncio.create_subprocess_exec',
                 new_callable=AsyncMock,
                 return_value=mock_proc)
    mock_async_path = mocker.patch('gendisc.utils.AsyncPath')
    mock_async_path.return_value.resolve = AsyncMock(return_value=mock_async_path.return_value)
    (mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.write_text
     ) = AsyncMock()
    mock_async_path.return_value.__truediv__.return_value.__truediv__.return_value.chmod = (
        AsyncMock())
    mock_async_path.return_value.__truediv__.return_value.mkdir = AsyncMock()
    mocker.patch('gendisc.utils.walk', return_value=[('base', [], [])])
    mocker.patch('gendisc.utils.isdir', return_value=True)
    mocker.patch('gendisc.utils.islink', return_value=False)
    mock_get_dir_size = mocker.patch('gendisc.utils.get_dir_size',
                                     new_callable=AsyncMock,
                                     return_value=1024)
    mocker.patch('gendisc.utils.get_mounts', new_callable=AsyncMock, return_value=[])
    splitter = DirectorySplitter('test_path', 'prefix')
    await splitter.split()
    await splitter.split()
    # The second call should reuse the cached size rather than re-computing it.
    assert mock_get_dir_size.call_count == 1
