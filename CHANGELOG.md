<!-- markdownlint-disable MD024 -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

## [0.1.1] - 2026-05-08

### Changed

- `gendisc.utils.DirectorySplitter.sets` now returns
  `tuple[tuple[str, ...], ...]` instead of `list[list[str]]`, so the property no longer exposes the
  splitter's internal state to mutation.
- `gendisc.utils.get_mounts` and `gendisc.utils.reload_mounts` now return `tuple[str, ...]`
  instead of `list[str]` and the underlying mount cache is stored as a tuple, preventing callers
  from mutating the cached value.

## [0.1.0] - 2026-04-17

### Added

- New public API:
  - `gendisc.genlabel.line_intersection` (promoted from the private `_line_intersection` helper).
  - `gendisc.utils.get_mounts`, `gendisc.utils.reload_mounts`, and
    `gendisc.utils.clear_mounts_cache` for inspecting and managing the cached mount table.
  - Read-only `sets` property on `gendisc.utils.DirectorySplitter` exposing the split result.
  - `gendisc.utils.MogrifyLabelPool` queues disc label rasterisation (`mogrify`) across concurrent
    workers; the main CLI waits for the pool to drain before exiting.
  - `gendisc.typing` with progress and status protocols for static typing.

### Changed

- Public API is now asynchronous. The following are now `async` coroutines and must be awaited:
  - `gendisc.genlabel.write_spiral_text_svg` and `gendisc.genlabel.write_spiral_text_png`.
  - `gendisc.utils.DirectorySplitter.split`.
  - `gendisc.utils.get_dir_size`.
  - `gendisc.utils.is_cross_fs`.
- The `gendisc` and `gendisc-genlabel` CLI entry points remain synchronous but now size
  directories concurrently via `asyncio.gather` with a bounded semaphore.
- Progress reporting switched from `tqdm` to `rich.progress`.
- Main `gendisc` CLI prints a short `Scanning …` line before work begins (non-debug runs).
- `gendisc.utils.get_dir_size` can show progress while counting files on large trees without
  blocking the asyncio event loop.
- `gendisc` and `gendisc-genlabel` print clear messages on `Ctrl+C`, warn if interrupted again
  during shutdown, and exit with status 130.

### Removed

- `gendisc.utils.LazyMounts` (replaced by `get_mounts` / `reload_mounts` /
  `clear_mounts_cache`).

### Fixed

- Fix label generation producing incorrect common path prefix by replacing `os.path.commonprefix`
  (character-based) with `os.path.commonpath` (path-aware) in `DirectorySplitter`.
- The buggy-filesystem warning for CIFS mounts with the `unix` option now fires once per unique
  path instead of once per process.

## [0.0.14] - 2025-05-26

### Changed

- Switch to Jinja for rendering the SVG.

### Fixed

- Label: fix prefix removal to only count paths towards the prefix (everything before the first `/`).

## [0.0.13] - 2025-05-26

### Changed

- Use Jinja to render the GIMP script.

### Fixed

- Fix prefix removal on label when only 1 path is in the path list

## [0.0.12] - 2025-05-25

### Fixed

- Fix label generation when a prefix is specified (again).

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

[unreleased]: https://github.com/Tatsh/gendisc/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Tatsh/gendisc/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Tatsh/gendisc/compare/v0.0.14...v0.1.0
[0.0.14]: https://github.com/Tatsh/gendisc/compare/v0.0.13...v0.0.14
[0.0.13]: https://github.com/Tatsh/gendisc/compare/v0.0.12...v0.0.13
[0.0.12]: https://github.com/Tatsh/gendisc/compare/v0.0.11...v0.0.12
[0.0.11]: https://github.com/Tatsh/gendisc/compare/v0.0.10...v0.0.11
[0.0.10]: https://github.com/Tatsh/gendisc/compare/v0.0.9...v0.0.10
[0.0.9]: https://github.com/Tatsh/gendisc/compare/v0.0.8...v0.0.9
[0.0.8]: https://github.com/Tatsh/gendisc/compare/v0.0.6...v0.0.8
[0.0.6]: https://github.com/Tatsh/gendisc/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/Tatsh/gendisc/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/Tatsh/gendisc/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/Tatsh/gendisc/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/Tatsh/gendisc/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/Tatsh/gendisc/releases/tag/v0.0.1
