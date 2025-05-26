<!-- markdownlint-disable MD024 -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

## [0.0.11] - 2025-05-25

### Changed

- Use Jinja to render the script.

### Fixed

- Fix label generation when a prefix is specified.

## [0.0.10] - 2025-05-24

### Changed

- Do not re-create the listing, metadata, or tree files unnecessarily.
- Exit on failure of `cdrecord`.

## [0.0.9] - 2025-05-24

### Changed

- In the script write to files ending in `.__incomplete__` first then move them to the correct name
  after successful completion.

### Fixed

- Fallback to normal piping when `pv` is not installed.

## [0.0.8] - 2025-05-23

### Added

- Added option in script to open GIMP normally instead of directly to the print window.

### Changed

- Use `jq` instead of `prettier` to format JSON files (since `exiftool`'s JSON file is technically
  "ndjson"). Also convert the ndjson file to normal JSON.

### Fixed

- Fixed formatting EXIF data JSON file.

## [0.0.6] - 2025-05-23

## Added

- Add options to add preparer and publisher values to images

## [0.0.5] - 2025-05-22

### Changed

- Use longer volume ID on the disc label.

## [0.0.4] - 2025-05-22

### Added

- Workaround `os.walk` mistakenly putting directories in the filenames list. This is happening for
  me on Linux with CIFS and the `unix` option enabled (server side has
  `smb3 unix extensions = on`). Report the issue once at warning level.
- Open GIMP to the printer dialogue if it is installed for label printing (unless `-G` is passed to
  the generation script).
- Ability to change write speed for individual disc types. Defaults are values intended for use with
  current Verbatim/Ritek printable media and Sony's 128 GB disc (4X).

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

[unreleased]: https://github.com/Tatsh/gendisc/-/compare/v0.0.11...master
