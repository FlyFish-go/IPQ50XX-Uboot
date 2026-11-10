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

