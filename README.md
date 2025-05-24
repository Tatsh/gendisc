# gendisc

[![Python versions](https://img.shields.io/pypi/pyversions/gendisc.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/gendisc)](https://pypi.org/project/gendisc/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/gendisc)](https://github.com/Tatsh/gendisc/tags)
[![License](https://img.shields.io/github/license/Tatsh/gendisc)](https://github.com/Tatsh/gendisc/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/gendisc/v0.0.9/master)](https://github.com/Tatsh/gendisc/compare/v0.0.9...master)
[![QA](https://github.com/Tatsh/gendisc/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/gendisc/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/gendisc/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/gendisc/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/gendisc/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/gendisc?branch=master)
[![Documentation Status](https://readthedocs.org/projects/gendisc/badge/?version=latest)](https://gendisc.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![pydocstyle](https://img.shields.io/badge/pydocstyle-enabled-AD4CD3)](http://www.pydocstyle.org/en/stable/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/gendisc/month)](https://pepy.tech/project/gendisc)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/gendisc?logo=github&style=flat)](https://github.com/Tatsh/gendisc/stargazers)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Ddid%3Aplc%3Auq42idtvuccnmtl57nsucz72%26query%3D%24.followersCount%26style%3Dsocial%26logo%3Dbluesky%26label%3DFollow%2520%40Tatsh&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40Tatsh)](https://bsky.app/profile/Tatsh.bsky.social)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)

Generate disk file paths for mkisofs that fit on certain size discs.

## Installation

### Poetry

```shell
poetry add gendisc
```

### Pip

```shell
pip install gendisc
```

## Usage

```plain
Usage: gendisc [OPTIONS] PATH

  Make a file listing filling up discs.

Options:
  --cross-fs                   Allow crossing file systems.
  -D, --drive FILE             Drive path.
  -d, --debug                  Enable debug logging.
  -i, --starting-index INDEX   Index to start with (defaults to 1).  [x>=1]
  -o, --output-dir DIRECTORY   Output directory. Will be created if it does
                               not exist.
  -p, --prefix TEXT            Prefix for volume ID and files.
  -r, --delete                 Unlink instead of sending to trash.
  --no-labels                  Do not create labels.
  --cd-write-speed INTEGER     CD-R write speed.
  --dvd-write-speed INTEGER    DVD-R write speed.
  --dvd-dl-write-speed FLOAT   DVD-R DL write speed.
  --bd-write-speed INTEGER     BD-R write speed.
  --bd-dl-write-speed INTEGER  BD-R DL write speed.
  --bd-tl-write-speed INTEGER  BD-R TL write speed.
  --bd-xl-write-speed INTEGER  BD-R XL write speed.
  --preparer TEXT              Preparer string (128 characters).
  --publisher TEXT             Publisher string (128 characters).
  -h, --help                   Show this message and exit.
```

The output is a series of shell scripts (1 for each disc) that do the following:

- Generate the ISO image with `mkisofs` for the current set.
- Save a SHA256 sum of the image for verification.
- Save a tree listing for later use (`tree` must be installed).
- Save a file listing via `find` for later use.
- Requests to insert a blank disc.
- Uses `cdrecord` to burn.
- Ejects and re-inserts the disc.
- Verifies the disc.
- Deletes the source files or sends them to the bin.
- Ejects the disc.
- Requests to move the disc to a label printer.
- If you have GIMP installed, open it to the printer dialogue.

If you have `mogrify` (ImageMagick) and Inkscape installed, a label will be generated. This can be
then opened in a tool that can have your printer (such as an Epson XP-7100) print to disc (GIMP).
The image should be ready for printing (under `Image Settings` you should see it is exactly 12 cm at
DPI 600).

Many of the steps above can be skipped by passing flags to the script. Currently the script supports
these options:

```plain
Usage: script.sh [-h] [-G] [-K] [-k] [-O] [-s] [-S] [-V]
All flags default to no.
  -h: Show this help message.
  -G: Do not open GIMP on completion (if label file exists).
  -K: Keep ISO image after burning.
  -k: Keep source files after burning.
  -O: Only create ISO image.
  -s: Skip clean-up of .directory files.
  -S: Skip ejecting tray for blank disc (assume already inserted).
  -V: Skip verification of burnt disc.
```
