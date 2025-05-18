# gendisc

[![Python versions](https://img.shields.io/pypi/pyversions/gendisc.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/gendisc)](https://pypi.org/project/gendisc/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/gendisc)](https://github.com/Tatsh/gendisc/tags)
[![License](https://img.shields.io/github/license/Tatsh/gendisc)](https://github.com/Tatsh/gendisc/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/gendisc/v0.0.2/master)](https://github.com/Tatsh/gendisc/compare/v0.0.2...master)
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
  --cross-fs                  Allow crossing file systems.
  -D, --drive FILE            Drive path.
  -d, --debug                 Enable debug logging.
  -i, --starting-index INDEX  Index to start with (defaults to 1).  [x>=1]
  -o, --output-dir DIRECTORY  Output directory. Will be created if it does not
                              exist.
  -p, --prefix TEXT           Prefix for volume ID and files.
  -r, --delete                Unlink instead of sending to trash.
  -h, --help                  Show this message and exit.
```

The output is a series of shell scripts (1 for each disc) that do the following:

- Generate the ISO image with `mkisofs` for the current set.
- Save a SHA256 sum of the image for verification.
- Save a tree listing for later use (`tree` must be installed).
- Save a file listing via `find` for later use.
- Requests to insert a blank disc.
- Uses `cdrecord` to burn (currently set to burn at 4x speed).
- Ejects and re-inserts the disc.
- Verifies the disc.
- Deletes the source files or sends them to the bin.
- Ejects the disc.
- Requests to move the disc to a label printer.

If you have `mogrify` (ImageMagick) installed, a label will be generated. This can be then opened in
a tool that can ask your printer (such as an Epson XP-7100) to print to disc (GIMP). In GIMP, be
sure to set the _Width_ and _Height_ to 12 cm in _Image Settings_ in the print dialogue before
printing.
