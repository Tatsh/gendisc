from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gendisc.main import genlabel_main, main

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
    mock_logging = mocker.patch('gendisc.main.setup_logging')
    runner.invoke(main, ['test_path', '--debug'])
    mock_logging.assert_called_once_with(debug=True)


def test_main_default_values(runner: CliRunner, mocker: MockerFixture) -> None:
    mocker.patch('gendisc.main.Path.mkdir')
    mocker.patch('gendisc.main.keep.running')
    mock_splitter = mocker.patch('gendisc.main.DirectorySplitter')
    runner.invoke(main, ['test_path'])
    mock_splitter.assert_called_once()
    args, kwargs = mock_splitter.call_args
    assert args[0].name == 'test_path'
    assert args[1] == 'test_path'
    assert kwargs['delete_command'] == 'trash'
    assert kwargs['drive'] == Path('/dev/sr0')
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


def test_genlabel_main_svg_output(runner: CliRunner, mocker: MockerFixture) -> None:
    mock_svg = mocker.patch('gendisc.main.write_spiral_text_svg')
    result = runner.invoke(genlabel_main,
                           ['Hello', 'World', '--svg', '-o', 'label.svg', '-w', '500', '-f', '20'])
    assert result.exit_code == 0
    mock_svg.assert_called_once()
    args = mock_svg.call_args[0]
    assert args[0].name.endswith('.svg')
    assert 'Hello World' in args


def test_genlabel_main_png_output(runner: CliRunner, mocker: MockerFixture) -> None:
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png')
    result = runner.invoke(genlabel_main, ['Test', '-o', 'label.png', '-w', '400', '--dpi', '300'])
    assert result.exit_code == 0
    mock_png.assert_called_once()
    args = mock_png.call_args[0]
    assert args[0].name.endswith('.png')
    assert 'Test' in args


def test_genlabel_main_with_center_and_view_box(runner: CliRunner, mocker: MockerFixture) -> None:
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png')
    result = runner.invoke(genlabel_main, [
        'Centred', '-o', 'centred.png', '-c', '100', '100', '-V', '0', '0', '400', '400', '-w',
        '400'
    ])
    assert result.exit_code == 0
    mock_png.assert_called_once()
    args = mock_png.call_args[0]
    # Check that Point is passed for center
    assert hasattr(args[7], 'x')
    assert hasattr(args[7], 'y')
    # Check that view_box is passed
    assert args[4] == (0, 0, 400, 400)


def test_genlabel_main_keep_svg_flag(runner: CliRunner, mocker: MockerFixture) -> None:
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png')
    runner.invoke(genlabel_main, ['KeepSVG', '-o', 'keep.png', '--keep-svg'])
    mock_png.assert_called_once()
    kwargs = mock_png.call_args.kwargs
    assert kwargs.get('keep') is True


def test_genlabel_main_font_size_and_theta(runner: CliRunner, mocker: MockerFixture) -> None:
    mock_png = mocker.patch('gendisc.main.write_spiral_text_png')
    runner.invoke(genlabel_main, ['FontTest', '-o', 'font.png', '-f', '22', '-t', '45'])
    mock_png.assert_called_once()
    args = mock_png.call_args[0]
    assert args[6] == 22  # font_size
    assert args[12] == 45  # theta_step
