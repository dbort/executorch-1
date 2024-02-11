#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import logging
import os
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


def amalgamate_sources(outfp: TextIO, root: Path, srcs: list[str], includes_to_paths: dict[str, str], header: Optional[str]) -> None:
    """Combines the sources, writing the output to an open file.

    Args:
        outfp: The file object to write to.
        root: Prefix to use for relative paths.
        srcs: The list of paths of the source files to combine, in order.
        includes_to_paths: A mapping of #include paths to the filesystem paths
            that should be loaded in their places.
        header: Optional multi-line string to add to the top of the file.
    """
    if header:
        outfp.write(header)
        outfp.write("\n")

    seen_includes: set[str] = set()
    for src in srcs:
        source_path = SourcePath(root=root, src=src)
        section_comment(outfp, f"Begin file {source_path.rel}")
        section_comment(outfp, f"End of {source_path.rel}")


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