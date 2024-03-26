#!/bin/bash
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# Test the end-to-end flow of using custom operator in a PyTorch model and use
# EXIR to capture and export a model file. Then use `executor_runner` demo C++
# binary to run the model.

set -eu
set -o pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/../../../.ci/scripts/utils.sh"

# Allow overriding the number of build jobs. The `-` makes this safe to check
# even if the variable isn't defined; it is not a negative value.
readonly NUM_JOBS=${CMAKE_BUILD_PARALLEL_LEVEL:-9}

test_buck2_custom_op_1() {
  local model_name='custom_ops_1'
  echo "Exporting ${model_name}.pte"
  ${PYTHON_EXECUTABLE} -m "examples.portable.custom_ops.${model_name}"
  # should save file custom_ops_1.pte

  echo 'Running executor_runner'
  $BUCK run //examples/portable/executor_runner:executor_runner \
      --config=executorch.register_custom_op=1 -- --model_path="./${model_name}.pte"
  # should give correct result

  echo "Removing ${model_name}.pte"
  rm "./${model_name}.pte"
}

test_cmake_custom_op_1() {
  local model_name='custom_ops_1'
  echo "Exporting ${model_name}.pte"
  ${PYTHON_EXECUTABLE} -m "examples.portable.custom_ops.${model_name}"
  # should save file custom_ops_1.pte
  local example_dir=examples/portable/custom_ops
  local build_dir=cmake-out/${example_dir}
  rm -rf ${build_dir}
  retry cmake \
        -DREGISTER_EXAMPLE_CUSTOM_OP=1 \
        -DPYTHON_EXECUTABLE="$PYTHON_EXECUTABLE" \
        -B${build_dir} \
        ${example_dir}

  echo "Building ${example_dir}"
  cmake --build ${build_dir} -j${NUM_JOBS} --config Release

  echo 'Running custom_ops_executor_runner'
  ${build_dir}/custom_ops_executor_runner --model_path="./${model_name}.pte"
}

test_buck2_custom_op_2() {
  local model_name='custom_ops_2'

  echo 'Building custom ops shared library'
  SO_LIB=$($BUCK build //examples/portable/custom_ops:custom_ops_aot_lib_2 --show-output | grep "buck-out" | cut -d" " -f2)

  echo "Exporting ${model_name}.pte"
  ${PYTHON_EXECUTABLE} -m "examples.portable.custom_ops.${model_name}" --so_library="$SO_LIB"
  # should save file custom_ops_2.pte

  $BUCK run //examples/portable/executor_runner:executor_runner \
      --config=executorch.register_custom_op=2 -- --model_path="./${model_name}.pte"
  # should give correct result
  echo "Removing ${model_name}.pte"
  rm "./${model_name}.pte"
}

get_shared_lib_ext() {
  UNAME=$(uname)
  if [[ $UNAME == "Darwin" ]];
  then
    EXT=".dylib"
  elif [[ $UNAME == "Linux" ]];
  then
    EXT=".so"
  else
    echo "Unsupported platform $UNAME"
    exit 1
  fi
  echo $EXT
}

test_cmake_custom_op_2() {
  local model_name='custom_ops_2'
  # Declare as local separately so it doesn't hide errors when executing the
  # subcommand.
  local site_packages
  site_packages="$(${PYTHON_EXECUTABLE} -c \
    'from distutils.sysconfig import get_python_lib; print(get_python_lib())')"
  # executorch-config.cmake is installed under cmake-out. The torch config lives
  # inside its installed pip package.
  local cmake_prefix_path="$PWD/cmake-out;${site_packages}/torch"

  local example_dir=examples/portable/custom_ops
  local build_dir=cmake-out/${example_dir}
  rm -rf ${build_dir}
  retry cmake \
        -DREGISTER_EXAMPLE_CUSTOM_OP=2 \
        -DCMAKE_PREFIX_PATH="${cmake_prefix_path}" \
        -DPYTHON_EXECUTABLE="${PYTHON_EXECUTABLE}" \
        -B${build_dir} \
        ${example_dir}

  echo "Building ${example_dir}"
  cmake --build ${build_dir} -j${NUM_JOBS} --config Release

  EXT=$(get_shared_lib_ext)
  echo "Exporting ${model_name}.pte"
  ${PYTHON_EXECUTABLE} -m "examples.portable.custom_ops.${model_name}" --so_library="cmake-out/examples/portable/custom_ops/libcustom_ops_aot_lib$EXT"
  # should save file custom_ops_2.pte

  echo 'Running custom_ops_executor_runner'
  ${build_dir}/custom_ops_executor_runner --model_path="./${model_name}.pte"
}

if [[ -z ${PYTHON_EXECUTABLE:-} ]];
then
  PYTHON_EXECUTABLE=python3
fi

if [[ -z ${BUCK:-} ]];
then
  BUCK=buck2
fi

if [[ $1 == "cmake" ]];
then
  cmake_install_executorch_lib
  test_cmake_custom_op_1
  test_cmake_custom_op_2
elif [[ $1 == "buck2" ]];
then
  test_buck2_custom_op_1
  test_buck2_custom_op_2
else
  cmake_install_executorch_lib
  test_cmake_custom_op_1
  test_cmake_custom_op_2
  test_buck2_custom_op_1
  test_buck2_custom_op_2
fi
