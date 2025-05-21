<!-- markdownlint-disable MD024 -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.4] - 2025-05-18

### Added

- Workaround `os.walk` mistakenly putting directories in the filenames list. This is happening for
  me on Linux with CIFS and the `unix` option enabled (server side has
  `smb3 unix extensions = on`). Report the issue once at warning level.
- Open GIMP to the printer dialogue if it is installed for label printing (unless `-G` is passed to
  the generation script).

### Changed

- When getting directory sizes and path lists, skip directories named `.Trash-*`, `Trash`, and
  `.Trash`.
- Generation script and other files get their own subdirectory in the output directory.
- The generation script now takes many flags to change its behaviour.

### Fixed

- Escape text in SVG generation.
- Keep volume ID <= 32 characters.

## [0.0.3] - 2025-05-18

### Changed

- Changed logging format.

## [0.0.2] - 2025-05-18

### Added

- `genlabel` command.

## [0.0.1] - 2025-05-17

First version.

[unreleased]: https://github.com/Tatsh/gendisc/-/compare/v0.0.4...master
