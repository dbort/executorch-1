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

from amalgamate import amalgamate_sources
from extract_sources import query_targets_to_srcs, Buck2Runner

# extract_sources config to get the source files to combine.
CONFIG_TOML = """
# This target is important so that we filter out the sources used to build
# the flatc binary, which we don't need at runtime. But we do need the core
# flatbuffers headers.
[targets.program_schema]
buck_targets = [
    "//schema:program",
]
filters = [
    ".fbs$",
    "/include/flatbuffers/.*[.]h$",
]

# List the .cpp and .h files used to build the core runtime. Does not include
# the generated schema headers nor the core flatbuffers headers.
[targets.executorch]
buck_targets = [
    "//runtime/executor:program",
]
deps = [
    "program_schema",
]
filters = [
    ".cpp$",
    ".h$",
]
excludes = [
    "^third-party",
]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combines ExecuTorch sources into a smaller number of .cpp and .h files",
    )
    parser.add_argument(
        "--buck2",
        default="buck2",
        help="'buck2' command to use",
    )
    # parser.add_argument(
    #     "--targets",
    #     default=["executorch"],
    #     required=True,
    #     help="Targets to amalgamate",
    # )
    parser.add_argument(
        "--outdir",
        metavar="/out/dir",
        required=True,
        help="Path to the directory to write files to.",
    )
    return parser.parse_args()


def build_fbs_headers(fbs_sources: list[str], runner: Buck2Runner) -> dict[str, str]:
    """Builds flatbuffer-based headers and returns an include-to-file mapping.

    Args:
        fbs_srcs: List of source files to build or translate. Should contain
            only .fbs files or header files under a flatbuffers/include/...
            directory.
        runner: The Buck2Runner to use to run commands.

    Returns:
        A dictionary mapping include paths to actual file locations, either
        absolute or relative to the root of the tree.
    """
    include_to_header: dict[str, str] = {}
    for src in fbs_sources:
        if "/include/flatbuffers/" in src:
            # Add a mapping for the flatbuffer file, which will be included like
            # "flatbuffers/flatbuffers.h".
            include_to_header[re.sub(r'.*/include/', '', src)] = src
            continue

        assert(src.endswith(".fbs")), f"Unexpected file name: {src}"

        # Get the file stem: e.g., "schema/program.fbs" -> "program"
        stem, _ = os.path.splitext(os.path.basename(src))

        # Get the name of the header file.
        header = f"{stem}_generated.h"

        # Build it and get its location.
        stdout = runner.run([
            "build",
            # It's a little fragile to hard-code this internal target,
            # but since these headers aren't part of the public API we
            # need to do something like this.
            f"//schema:generate_program[{header}]",
            "--show-full-output",
        ])
        assert len(stdout) == 1, f"Expected one line of output, got:\n{repr(stdout)}"
        # The line should have two fields separated by a space. The
        # second is the absolute path to the built header.
        _, abs_header = stdout[0].split(" ", maxsplit=1)

        # Mappings from the include path to the built path.
        include_to_header[f"executorch/schema/{header}"] = abs_header
        # Generated headers can include other generated headers without a path
        # prefix.
        include_to_header[f"{header}"] = abs_header

    return include_to_header


def main():
    args = parse_args()
    runner: Buck2Runner = Buck2Runner(args.buck2)

    # Get the list of source files.
    logging.info("Querying source list from buck2...")
    target_to_srcs = query_targets_to_srcs(CONFIG_TOML, runner)

    # For .fbs files, build the generated headers and get a mapping from the
    # include path (e.g., "executorch/schema/program.h") to the built header
    # path (somewhere under buck-out). Intentionally die with KeyError if this
    # key isn't present.
    logging.info("Building flatbuffer headers...")
    include_to_file = build_fbs_headers(target_to_srcs["program_schema"], runner)

    # Finish out the include mapping by adding entries prefixed with
    # "executorch/" to match the expected include paths. Intentinally die with
    # KeyError if this key isn't present.
    for src in target_to_srcs["executorch"]:
        if src.endswith(".h"):
            include_to_file[f"executorch/{src}"] = src

    for k, v in include_to_file.items():
        print(f"{k}: {v}")
    logging.info(f"Root {runner.root}")

    # Generate executorch.cpp.
    cpp_srcs = [src for src in target_to_srcs["executorch"] if src.endswith(".cpp")]
    with open(os.path.join(args.outdir, "executorch.cpp"), "w") as fp:
        fp.write("/* @" + "generated */\n")
        fp.write("/* Try building with: " + "clang++ --std=c++17 -c executorch.cpp -o executorch.o */\n")
        amalgamate_sources(fp, root=runner.root, srcs=cpp_srcs, includes_to_paths=include_to_file, line_macros=True)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    main()
