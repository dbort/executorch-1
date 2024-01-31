#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import os
import re
import subprocess

from extract_sources import query_targets_to_srcs

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
  "/flatbuffers/flatbuffers.h$",
  "/flatbuffers/base.h$",
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
        description="Combines .cpp and .h files into a smaller number of files",
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


def main():
    args = parse_args()

    target_to_srcs = query_targets_to_srcs(CONFIG_TOML, args.buck2)
    print(target_to_srcs)


if __name__ == "__main__":
    main()
