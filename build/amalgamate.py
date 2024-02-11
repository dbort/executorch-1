#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import logging
import os
import re
import sys

from pathlib import Path
from typing import Optional, TextIO

# https://sqlite.org/amalgamation.html
# https://www3.sqlite.org/src/file?name=tool/mksqlite3c.tcl&ci=trunk

"""
for .cpp:
- input cpp files, in order
- import mapping to use to find headers while building .cpp
    - mark certain includes as pass-through: e.g. stdlib

for .h:
- public .h files to use as root
- import mapping for transitive includes
- add pragma once at top

will need to remove the "pragma once" lines
"""

COLUMNS: int = 80

class SourcePath:
    def __init__(self, root: Path, src: str):
        if not os.path.isabs(src):
            # Ensure the path is absolute.
            src = os.path.join(root, src)

        self.root = root
        # Canonicalize the absolute path.
        self.abs = os.path.abspath(src)
        # Will contain ".." components if it doesn't live under root.
        self.rel = os.path.relpath(self.abs, root)


def section_comment(outfp: TextIO, text: str) -> None:
    global COLUMNS
    line = "/************** " + text + " "
    remainder = COLUMNS - len(line) - 2
    if remainder > 0:
        line += "*" * remainder
    line += "*/\n"
    outfp.write(line)


class _SourceWriter:
    def __init__(self, outfp: TextIO, root: Path, includes_to_paths: dict[str, str], line_macros: bool = False):
        # Immutable attributes.
        self._outfp = outfp
        # Convert keys to SourcePath entries to simplify the main loop.
        self._includes_to_paths = {k: SourcePath(root, v) for k, v in includes_to_paths.items()}
        self._line_macros = line_macros

        # Mutable attributes.
        # Set of include paths that have already been expanded.
        self._seen_includes: set[str] = set()

    def write(self, src: SourcePath) -> None:
        section_comment(self._outfp, f"Begin file {src.rel}")
        if self._line_macros:
            self._outfp.write("#line 1 " + src.rel + "\n")

        with open(src.abs, "r") as infp:
            for line in infp:
                line = line.rstrip("\r\n")
                match = re.match(r'^\s*#\s*include\s*(<([^>]*)>|"([^"]*)")', line)
                if match:
                    include = match.group(2) or match.group(3)
                    if include in self._includes_to_paths:
                        header_path = self._includes_to_paths[include].abs
                        if header_path in self._seen_includes:
                            self._outfp.write(f">>> skipping seen include {include}\n")
                        else:
                            self._outfp.write(f">>> new include {include} -> {header_path}\n")
                            self._seen_includes.add(header_path)
                    else:
                        self._outfp.write(f">>> unhandled include {include}\n")

        section_comment(self._outfp, f"End of {src.rel}")


def amalgamate_sources(outfp: TextIO, root: Path, srcs: list[str], includes_to_paths: dict[str, str], line_macros: bool = False) -> None:
    # Write the contents of each source file into the output, expanding each
    # `#include` only the first time it's seen.
    writer = _SourceWriter(outfp=outfp, root=root, includes_to_paths=includes_to_paths, line_macros=line_macros)
    for src in srcs:
        writer.write(SourcePath(root=root, src=src))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combines .cpp and .h files into a smaller number of files",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pass


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    main()