from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import logging

from gendisc.main import main

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_main_success(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    mocker.patch('gendisc.main.DirectorySplitter')
    result = runner.invoke(main, ('test_path', '-D', '/dev/sr0', '-o', 'output_dir', '-i', '1'))
    assert result.exit_code == 0


def test_main_debug_logging(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    mocker.patch('gendisc.main.DirectorySplitter')
    mock_logging = mocker.patch('gendisc.main.logging.basicConfig')
    runner.invoke(main, ['test_path', '--debug'])
    mock_logging.assert_called_once_with(level=logging.DEBUG)


def test_main_default_values(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    mock_splitter = mocker.patch('gendisc.main.DirectorySplitter')
    runner.invoke(main, ['test_path'])
    mock_splitter.assert_called_once()
    args, kwargs = mock_splitter.call_args
    assert args[0] == 'test_path'
    assert args[1] == 'test_path'
    assert kwargs['delete_command'] == 'trash'
    assert kwargs['drive'] == '/dev/sr0'
    assert kwargs['output_dir'] == Path.cwd()
    assert kwargs['cross_fs'] is False
    assert kwargs['labels'] is True


def test_main_delete_option(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    mock_splitter = mocker.patch('gendisc.main.DirectorySplitter')
    runner.invoke(main, ['test_path', '--delete'])
    mock_splitter.assert_called_once()
    _args, kwargs = mock_splitter.call_args
    assert kwargs['delete_command'] == 'rm -rf'
