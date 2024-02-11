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

    def _section_comment(self, text: str) -> None:
        columns = 80
        line = "/************** " + text + " "
        remainder = columns - len(line) - len("*/")
        if remainder > 0:
            line += "*" * remainder
        line += "*/\n"
        self._outfp.write(line)

    def _comment_line(self, line: str) -> None:
        """Wraps the line in a comment and writes it.

        Handles simple cases of block comment markers "/*" and "*/" appearing on
        the line, but does not handle the case where a block comment begins/ends
        on this line and ends/begins on a different line.
        """
        escaped_line = line.replace("/*", "|*").replace("*/", "*|")
        self._outfp.write(f"/* {escaped_line} */\n")

    def _write_line(self, src: SourcePath, line: str, lineno: int):
        match = re.match(r'^\s*#\s*include\s*(<([^>]*)>|"([^"]*)")', line)
        if match:
            # This is a `#include` line.
            include = match.group(2) or match.group(3)
            if include in self._includes_to_paths:
                header = self._includes_to_paths[include]
                if header.abs in self._seen_includes:
                    self._comment_line(line)
                else:
                    # Use the absolute path as an unambiguous way to refer to a
                    # specific file, since it could be included using different
                    # relative paths.
                    self._seen_includes.add(header.abs)
                    self._section_comment(f"Include {header.rel} in the middle of {src.rel}")
                    self.write_file(header)
                    self._section_comment(f"Continuing where we left off in {src.rel}")
                    if self._line_macros:
                        self._outfp.write(f"#line {lineno+1} \"{src.rel}\"\n")
            else:
                # Probably a system header. We want to print the `#include`
                # the first time we see it, then skip all future instances.
                # Use a special prefix to make it less likely to alias to
                # real includes.
                include_key = f"$//{include}"
                if include_key in self._seen_includes:
                    self._comment_line(line)
                else:
                    self._seen_includes.add(include_key)
                    self._outfp.write(line + "\n")
        else:
            # TODO: Remove #pragma once if this is a .cpp file

            # This is not a `#include` line.
            self._outfp.write(line + "\n")

    def write_file(self, src: SourcePath) -> None:
        # TODO: Print a less awkward path for generated headers
        self._section_comment(f"Begin file {src.rel}")
        if self._line_macros:
            self._outfp.write(f"#line 1 \"{src.rel}\"\n")

        with open(src.abs, "r") as infp:
            lineno: int = 0
            for line in infp:
                lineno += 1
                self._write_line(src=src, line=line.rstrip("\r\n"), lineno=lineno)

        self._section_comment(f"End of {src.rel}")


def amalgamate_sources(outfp: TextIO, root: Path, srcs: list[str], includes_to_paths: dict[str, str], line_macros: bool = False) -> None:
    # Write the contents of each source file into the output, expanding each
    # `#include` only the first time it's seen.
    writer = _SourceWriter(outfp=outfp, root=root, includes_to_paths=includes_to_paths, line_macros=line_macros)
    for src in srcs:
        writer.write_file(SourcePath(root=root, src=src))


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