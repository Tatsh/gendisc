gendisc
=======

.. only:: html

   .. image:: https://img.shields.io/pypi/pyversions/gendisc.svg?color=blue&logo=python&logoColor=white
      :target: https://www.python.org/
      :alt: Python versions

   .. image:: https://img.shields.io/pypi/v/gendisc
      :target: https://pypi.org/project/gendisc/
      :alt: PyPI - Version

   .. image:: https://img.shields.io/github/v/tag/Tatsh/gendisc
      :target: https://github.com/Tatsh/gendisc/tags
      :alt: GitHub tag (with filter)

   .. image:: https://img.shields.io/github/license/Tatsh/gendisc
      :target: https://github.com/Tatsh/gendisc/blob/master/LICENSE.txt
      :alt: License

   .. image:: https://img.shields.io/github/commits-since/Tatsh/gendisc/v0.0.12/master
      :target: https://github.com/Tatsh/gendisc/compare/v0.0.12...master
      :alt: GitHub commits since latest release

   .. image:: https://github.com/Tatsh/gendisc/actions/workflows/qa.yml/badge.svg
      :target: https://github.com/Tatsh/gendisc/actions/workflows/qa.yml
      :alt: QA

   .. image:: https://github.com/Tatsh/gendisc/actions/workflows/tests.yml/badge.svg
      :target: https://github.com/Tatsh/gendisc/actions/workflows/tests.yml
      :alt: Tests

   .. image:: https://coveralls.io/repos/github/Tatsh/gendisc/badge.svg?branch=master
      :target: https://coveralls.io/github/Tatsh/gendisc?branch=master
      :alt: Coverage Status

   .. image:: https://readthedocs.org/projects/gendisc/badge/?version=latest
      :target: https://gendisc.readthedocs.org/?badge=latest
      :alt: Documentation Status

   .. image:: https://www.mypy-lang.org/static/mypy_badge.svg
      :target: http://mypy-lang.org/
      :alt: mypy

   .. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
      :target: https://github.com/pre-commit/pre-commit
      :alt: pre-commit

   .. image:: https://img.shields.io/badge/pydocstyle-enabled-AD4CD3
      :target: http://www.pydocstyle.org/en/stable/
      :alt: pydocstyle

   .. image:: https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black
      :target: https://docs.pytest.org/en/stable/
      :alt: pytest

   .. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
      :target: https://github.com/astral-sh/ruff
      :alt: Ruff

   .. image:: https://static.pepy.tech/badge/gendisc/month
      :target: https://pepy.tech/project/gendisc
      :alt: Downloads

   .. image:: https://img.shields.io/github/stars/Tatsh/gendisc?logo=github&style=flat
      :target: https://github.com/Tatsh/gendisc/stargazers
      :alt: Stargazers

   .. image:: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Ddid%3Aplc%3Auq42idtvuccnmtl57nsucz72%26query%3D%24.followersCount%26style%3Dsocial%26logo%3Dbluesky%26label%3DFollow%2520%40Tatsh&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40Tatsh
      :target: https://bsky.app/profile/Tatsh.bsky.social
      :alt: Follow @Tatsh on Bluesky

   .. image:: https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social
      :target: https://hostux.social/@Tatsh
      :alt: Mastodon Follow

This tool generates scripts to create disc ISOs from a directory structure maximising use of the
available space on each disc. This is useful for creating backups of large amounts of data that do
not fit on a single disc. Directories whose capacity is larger than a single disc are split into
multiple discs.

Commands
--------

.. click:: gendisc.main:main
  :prog: gendisc
  :nested: full

Output
^^^^^^

The output consists of a series of shell scripts (1 for each disc) that perform the following steps:

- Generate the ISO image for the current set using ``mkisofs``.
- Save a SHA256 checksum of the image for verification.
- Save a directory tree listing (requires ``tree``).
- Save a file listing using ``find``.
- Prompt to insert a blank disc. It will tell you the kind of disc to use.
- Burn the image to disc using ``cdrecord``.
- Eject and re-insert the disc.
- Verify the disc.
- Delete or move the source files to the bin.
- Eject the disc.
- Prompt to move the disc to a label printer.
- Open GIMP if you have it installed to the printer dialogue.

If you have `mogrify` (ImageMagick) and Inkscape installed, a label will be generated. This label
can be opened in a tool that supports disc printing (such as GIMP). The image should be ready for
printing (under `Image Settings` you should see it is exactly 12 cm at DPI 600).

Many of the steps above can be skipped by passing flags to the script. Currently the script supports
these options:

.. code-block:: text

   Usage: script.sh [-h] [-G] [-K] [-k] [-O] [-P] [-s] [-S] [-V]
   All flags default to no.
     -h: Show this help message.
     -G: Do not open GIMP on completion (if label file exists).
     -K: Keep ISO image after burning.
     -O: Only create ISO image.
     -P: Open GIMP in normal mode instead of batch mode.
     -S: Skip ejecting tray for blank disc (assume already inserted).
     -V: Skip verification of burnt disc.
     -k: Keep source files after burning.
     -s: Skip clean-up of .directory files.

Label generation
----------------

.. click:: gendisc.main:genlabel_main
  :prog: genlabel
  :nested: full

.. only:: html

   Library
   -------

   .. automodule:: gendisc
      :members:

   .. automodule:: gendisc.genlabel
      :exclude-members: MogrifyNotFound, Point, write_spiral_text_png, write_spiral_text_svg
      :members:

   .. automodule:: gendisc.utils
      :exclude-members: DirectorySplitter
      :members:

   Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
