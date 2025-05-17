gendisc
=======

.. |python-versions| image:: https://img.shields.io/pypi/pyversions/gendisc.svg?color=blue&logo=python&logoColor=white
   :target: https://www.python.org/
   :alt: Python versions

.. |pypi-version| image:: https://img.shields.io/pypi/v/gendisc
   :target: https://pypi.org/project/gendisc/
   :alt: PyPI - Version

.. |github-tag| image:: https://img.shields.io/github/v/tag/Tatsh/gendisc
   :target: https://github.com/Tatsh/gendisc/tags
   :alt: GitHub tag (with filter)

.. |license| image:: https://img.shields.io/github/license/Tatsh/gendisc
   :target: https://github.com/Tatsh/gendisc/blob/master/LICENSE.txt
   :alt: License

.. |commits-since| image:: https://img.shields.io/github/commits-since/Tatsh/gendisc/v0.0.0/master
   :target: https://github.com/Tatsh/gendisc/compare/v0.0.0...master
   :alt: GitHub commits since latest release

.. |qa| image:: https://github.com/Tatsh/gendisc/actions/workflows/qa.yml/badge.svg
   :target: https://github.com/Tatsh/gendisc/actions/workflows/qa.yml
   :alt: QA

.. |tests| image:: https://github.com/Tatsh/gendisc/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/Tatsh/gendisc/actions/workflows/tests.yml
   :alt: Tests

.. |coverage| image:: https://coveralls.io/repos/github/Tatsh/gendisc/badge.svg?branch=master
   :target: https://coveralls.io/github/Tatsh/gendisc?branch=master
   :alt: Coverage Status

.. |docs| image:: https://readthedocs.org/projects/gendisc/badge/?version=latest
   :target: https://gendisc.readthedocs.org/?badge=latest
   :alt: Documentation Status

.. |mypy| image:: https://www.mypy-lang.org/static/mypy_badge.svg
   :target: http://mypy-lang.org/
   :alt: mypy

.. |pre-commit| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit

.. |pydocstyle| image:: https://img.shields.io/badge/pydocstyle-enabled-AD4CD3
   :target: http://www.pydocstyle.org/en/stable/
   :alt: pydocstyle

.. |pytest| image:: https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black
   :target: https://docs.pytest.org/en/stable/
   :alt: pytest

.. |ruff| image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff

.. |downloads| image:: https://static.pepy.tech/badge/gendisc/month
   :target: https://pepy.tech/project/gendisc
   :alt: Downloads

.. |stargazers| image:: https://img.shields.io/github/stars/Tatsh/gendisc?logo=github&style=flat
   :target: https://github.com/Tatsh/gendisc/stargazers
   :alt: Stargazers

.. |bsky| image:: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor%3Ddid%3Aplc%3Auq42idtvuccnmtl57nsucz72%26query%3D%24.followersCount%26style%3Dsocial%26logo%3Dbluesky%26label%3DFollow%2520%40Tatsh&query=%24.followersCount&style=social&logo=bluesky&label=Follow%20%40Tatsh
   :target: https://bsky.app/profile/Tatsh.bsky.social
   :alt: Follow @Tatsh on Bluesky

.. |mastodon| image:: https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social
   :target: https://hostux.social/@Tatsh
   :alt: Mastodon Follow

|python-versions| |pypi-version| |github-tag| |license| |commits-since| |qa| |tests| |coverage| |docs| |mypy| |pre-commit| |pydocstyle| |pytest| |ruff| |downloads| |stargazers| |bsky| |mastodon|

Generate scripts to create disc ISOs from a directory structure maximising use of the available
space on each disc.

Commands
--------

.. click:: gendisc.main:main
  :prog: gendisc
  :nested: full

.. only:: html

   Library
   -------

   .. automodule:: gendisc
      :members:

   .. automodule:: gendisc.utils
      :exclude-members: DirectorySplitter, write_spiral_svg
      :members:

   Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
