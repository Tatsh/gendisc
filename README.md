# Disc generator

A very specific script for me.

## Installation

```shell
pip install gendisc
```

## Usage

```plain
Usage: gendisc [OPTIONS] PATH

  Make a file listing filling up a disc.

Options:
  -p, --prefix TEXT               [required]
  -i, --starting-index INTEGER
  -d, --debug                     Enable debug logging.
  -o, --output-dir DIRECTORY
  -d, --drive FILE                Drive path.
  -t, --disc-type [bd|bd-dl|bdxl|bd-ql|dvd|dvd-dl]
                                  Disc type (bd = Blu-ray, *dl = dual layer,
                                  *xl = triple layer, *ql = quadruple-layer).
  -h, --help                      Show this message and exit.
```
