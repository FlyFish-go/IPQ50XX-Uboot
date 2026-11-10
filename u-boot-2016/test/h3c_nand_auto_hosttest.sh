#!/bin/sh
# h3c_nand_auto_hosttest.sh - run-time NAND profile selection (pure core) and
# the build-identity compatibility rules that depend on it.
set -eu
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror \
  -DH3C_NAND_AUTO_HOST_TEST -DH3C_NAND_ECC_HOST_TEST \
  -Iinclude -idirafter include test/h3c_nand_auto_hosttest.c \
  lib/h3c_nand_auto_core.c lib/h3c_nand_ecc_core.c -o "$tmp/auto"
"$tmp/auto"

# Build identity: an auto build and a pinned build that accepts auto uploads.
for variant in auto pinned; do
  if [ "$variant" = auto ]; then
    defs="-DCONFIG_H3C_NAND_AUTO_PROFILE=1 -DCONFIG_H3C_NAND_ACCEPT_AUTO_IMAGE=1"
  else
    defs="-DCONFIG_H3C_NAND_ACCEPT_AUTO_IMAGE=1 -DCONFIG_H3C_NAND_PROFILE_ID=\"h3c-oem-efba-128m-2k-sp64\" -DCONFIG_H3C_NAND_SOURCE_MASK=0x1 -DCONFIG_H3C_NAND_LOAD_ECC_BITS=4"
  fi
  # shellcheck disable=SC2086
  cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -DH3C_BUILD_ID_HOST_TEST \
    -DCONFIG_TARGET_IPQ5018_H3C_HW_A $defs -Iinclude -idirafter include \
    test/h3c_build_id_auto_hosttest.c failsafe/modules/h3c_build_id.c -o "$tmp/id-$variant"
  "$tmp/id-$variant"
done
