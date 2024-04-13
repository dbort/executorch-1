# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# This file is sourced into the environment before building a pip wheel. It
# should typically only contain shell variable assignments.

# Enable pybindings so that users can execute ExecuTorch programs from python.
EXECUTORCH_BUILD_PYBIND=ON

# Link the XNNPACK backend into the pybindings runtime so that users can execute
# ExecuTorch programs that delegate to it.
EXECUTORCH_BUILD_XNNPACK=ON
