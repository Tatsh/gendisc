from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
import asyncio

from gendisc.main import genlabel_main, main

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def _run_coroutine(coroutine: Any) -> None:
    asyncio.new_event_loop().run_until_complete(coroutine)


def _patch_asyncio_run(mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.asyncio.run', side_effect=_run_coroutine)


def _patch_splitter(mocker: MockerFixture) -> MagicMock:
    splitter_cls = mocker.patch('gendisc.main.DirectorySplitter')
    instance = splitter_cls.return_value
    instance.split = AsyncMock(return_value=None)
    return splitter_cls


def test_main_success(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    _patch_asyncio_run(mocker)
    _patch_splitter(mocker)
    result = runner.invoke(main, ('test_path', '-D', '/dev/sr0', '-o', 'output_dir', '-i', '1'))
    assert result.exit_code == 0


def test_main_debug_logging(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    _patch_asyncio_run(mocker)
    _patch_splitter(mocker)
    mock_logging = mocker.patch('gendisc.main.setup_logging')
    runner.invoke(main, ['test_path', '--debug'])
    mock_logging.assert_called_once_with(debug=True, loggers=mocker.ANY)


def test_main_default_values(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    _patch_asyncio_run(mocker)
    splitter_cls = _patch_splitter(mocker)
    runner.invoke(main, ['test_path'])
    splitter_cls.assert_called_once()
    args, kwargs = splitter_cls.call_args
    assert args[0].name == 'test_path'
    assert args[1] == 'test_path'
    assert kwargs['cross_fs'] is False
    assert kwargs['labels'] is True
    assert kwargs['delete_command'] == 'trash'


def test_main_delete_option(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    _patch_asyncio_run(mocker)
    splitter_cls = _patch_splitter(mocker)
    runner.invoke(main, ['test_path', '--delete'])
    splitter_cls.assert_called_once()
    _args, kwargs = splitter_cls.call_args
    assert kwargs['delete_command'] == 'rm -rf'


def test_genlabel_main_svg_output(runner: CliRunner, mocker: MockerFixture) -> None:
    _patch_asyncio_run(mocker)
    mock_svg = mocker.patch('gendisc.main.write_spiral_text_svg', new_callable=AsyncMock)
    mocker.patch('gendisc.main.write_spiral_text_png', new_callable=AsyncMock)
    result = runner.invoke(genlabel_main,
                           ['Hello', 'World', '--svg', '-o', 'label.svg', '-w', '500', '-f', '20'])
    assert result.exit_code == 0
    mock_svg.assert_awaited_once()
    args = mock_svg.call_args.args
    assert isinstance(args[0], Path)
    assert args[1] == 'Hello World'


def test_genlabel_main_png_output(runner: CliRunner, mocker: MockerFixture) -> None:
    _patch_asyncio_run(mocker)
    mocker.patch('gendisc.main.write_spiral_text_svg', new_callable=AsyncMock)
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png', new_callable=AsyncMock)
    result = runner.invoke(genlabel_main, ['Test', '-o', 'label.png', '-w', '400', '--dpi', '300'])
    assert result.exit_code == 0
    mock_png.assert_awaited_once()
    args = mock_png.call_args.args
    assert args[1] == 'Test'


def test_genlabel_main_with_center_and_view_box(runner: CliRunner, mocker: MockerFixture) -> None:
    _patch_asyncio_run(mocker)
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png', new_callable=AsyncMock)
    result = runner.invoke(genlabel_main, [
        'Centred', '-o', 'centred.png', '-c', '100', '100', '-V', '0', '0', '400', '400', '-w',
        '400'
    ])
    assert result.exit_code == 0
    mock_png.assert_awaited_once()
    args = mock_png.call_args.args
    assert args[4] == (0, 0, 400, 400)
    assert hasattr(args[7], 'x')
    assert hasattr(args[7], 'y')


def test_genlabel_main_keep_svg_flag(runner: CliRunner, mocker: MockerFixture) -> None:
    _patch_asyncio_run(mocker)
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png', new_callable=AsyncMock)
    runner.invoke(genlabel_main, ['KeepSVG', '-o', 'keep.png', '--keep-svg'])
    mock_png.assert_awaited_once()
    assert mock_png.call_args.kwargs.get('keep') is True


def test_genlabel_main_font_size_and_theta(runner: CliRunner, mocker: MockerFixture) -> None:
    _patch_asyncio_run(mocker)
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png', new_callable=AsyncMock)
    runner.invoke(genlabel_main, ['FontTest', '-o', 'font.png', '-f', '22', '-t', '45'])
    mock_png.assert_awaited_once()
    args = mock_png.call_args.args
    assert args[6] == 22
    assert args[12] == 45
