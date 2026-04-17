gendisc
=======

.. include:: badges.rst

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

   .. automodule:: gendisc.genlabel
      :members:

   .. automodule:: gendisc.typing
      :members:

   .. automodule:: gendisc.utils
      :members:

   Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
